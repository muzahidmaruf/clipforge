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
SUPPORTED_TYPES = {
    "lower_third",
    "stat_card",
    "pull_quote",
    "kinetic_slam",
    "bullet_cascade",
    "progress_bar",
    "bar_chart",
    "confetti",
}

DIRECTOR_PROMPT = """You are a senior motion graphics designer working on a short-form video (TikTok / Reels / Shorts). Your job is to read the word-level transcript below and plan a TIMELINE of on-screen motion graphics that make this clip feel designed, not raw.

You have SEVEN component types available. Use them sparingly — quality over quantity. A 60-second clip should have 4 to 7 cues total, never more than one graphic on screen at a time, and at least 2.5 seconds of breathing room between cues.

---

COMPONENTS:

1. **lower_third** — animated name/title strip. Use ONCE at the START only if the transcript clearly identifies a speaker (name + role). Do NOT invent names.
   Fields: `title` (name, uppercase), `sub` (role, title case, max 40 chars)

2. **stat_card** — big number pop. The number MUST appear verbatim in the transcript. Skip if no real stat.
   Fields: `number` (e.g. "80%", "$2.4B", "10,000"), `label` (max 50 chars, title case)

3. **pull_quote** — full-screen quote. Use for the SINGLE most powerful, mic-drop sentence in the clip. At most ONE per clip.
   Fields: `text` (direct quote, 8–80 chars, ends with punctuation)

4. **kinetic_slam** — 2–5 individual words that slam onto screen one by one for dramatic emphasis. Use for punchlines, beat drops, or triple-beat emphasis moments (e.g. "THIS. CHANGES. EVERYTHING." or "FASTER. BETTER. CHEAPER."). Words must appear in sequence in the transcript around time `t`. At most ONE per clip.
   Fields: `words` (array of 2–5 uppercased strings, each 2–14 chars)

5. **bullet_cascade** — vertical list of 2–5 short items that cascade in. Use ONLY when the speaker enumerates a concrete list (e.g. "three things: attention, memory, and emotion"). Items must be the actual things listed.
   Fields: `title` (optional short header, max 30 chars, title case), `items` (array of 2–5 strings, each 2–28 chars, title case, no trailing period)

6. **progress_bar** — horizontal bar that fills to a percentage with a big number counter. Use for percentage-based claims (e.g. "73% of people...", "only 10% succeed"). Percentage must be in the transcript.
   Fields: `label` (what the % measures, max 40 chars, title case), `value` (integer 0–100)

7. **bar_chart** — 2–4 labeled horizontal bars growing to proportional lengths. Use ONLY when the speaker compares multiple concrete numeric values (e.g. "sales went from 40 to 68 to 120"). All values must be real numbers from the transcript.
   Fields: `title` (optional short header, max 30 chars), `bars` (array of 2–4 objects: `{{label: string max 14 chars, value: number}}`)

8. **confetti** — particle celebration burst. Use ONCE per clip, ONLY for a genuine win/celebration/breakthrough/achievement moment (e.g. "finally got it", "we did it", "hit a million", "success", "after years of struggle"). Do NOT use for generic positive vibes.
   Fields: `intensity` ("low" | "medium" | "high") — `high` for huge wins, `low` for smaller positive beats

---

TIMING RULES:
- `t` is the START time in seconds (float, relative to clip start at 0).
- Align cues to when the speaker starts SAYING the relevant content.
- For `lower_third`, t between 0.5 and 3.0.
- For `pull_quote`, `kinetic_slam`, `stat_card`, `progress_bar` — `t` should land as the content is being said (0.2–0.5s lead-in feels right).
- For `bullet_cascade` — `t` at the start of the list phrase.
- Never place a cue in the last 2 seconds of the clip.

---

SELECTION RULES (critical):
- No speaker intro? → NO `lower_third`.
- No real stat/number? → NO `stat_card`.
- No mic-drop quote? → NO `pull_quote`.
- No 2–5 word emphatic punchline? → NO `kinetic_slam`.
- No actual enumerated list? → NO `bullet_cascade`.
- No percentage? → NO `progress_bar`.
- No compared numeric values? → NO `bar_chart`.
- No genuine win/celebration moment? → NO `confetti`.
- It is perfectly fine to return an empty array. Plain is better than forced or fake.
- NEVER invent numbers, names, or facts. Everything must come from the transcript.

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
  {{"t": 14.0, "type": "bullet_cascade", "title": "Three Pillars", "items": ["Attention", "Memory", "Emotion"]}},
  {{"t": 24.8, "type": "progress_bar", "label": "Habits form within 66 days", "value": 90}},
  {{"t": 38.5, "type": "kinetic_slam", "words": ["THIS", "CHANGES", "EVERYTHING"]}},
  {{"t": 48.0, "type": "pull_quote", "text": "Your brain rewires while you sleep."}}
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
        # Must contain at least one digit — otherwise it's not a stat
        if not re.search(r"\d", number):
            return None
        return {"t": round(t, 2), "type": cue_type, "number": number, "label": label}

    if cue_type == "pull_quote":
        text = str(cue.get("text", "")).strip()
        if not text or len(text) > 80 or len(text) < 8:
            return None
        return {"t": round(t, 2), "type": cue_type, "text": text}

    if cue_type == "kinetic_slam":
        words = cue.get("words")
        if not isinstance(words, list) or not (2 <= len(words) <= 5):
            return None
        clean = []
        for w in words:
            s = str(w).strip().upper()
            if not (2 <= len(s) <= 14):
                return None
            clean.append(s)
        return {"t": round(t, 2), "type": cue_type, "words": clean}

    if cue_type == "bullet_cascade":
        items = cue.get("items")
        if not isinstance(items, list) or not (2 <= len(items) <= 5):
            return None
        clean = []
        for it in items:
            s = str(it).strip().rstrip(".").strip()
            if not (2 <= len(s) <= 28):
                return None
            clean.append(s)
        title = str(cue.get("title", "")).strip()[:30] or None
        out = {"t": round(t, 2), "type": cue_type, "items": clean}
        if title:
            out["title"] = title
        return out

    if cue_type == "progress_bar":
        label = str(cue.get("label", "")).strip()[:40]
        try:
            value = int(cue.get("value", -1))
        except (TypeError, ValueError):
            return None
        if not label or not (0 <= value <= 100):
            return None
        return {"t": round(t, 2), "type": cue_type, "label": label, "value": value}

    if cue_type == "confetti":
        intensity = str(cue.get("intensity", "medium")).strip().lower()
        if intensity not in ("low", "medium", "high"):
            intensity = "medium"
        return {"t": round(t, 2), "type": cue_type, "intensity": intensity}

    if cue_type == "bar_chart":
        bars = cue.get("bars")
        if not isinstance(bars, list) or not (2 <= len(bars) <= 4):
            return None
        clean_bars = []
        for b in bars:
            if not isinstance(b, dict):
                return None
            lab = str(b.get("label", "")).strip()[:14]
            try:
                val = float(b.get("value", -1))
            except (TypeError, ValueError):
                return None
            if not lab or val < 0:
                return None
            clean_bars.append({"label": lab, "value": val})
        if max(b["value"] for b in clean_bars) <= 0:
            return None
        title = str(cue.get("title", "")).strip()[:30] or None
        out = {"t": round(t, 2), "type": cue_type, "bars": clean_bars}
        if title:
            out["title"] = title
        return out

    return None


def _dedupe_and_space(cues: list, min_gap: float = 2.5) -> list:
    """Order by time, enforce gap, allow only one of each singleton type per clip."""
    cues = sorted(cues, key=lambda c: c["t"])
    kept = []
    seen_singletons = set()
    last_t = -999.0
    SINGLETONS = {"lower_third", "pull_quote", "kinetic_slam", "confetti"}
    for c in cues:
        if c["t"] - last_t < min_gap:
            continue
        if c["type"] in SINGLETONS:
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
