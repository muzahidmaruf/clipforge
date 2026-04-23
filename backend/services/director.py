"""
Motion-graphics director.

Takes a clip's word-level transcript and asks Gemma to plan a timeline of
motion-graphics overlays (lower thirds, stat cards, pull quotes). Returns a
validated shot list cached to disk.
"""
import os
import json
import re
import requests
from config import (
    OLLAMA_CLOUD_BASE_URL,
    OLLAMA_CLOUD_API_KEY,
    OLLAMA_CLOUD_MODEL,
    OLLAMA_CLOUD_TIMEOUT,
    MOTION_DIR,
)

# Currently supported component types. Adding a new type = add it here + schema
# below + a React component on the frontend.
SUPPORTED_TYPES = {"lower_third", "stat_card", "pull_quote"}

DIRECTOR_PROMPT = """You are a senior motion graphics designer working on a short-form video (TikTok / Reels / Shorts). Your job is to read the word-level transcript below and plan a TIMELINE of on-screen motion graphics that make this clip feel designed, not raw.

You have exactly THREE component types available. Use them sparingly — quality over quantity. A 60-second clip should have 3 to 6 cues total, never more than one graphic on screen at a time, and at least 3 seconds of breathing room between cues.

---

COMPONENTS:

1. **lower_third** — animated name/title strip. Use ONCE at the START of the clip ONLY if the transcript clearly identifies a speaker (name + role/credential). Do NOT invent names.
   Fields: `title` (person's name, uppercase), `sub` (their role, title case, max 40 chars)

2. **stat_card** — big number pop. Use when the transcript mentions a specific statistic, percentage, dollar amount, or striking number that is central to the point. The number MUST appear in the transcript exactly. Skip if there's no real stat.
   Fields: `number` (the figure exactly as said, e.g. "80%", "$2.4B", "10,000"), `label` (what the number represents, max 50 chars, title case)

3. **pull_quote** — full-screen quote emphasis. Use for the SINGLE most powerful, quotable sentence in the clip — a punchy one-liner, counterintuitive claim, or mic-drop moment. Pick only ONE per clip.
   Fields: `text` (a direct quote of the sentence, under 80 chars, ending with punctuation)

---

TIMING RULES:
- `t` is the START time in seconds (float, relative to clip start at 0).
- Align cues to when the speaker SAYS the relevant content, not before. For a stat, `t` should be slightly BEFORE the number is said (0.3s lead-in feels natural).
- For `lower_third`, t should be between 0.5 and 3.0.
- For `pull_quote`, t should be AFTER the quote starts — let the viewer hear the first few words, then reinforce visually.
- Never place a cue in the last 2 seconds of the clip.

---

SELECTION RULES (critical):
- If there's no speaker intro → NO lower_third.
- If there's no real statistic → NO stat_card. Do not invent.
- If nothing is quote-worthy → NO pull_quote.
- It is perfectly fine to return an empty array. A plain clip is better than forced, generic graphics.
- Do NOT describe actions, emotions, or anything outside of these three components.

---

TRANSCRIPT (word-level, time in seconds from clip start):
{transcript}

CLIP DURATION: {duration} seconds

---

OUTPUT:
Respond with ONLY a valid JSON array. No prose, no markdown, no code fences.

Example:
[
  {{"t": 1.2, "type": "lower_third", "title": "DR. ANDREW HUBERMAN", "sub": "Neuroscientist, Stanford"}},
  {{"t": 18.4, "type": "stat_card", "number": "90%", "label": "Of habits form within 66 days"}},
  {{"t": 42.0, "type": "pull_quote", "text": "Your brain literally rewires while you sleep."}}
]"""


def _call_gemma(prompt: str) -> list:
    if not OLLAMA_CLOUD_API_KEY:
        raise RuntimeError("OLLAMA_CLOUD_API_KEY not set")

    url = f"{OLLAMA_CLOUD_BASE_URL}/api/generate"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}"},
        json={
            "model": OLLAMA_CLOUD_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.4,
                "top_p": 0.9,
                "num_predict": 1200,
            },
        },
        timeout=OLLAMA_CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    raw = response.json()["response"].strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # Find the JSON array
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    return json.loads(raw)


