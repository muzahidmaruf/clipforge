import requests
import json
import re
from config import (
    OLLAMA_CLOUD_BASE_URL,
    OLLAMA_CLOUD_API_KEY,
    OLLAMA_CLOUD_MODEL,
    OLLAMA_CLOUD_TIMEOUT,
    MIN_CLIP_DURATION,
    MAX_CLIP_DURATION,
)
from utils.time_utils import parse_timestamp, seconds_to_timestamp

# ---------------------------------------------------------------------------
# Prompt — inspired by OpenShorts' Gemini prompt, adapted for Qwen/Gemma.
# Key upgrades over the old ClipForge prompt:
#  • Timestamps are ABSOLUTE SECONDS (no HH:MM:SS parsing errors)
#  • Passes word-level JSON for precision boundary detection
#  • Returns viral_hook_text overlay per clip
#  • Returns per-platform descriptions (TikTok / Instagram / YouTube title)
#  • Flexible duration: 15–90 s (catches great short moments + longer stories)
#  • Ordered by predicted performance
# ---------------------------------------------------------------------------
VIRAL_PROMPT = """You are a senior short-form video editor. Read the ENTIRE transcript and word-level timestamps to choose the {num_clips} MOST VIRAL moments for TikTok/Instagram Reels/YouTube Shorts. Each clip must be between 15 and 90 seconds long.

⚠️ TIMESTAMP CONTRACT — STRICTLY FOLLOW:
- Return timestamps as ABSOLUTE SECONDS from the start of the video (decimal, up to 3 decimals).
- Only plain numbers — e.g. 0, 12.340, 47.900. NO HH:MM:SS, NO colons, NO text.
- Ensure 0 ≤ start < end ≤ VIDEO_DURATION_SECONDS.
- Each clip between 15 and 90 seconds.
- Prefer starting 0.2–0.4 s BEFORE the hook word and ending 0.2–0.4 s AFTER the payoff.
- Use silence/pause moments for natural cuts; NEVER cut mid-word or mid-sentence.

VIDEO_DURATION_SECONDS: {video_duration}

TRANSCRIPT (raw text with rough timing):
{transcript_text}

WORD_TIMESTAMPS (array of {{w: word, s: start_seconds, e: end_seconds}}):
{words_json}

STRICT SELECTION CRITERIA — each clip MUST satisfy ALL:
1. COMPLETE THOUGHT — clear beginning, middle, end. A cold viewer understands it.
2. STRONG HOOK — first sentence grabs attention alone (bold claim, surprising stat, question, story).
3. SATISFYING PAYOFF — surprise revealed, question answered, advice given, story lands.
4. NO FLUFF — skip intros, outros, sponsor reads, "like and subscribe".
5. NO OVERLAPS — clips must not overlap at all.
6. VIRAL POTENTIAL — counterintuitive opinion, shocking fact, raw emotion, insider secret, actionable tip.

OUTPUT — RETURN ONLY VALID JSON (no markdown, no comments). Order clips by predicted performance (best first):
{{
  "shorts": [
    {{
      "start": <number in seconds e.g. 12.340>,
      "end": <number in seconds e.g. 47.900>,
      "virality_score": <integer 0-100>,
      "viral_hook_text": "<SHORT punchy overlay text max 8 words. Same language as transcript. Examples: 'Nobody tells you this...', 'Stop doing this!', 'POV: You just learned'>",
      "hook": "<direct quote of first full sentence of this clip>",
      "reason": "<one sentence: why this is self-contained and compelling>",
      "video_description_for_tiktok": "<TikTok caption optimized for views, include relevant hashtags>",
      "video_description_for_instagram": "<Instagram caption optimized for saves and shares>",
      "video_title_for_youtube_short": "<YouTube Shorts title, max 100 chars, click-worthy>"
    }}
  ]
}}"""


def format_words_json(transcript_result: dict, max_words: int = 800) -> str:
    """Extract word-level timestamps from Whisper result as compact JSON.
    Capped at max_words to avoid blowing the context window."""
    words = []
    for seg in transcript_result.get("segments", []):
        for w in seg.get("words", []):
            word = w.get("word", "").strip()
            if word:
                words.append({"w": word, "s": round(w["start"], 3), "e": round(w["end"], 3)})
    # Cap to max_words
    if len(words) > max_words:
        words = words[:max_words]
    return json.dumps(words, ensure_ascii=False, separators=(",", ":"))


def _extract_json(raw: str) -> dict | list:
    """Robustly extract JSON (object or array) from a model response
    that may include preamble text or markdown fences."""
    # Strip markdown code fences
    if "```" in raw:
        parts = raw.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:
                chunk = part.lstrip("json").lstrip("JSON").strip()
                if chunk.startswith(("{", "[")):
                    raw = chunk
                    break
    raw = raw.strip()

    # Try direct parse
    if raw.startswith(("{", "[")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Find JSON object or array anywhere in response
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    return json.loads(raw)


def _call_ollama_cloud(prompt: str, model_name: str):
    """Call Ollama Cloud via OpenAI-compatible API."""
    if not OLLAMA_CLOUD_API_KEY:
        raise RuntimeError("OLLAMA_CLOUD_API_KEY not set — get one at https://ollama.com/settings/keys")

    url = f"{OLLAMA_CLOUD_BASE_URL}/v1/chat/completions"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 3000,
        },
        timeout=OLLAMA_CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    print(f"[analysis] raw response (first 600 chars): {raw[:600]}")
    return _extract_json(raw)


