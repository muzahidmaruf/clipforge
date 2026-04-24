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

# Motion-graphics template library catalog (vendored in the frontend tree).
# We read it so Gemma knows what templates/lotties are actually available.
_LIBRARY_CATALOG_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "frontend", "src", "components", "motion", "library", "catalog.json",
    )
)


def _load_library_catalog():
    """Load the vendored template library catalog. Silently returns None if
    the frontend isn't installed (e.g. backend-only deploys)."""
    try:
        with open(_LIBRARY_CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _format_catalog_for_prompt(catalog):
    """Compact a catalog into a short bullet list Gemma can digest without
    blowing the context budget."""
    if not catalog:
        return ""
    libs = catalog.get("libraries", {})
    lines = []
    mu = libs.get("magic-ui", {}).get("components", [])
    if mu:
        lines.append("magic-ui (text + effects): " + ", ".join(mu[:40]))
    mp = libs.get("motion-primitives", {}).get("components", [])
    if mp:
        lines.append("motion-primitives: " + ", ".join(mp))
    rb = libs.get("react-bits", {}).get("categories", {})
    for cat, names in rb.items():
        if names:
            lines.append(f"react-bits/{cat}: " + ", ".join(names[:30]))
    lot = libs.get("lotties", {}).get("assets", [])
    if lot:
        lines.append("lotties (icon animations, JSON): " + ", ".join(lot))
    return "\n".join(lines)

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
    "word_treatment",
    "template",
    "lottie",
}

# All treatments the frontend can render for word_treatment cues.
WORD_TREATMENTS = {
    "highlight",      # yellow highlighter swipes L→R behind the word
    "scale_pop",      # scales to 2.2x then settles to 1.1x
    "shake",          # rapid horizontal tremor
    "strikethrough",  # line draws through (for negation/deletion)
    "glow_pulse",     # text-shadow pulses primary color
    "color_flash",    # word flashes primary color then returns
    "stamp",          # rotates in like a rubber stamp
    "drop",           # drops down from above landing with impact
    "rise",           # rises up like being pulled
    "underline_draw", # dotted underline animates L→R
    "blur_reveal",    # starts blurred + transparent, sharpens into focus
    "chromatic",      # RGB split glitch effect
}