def _build_transcript_text(words: list) -> str:
    """Compact one-line-per-sentence-ish transcript with leading timestamps."""
    lines = []
    buf = []
    buf_start = None
    for w in words:
        if buf_start is None:
            buf_start = w["start"]
        buf.append(w["word"])
        # Flush on sentence-ending punctuation or after ~12 words
        txt = w["word"]
        if txt.endswith((".", "!", "?")) or len(buf) >= 12:
            lines.append(f"[{buf_start:.2f}s] {' '.join(buf)}")
            buf = []
            buf_start = None
    if buf:
        lines.append(f"[{buf_start:.2f}s] {' '.join(buf)}")
    return "\n".join(lines)


def _validate_cue(cue: dict, duration: float) -> dict | None:
    """Return a normalized cue, or None if invalid."""
    if not isinstance(cue, dict):
        return None
    cue_type = cue.get("type")
    if cue_type not in SUPPORTED_TYPES:
        return None

    try:
        t = float(cue.get("t", -1))
    except (TypeError, ValueError):
        return None
    if t < 0 or t > max(0, duration - 2.0):
        return None

    if cue_type == "lower_third":
        title = str(cue.get("title", "")).strip()
        sub = str(cue.get("sub", "")).strip()[:40]
        if not title or len(title) > 40:
            return None
        return {"t": round(t, 2), "type": cue_type, "title": title.upper(), "sub": sub}

    if cue_type == "stat_card":
        number = str(cue.get("number", "")).strip()
        label = str(cue.get("label", "")).strip()[:50]
        if not number or not label or len(number) > 10:
            return None
        return {"t": round(t, 2), "type": cue_type, "number": number, "label": label}

    if cue_type == "pull_quote":
        text = str(cue.get("text", "")).strip()
        if not text or len(text) > 80 or len(text) < 8:
            return None
        return {"t": round(t, 2), "type": cue_type, "text": text}

    return None


def _dedupe_and_space(cues: list, min_gap: float = 3.0) -> list:
    """Keep cues ordered by time, enforcing minimum gap and one type per clip for lower_third/pull_quote."""
    cues = sorted(cues, key=lambda c: c["t"])
    kept = []
    seen_singletons = set()
    last_t = -999.0
    for c in cues:
        if c["t"] - last_t < min_gap:
            continue
        if c["type"] in ("lower_third", "pull_quote"):
            if c["type"] in seen_singletons:
                continue
            seen_singletons.add(c["type"])
        kept.append(c)
        last_t = c["t"]
    return kept


def generate_motion(clip_id: str, words: list, duration: float, force: bool = False) -> list:
    """
    Generate the motion-graphics shot list for a clip.

    Caches to MOTION_DIR/{clip_id}.json. Re-uses cache unless force=True.
    Returns [] on any failure (non-fatal — captions still work).
    """
    cache_path = os.path.join(MOTION_DIR, f"{clip_id}.json")
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f).get("cues", [])
        except Exception:
            pass

    if not words:
        return []

    transcript_text = _build_transcript_text(words)
    prompt = DIRECTOR_PROMPT.format(transcript=transcript_text, duration=f"{duration:.1f}")

    try:
        raw_cues = _call_gemma(prompt)
    except Exception as e:
        # Non-fatal: just return empty so the UI still works
        print(f"[director] Gemma call failed for clip {clip_id}: {e}")
        return []

    if not isinstance(raw_cues, list):
        return []

    validated = []
    for cue in raw_cues:
        v = _validate_cue(cue, duration)
        if v:
            validated.append(v)

    validated = _dedupe_and_space(validated)

    # Cache
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"clip_id": clip_id, "duration": duration, "cues": validated}, f, indent=2)
    except Exception:
        pass

    return validated