def analyze_transcript(
    transcript_text: str,
    duration: str,
    model_name: str = None,
    num_clips: int = 5,
    transcript_result: dict = None,
    video_duration_seconds: float = None,
):
    """Analyze transcript using Ollama Cloud. Returns list of segment dicts."""
    try:
        num_clips = max(1, min(15, int(num_clips)))
    except (TypeError, ValueError):
        num_clips = 5

    cloud_model = model_name or OLLAMA_CLOUD_MODEL
    print(f"[analysis] model={cloud_model} num_clips={num_clips}")

    # Build word-level JSON for precision boundary detection
    words_json = "[]"
    if transcript_result:
        words_json = format_words_json(transcript_result)

    # Resolve video duration in seconds
    if video_duration_seconds is None:
        try:
            video_duration_seconds = _parse_duration_str(duration)
        except Exception:
            video_duration_seconds = 9999.0

    prompt = VIRAL_PROMPT.format(
        num_clips=num_clips,
        video_duration=round(video_duration_seconds, 3),
        transcript_text=transcript_text,
        words_json=words_json,
    )

    try:
        result = _call_ollama_cloud(prompt, cloud_model)
    except Exception as e:
        print(f"[analysis] first attempt failed ({e}), retrying with stricter prompt")
        retry_prompt = prompt + "\n\nCRITICAL: Output ONLY the JSON object starting with { and ending with }. No other text."
        result = _call_ollama_cloud(retry_prompt, cloud_model)

    # Normalise: accept {"shorts": [...]} or bare [...]
    if isinstance(result, dict) and "shorts" in result:
        segments = result["shorts"]
    elif isinstance(result, list):
        segments = result
    else:
        segments = []

    print(f"[analysis] model returned {len(segments)} segments")
    return segments


def _parse_duration_str(duration: str) -> float:
    """Parse 'HH:MM:SS' or float string to seconds."""
    if ":" in str(duration):
        return parse_timestamp(str(duration))
    return float(duration)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _parse_flexible_timestamp(val) -> float:
    """Accept float seconds, int, or HH:MM:SS string."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().strip('"\'')
    try:
        return parse_timestamp(s)
    except Exception:
        return float(s)


def validate_segments(segments: list, video_duration: float) -> list:
    """Validate, clamp, and de-overlap segments. Logs every rejection reason."""
    valid = []
    seen_ranges = []

    min_dur = max(15.0, MIN_CLIP_DURATION - 15)   # at least 15 s
    max_dur = MAX_CLIP_DURATION + 30               # allow up to 120 s

    for i, seg in enumerate(segments):
        try:
            start = _parse_flexible_timestamp(seg.get("start", seg.get("start_time", "")))
            end   = _parse_flexible_timestamp(seg.get("end",   seg.get("end_time",   "")))
        except Exception as exc:
            print(f"[validate] seg {i}: timestamp parse failed — {exc} | seg={seg}")
            continue

        if end <= start:
            print(f"[validate] seg {i}: end ({end:.1f}s) ≤ start ({start:.1f}s) — skipped")
            continue

        orig_start, orig_end = start, end
        start = max(0.0, start)
        end   = min(video_duration, end)
        if orig_start != start or orig_end != end:
            print(f"[validate] seg {i}: clamped {orig_start:.1f}–{orig_end:.1f} → {start:.1f}–{end:.1f}")

        duration = end - start
        if duration < min_dur:
            print(f"[validate] seg {i}: duration {duration:.1f}s < min {min_dur:.1f}s — skipped")
            continue
        if duration > max_dur:
            print(f"[validate] seg {i}: duration {duration:.1f}s > max {max_dur:.1f}s — truncated")
            end = start + max_dur
            duration = max_dur

        overlaps = False
        for s, e in seen_ranges:
            if not (end <= s or start >= e):
                overlaps = True
                print(f"[validate] seg {i}: overlaps [{s:.1f}–{e:.1f}] — skipped")
                break
        if overlaps:
            continue

        seen_ranges.append((start, end))
        valid.append({
            "clip_index": len(valid) + 1,
            "start": seconds_to_timestamp(start),
            "end":   seconds_to_timestamp(end),
            "start_seconds": start,
            "end_seconds":   end,
            "duration": duration,
            "virality_score": min(100, max(0, int(seg.get("virality_score", 50)))),
            "hook":                     seg.get("hook",                     ""),
            "reason":                   seg.get("reason",                   ""),
            "viral_hook_text":          seg.get("viral_hook_text",          ""),
            "tiktok_description":       seg.get("video_description_for_tiktok", ""),
            "instagram_description":    seg.get("video_description_for_instagram", ""),
            "youtube_title":            seg.get("video_title_for_youtube_short",  ""),
        })

    print(f"[validate] accepted {len(valid)}/{len(segments)} segments")
    return valid