DIRECTOR_PROMPT = """You are a senior motion graphics designer working on a short-form video (TikTok / Reels / Shorts). Your job is to read the word-level transcript and choreograph BOTH (a) per-word visual treatments that make specific spoken words pop dramatically, and (b) occasional full-screen motion graphics for peak moments.

The caption track is always visible. Your primary tool is WORD TREATMENTS — you pick specific individual words in the transcript and give each one a custom visual treatment that triggers exactly when that word is spoken. This is what makes the video feel DESIGNED, like Submagic or Opus Clip. Aim for 6 to 14 word treatments across a 60-second clip — roughly one every 4-7 seconds.

Additionally, use 1 to 3 full-screen components (pull_quote, kinetic_slam, confetti, etc.) ONLY for peak moments where a whole caption take-over is justified.

---

WORD TREATMENTS (your PRIMARY tool):

Each cue takes the form:
`{{"t": <exact timestamp in seconds>, "type": "word_treatment", "word": "<exact word from transcript>", "treatment": "<one of the treatment names>"}}`

The `word` must appear verbatim in the transcript at approximately time `t` (within ±0.5s). You may include punctuation if that's how it appears.

Available treatments (pick the one that matches the emotional beat of the word):

- **highlight** — yellow highlighter swipes behind the word. Use for KEY CONCEPTS the viewer must remember.
- **scale_pop** — word scales to 2.2× and settles at 1.1×. Use for BIG, EMPHATIC words ("HUGE", "MASSIVE", "NEVER").
- **shake** — rapid horizontal tremor. Use for INTENSITY / ANGER / URGENCY words ("crashed", "exploded", "RIGHT NOW").
- **strikethrough** — line draws through the word. Use for NEGATION or CORRECTIONS ("wrong", "not", "never").
- **glow_pulse** — primary-color glow pulses around the word. Use for MAGIC / SPECIAL / REVEAL words ("secret", "hidden", "truth").
- **color_flash** — word flashes the primary color. Use for IMPORTANT but not loud words — a subtle accent.
- **stamp** — word rotates in like a rubber stamp. Use for VERDICTS / LABELS ("approved", "rejected", "proven", "fake").
- **drop** — word drops from above with impact. Use for CONCLUSIONS / ENDINGS / FINAL POINTS ("done", "that's it", "end").
- **rise** — word floats up. Use for UPLIFTING words ("grew", "soared", "hope", "rise").
- **underline_draw** — dotted underline animates L→R under the word. Use for DEFINITIONS / TERMS introduced by the speaker.
- **blur_reveal** — word starts blurred and snaps into focus. Use for REVEAL / INSIGHT moments ("realize", "discover", "actually").
- **chromatic** — RGB-split glitch effect. Use for GLITCHY / UNSETTLING / SURREAL words ("crazy", "insane", "mind-bending").

GOOD EXAMPLES:
- When the speaker says "dopamine is not the pleasure chemical" → treatment on "not" (strikethrough)
- When the speaker says "80% of decisions are SUBCONSCIOUS" → treatment on "subconscious" (scale_pop)
- When the speaker says "here's the secret" → treatment on "secret" (glow_pulse)
- When the speaker says "they CRASHED the market" → treatment on "crashed" (shake)
- When the speaker says "you're wrong" → treatment on "wrong" (strikethrough)

---

FULL-SCREEN COMPONENTS (use sparingly, max 3 per clip, at least 4 seconds apart):

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

9. **template** — drop in a pre-built motion-graphics template from the vendored library (see TEMPLATE LIBRARY below). Use for rich backgrounds, animated text effects, decorative borders, or full-screen hero moments that the built-in components don't cover. Pick a template whose NAME clearly matches the vibe of what the speaker is saying (e.g. `aurora` for a dreamy moment, `sparkles-text` for a magical reveal, `typing-text` for a reveal beat). Max 2 per clip. Keep the chosen name EXACTLY as it appears in the library list.
   Fields: `library` ("magic-ui" | "motion-primitives" | "react-bits"), `name` (exact template name from the list), `category` (REQUIRED for react-bits: one of `text` / `animations` / `backgrounds` / `components`), optional `text` (if the template shows text, the caption it should display — short, from the transcript).

10. **lottie** — play a small Lottie icon animation as an overlay. Use for punchy emoji-style reactions when the speaker says something that clearly maps to an available asset (e.g. `thumbs_up`, `heart_beat`, `rocket_launch`, `confetti_burst`, `trophy`). Max 3 per clip. The `lottie_id` MUST be from the LOTTIES list below.
   Fields: `lottie_id` (exact asset name from the lotties list), optional `position` ("top-left" | "top-right" | "bottom-left" | "bottom-right" | "center"), optional `scale` (0.3–1.5, default 0.6).

---

TEMPLATE LIBRARY (available vendored assets — pick ONLY from these names):

{template_library}

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

Example of a well-directed 45s clip (mostly word treatments, one peak moment):
[
  {{"t": 2.4, "type": "word_treatment", "word": "secretly", "treatment": "glow_pulse"}},
  {{"t": 5.8, "type": "word_treatment", "word": "80%", "treatment": "scale_pop"}},
  {{"t": 8.2, "type": "word_treatment", "word": "subconscious", "treatment": "highlight"}},
  {{"t": 12.0, "type": "word_treatment", "word": "not", "treatment": "strikethrough"}},
  {{"t": 12.6, "type": "word_treatment", "word": "pleasure", "treatment": "strikethrough"}},
  {{"t": 15.1, "type": "word_treatment", "word": "prediction", "treatment": "scale_pop"}},
  {{"t": 19.3, "type": "word_treatment", "word": "realize", "treatment": "blur_reveal"}},
  {{"t": 22.5, "type": "word_treatment", "word": "crashed", "treatment": "shake"}},
  {{"t": 26.0, "type": "word_treatment", "word": "wrong", "treatment": "stamp"}},
  {{"t": 30.2, "type": "pull_quote", "text": "The anticipation is the high."}},
  {{"t": 38.5, "type": "word_treatment", "word": "everything", "treatment": "drop"}}
]"""


def _call_gemma(prompt: str) -> list:
    """Call Ollama Cloud via OpenAI-compatible API (https://ollama.com/v1/chat/completions)."""
    if not OLLAMA_CLOUD_API_KEY:
        raise RuntimeError("OLLAMA_CLOUD_API_KEY not set")

    url = f"{OLLAMA_CLOUD_BASE_URL}/v1/chat/completions"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OLLAMA_CLOUD_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.4,
            "top_p": 0.9,
            "max_tokens": 1200,
        },
        timeout=OLLAMA_CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if present
    if "```" in raw:
        parts = raw.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:
                chunk = part.lstrip("json").lstrip("JSON").strip()
                if chunk.startswith("["):
                    raw = chunk
                    break

    raw = raw.strip()

    # Find the JSON array anywhere in the response
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


def _catalog_index(catalog):
    """Build quick lookup sets for validating template/lottie cues."""
    idx = {
        "magic-ui": set(),
        "motion-primitives": set(),
        "react-bits": {},  # category -> set(names)
        "lotties": set(),
    }
    if not catalog:
        return idx
    libs = catalog.get("libraries", {})
    idx["magic-ui"] = set(libs.get("magic-ui", {}).get("components", []))
    idx["motion-primitives"] = set(libs.get("motion-primitives", {}).get("components", []))
    rb = libs.get("react-bits", {}).get("categories", {})
    idx["react-bits"] = {cat: set(names) for cat, names in rb.items()}
    idx["lotties"] = set(libs.get("lotties", {}).get("assets", []))
    return idx


# Cached catalog index (rebuilt on each module reload, which is fine for dev)
_CATALOG_INDEX = _catalog_index(_load_library_catalog())


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

    if cue_type == "word_treatment":
        word = str(cue.get("word", "")).strip()
        treatment = str(cue.get("treatment", "")).strip().lower()
        if not word or len(word) > 24:
            return None
        if treatment not in WORD_TREATMENTS:
            return None
        return {"t": round(t, 2), "type": cue_type, "word": word, "treatment": treatment}

    if cue_type == "confetti":
        intensity = str(cue.get("intensity", "medium")).strip().lower()
        if intensity not in ("low", "medium", "high"):
            intensity = "medium"
        return {"t": round(t, 2), "type": cue_type, "intensity": intensity}

    if cue_type == "template":
        library = str(cue.get("library", "")).strip()
        name = str(cue.get("name", "")).strip()
        category = str(cue.get("category", "")).strip() or None
        if library not in ("magic-ui", "motion-primitives", "react-bits"):
            return None
        if not name:
            return None
        if library == "react-bits":
            if not category or category not in _CATALOG_INDEX["react-bits"]:
                return None
            if name not in _CATALOG_INDEX["react-bits"][category]:
                return None
        else:
            if name not in _CATALOG_INDEX[library]:
                return None
        out = {"t": round(t, 2), "type": cue_type, "library": library, "name": name}
        if category:
            out["category"] = category
        text = cue.get("text")
        if text is not None:
            s = str(text).strip()[:80]
            if s:
                out["text"] = s
        return out

    if cue_type == "lottie":
        lottie_id = str(cue.get("lottie_id", "")).strip()
        if not lottie_id:
            return None
        # If a catalog is installed, enforce membership. If not, reject all lottie cues.
        if not _CATALOG_INDEX["lotties"] or lottie_id not in _CATALOG_INDEX["lotties"]:
            return None
        position = str(cue.get("position", "center")).strip().lower()
        if position not in ("top-left", "top-right", "bottom-left", "bottom-right", "center"):
            position = "center"
        try:
            scale = float(cue.get("scale", 0.6))
        except (TypeError, ValueError):
            scale = 0.6
        scale = max(0.3, min(1.5, scale))
        return {
            "t": round(t, 2),
            "type": cue_type,
            "lottie_id": lottie_id,
            "position": position,
            "scale": round(scale, 2),
        }

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
    """Order by time. Word treatments flow freely; full-screen cues need spacing.
    Singleton types are capped at one per clip."""
    cues = sorted(cues, key=lambda c: c["t"])
    kept = []
    seen_singletons = set()
    last_fullscreen_t = -999.0
    SINGLETONS = {"lower_third", "pull_quote", "kinetic_slam", "confetti"}

    # Cap the number of templates and lotties per clip
    template_budget = 2
    lottie_budget = 3

    for c in cues:
        if c["type"] == "word_treatment":
            # Word treatments don't need spacing
            kept.append(c)
            continue

        if c["type"] == "lottie":
            if lottie_budget <= 0:
                continue
            lottie_budget -= 1
            kept.append(c)
            continue

        if c["type"] == "template":
            if template_budget <= 0:
                continue
            if c["t"] - last_fullscreen_t < min_gap:
                continue
            template_budget -= 1
            kept.append(c)
            last_fullscreen_t = c["t"]
            continue

        # Full-screen component — enforce gap and singleton rule
        if c["t"] - last_fullscreen_t < min_gap:
            continue
        if c["type"] in SINGLETONS:
            if c["type"] in seen_singletons:
                continue
            seen_singletons.add(c["type"])
        kept.append(c)
        last_fullscreen_t = c["t"]

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
    catalog = _load_library_catalog()
    library_block = _format_catalog_for_prompt(catalog) if catalog else "(no template library installed — do NOT emit `template` or `lottie` cues)"
    prompt = DIRECTOR_PROMPT.format(
        transcript=transcript_text,
        duration=f"{duration:.1f}",
        template_library=library_block,
    )

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
