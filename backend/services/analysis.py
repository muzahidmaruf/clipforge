import requests
import json
import re
from config import (
    OLLAMA_CLOUD_BASE_URL,
    OLLAMA_CLOUD_API_KEY,
    OLLAMA_CLOUD_MODEL,
    OLLAMA_CLOUD_TIMEOUT,
    MIN_CLIP_DURATION,
    MAX_CLIP_DURATION
)
from utils.time_utils import parse_timestamp

GEMMA_PROMPT = """You are a top-tier short-form video editor who has produced thousands of viral clips for TikTok, YouTube Shorts, and Instagram Reels. You understand what makes people STOP scrolling.

Below is a timestamped transcript from a long-form video. Your job is to identify **exactly {num_clips} standalone clips** (or as close to that number as the source material supports — never invent weak clips to hit the count) — not just chunks, but genuinely meaningful, self-contained stories, arguments, or insights that work without watching the rest of the video.

---

CRITICAL SELECTION CRITERIA (each clip MUST satisfy ALL):

1. **COMPLETE THOUGHT**: The clip must contain a complete idea with a clear beginning, middle, and end. A viewer who drops in cold must understand what is being said. Do NOT cut in the middle of an explanation, example, story, or argument.

2. **NATURAL BOUNDARIES**: Start AT the beginning of the first full sentence of the thought. End AFTER the last full sentence of that thought. Use the transcript's sentence punctuation and pause timing to find these boundaries. Never cut mid-sentence, mid-word, or mid-question.

3. **STRONG OPENING HOOK**: The first sentence must grab attention on its own — a bold claim, a surprising statistic, a provocative question, a vivid story moment, a promise of payoff. If the first sentence only makes sense because of what came before in the full video, do NOT select that starting point.

4. **SATISFYING PAYOFF**: The clip must deliver value or emotion by its ending — the surprise is revealed, the question is answered, the story lands, the advice is given. Do not end on a cliffhanger that the rest of the video answers.

5. **NO FLUFF**: Skip introductions, outros, sponsor reads, "before we start" disclaimers, "like and subscribe" asides, and transitional filler ("so, anyway..."). Jump into substance.

6. **NO OVERLAPS**: Clips must NOT overlap each other by even one second. Each must cover a distinct portion of the video.

7. **DURATION**: Minimum 30 seconds, maximum 90 seconds. Aim for 45-75s — long enough to build context and deliver payoff, short enough to stay on a Reel.

---

WHAT MAKES A CLIP VIRAL (prioritize segments with these):
- A counterintuitive or taboo opinion stated with conviction
- A specific, concrete story with emotional stakes
- A surprising fact, statistic, or reveal
- Actionable advice the viewer can use right away
- An insider secret, industry truth, or "they don't want you to know"
- Raw emotion: laughter, anger, vulnerability, genuine surprise
- A peak moment in a story arc (the twist, the climax, the lesson)

---

TRANSCRIPT:
{transcript}

VIDEO DURATION: {duration}

---

Output requirements:
- Respond with ONLY a valid JSON array. No prose, no markdown fences, no explanation.
- `start` and `end` must be timestamps from the transcript in HH:MM:SS format, aligned to sentence boundaries.
- `hook` must be a direct quote of the first full sentence of the clip (exactly as it appears in the transcript).
- `reason` must explain in ONE sentence why this specific clip is self-contained and compelling.
- `virality_score` must be an integer 0-100 reflecting genuine share potential.
- Sort clips by `virality_score` descending.

Example output format:

[
  {{
    "clip_index": 1,
    "start": "00:02:14",
    "end": "00:03:28",
    "virality_score": 92,
    "hook": "Most people don't realize that the brain makes up 80% of its decisions before you're even aware of them.",
    "reason": "Opens with a surprising stat, explains the mechanism with a concrete example, and lands on actionable advice — complete arc in 74 seconds."
  }}
]"""


def _extract_json_array(raw: str) -> list:
    """Robustly extract a JSON array from a model response that may include
    preamble text, markdown fences, or trailing commentary."""
    # 1. Strip markdown code fences (``` or ```json)
    if "```" in raw:
        parts = raw.split("```")
        # Take the first fenced block
        for i, part in enumerate(parts):
            if i % 2 == 1:  # inside a fence
                chunk = part.lstrip("json").lstrip("JSON").strip()
                if chunk.startswith("["):
                    raw = chunk
                    break

    raw = raw.strip()

    # 2. Try direct parse first
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # 3. Find the JSON array anywhere in the response (handles preamble text)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 4. Last resort: try to parse the whole thing
    return json.loads(raw)


def _call_ollama_cloud(prompt: str, model_name: str):
    """Call Ollama Cloud API.

    Ollama Cloud supports two API formats:
    1. OpenAI-compatible: POST /v1/chat/completions (with Bearer token)
    2. Native Ollama:    POST /api/generate (with API key header)

    We try OpenAI-compatible first, then fall back to native format.
    """
    if not OLLAMA_CLOUD_API_KEY:
        raise RuntimeError("OLLAMA_CLOUD_API_KEY not set — get one at https://ollama.com/settings/keys")

    # Try OpenAI-compatible endpoint first (preferred)
    url = f"{OLLAMA_CLOUD_BASE_URL}/v1/chat/completions"

    # Build request body with parameters that Qwen 3.5 Cloud supports
    request_body = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.3,
        "max_completion_tokens": 2000,
    }

    print(f"[analysis] calling Ollama Cloud at {url} with model={model_name}")

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=OLLAMA_CLOUD_TIMEOUT,
        )

        # If we get 404 on OpenAI endpoint, try native Ollama format
        if response.status_code == 404:
            print(f"[analysis] OpenAI endpoint returned 404, trying native Ollama format...")
            return _call_ollama_native(prompt, model_name)

        response.raise_for_status()
        response_data = response.json()

        if "choices" not in response_data or len(response_data["choices"]) == 0:
            print(f"[analysis] unexpected API response structure: {response_data}")
            raise RuntimeError("API returned empty or invalid response")

        raw = response_data["choices"][0]["message"]["content"].strip()
        print(f"[analysis] raw model response (first 500 chars): {raw[:500]}")
        return _extract_json_array(raw)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Try native format
            print(f"[analysis] OpenAI endpoint returned 404, trying native Ollama format...")
            return _call_ollama_native(prompt, model_name)
        # Log the full error response for debugging
        try:
            error_body = e.response.json() if e.response else {}
        except:
            error_body = {"raw": e.response.text if e.response else str(e)}
        print(f"[analysis] HTTP error {e.response.status_code}: {error_body}")
        raise RuntimeError(f"API error {e.response.status_code}: {error_body}")
    except requests.exceptions.Timeout:
        print(f"[analysis] request timed out after {OLLAMA_CLOUD_TIMEOUT}s")
        raise RuntimeError(f"Request timed out after {OLLAMA_CLOUD_TIMEOUT}s")
    except Exception as e:
        print(f"[analysis] unexpected error: {type(e).__name__}: {e}")
        raise


def _call_ollama_native(prompt: str, model_name: str):
    """Call Ollama Cloud using native /api/generate endpoint.

    This is the fallback for when the OpenAI-compatible endpoint doesn't work.
    """
    url = f"{OLLAMA_CLOUD_BASE_URL}/api/generate"

    request_body = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 2000,
        }
    }

    print(f"[analysis] calling native Ollama at {url} with model={model_name}")

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}",
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=OLLAMA_CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    response_data = response.json()

    # Native format returns 'response' field instead of 'choices[0].message.content'
    raw = response_data.get("response", "").strip()
    print(f"[analysis] raw model response (first 500 chars): {raw[:500]}")
    return _extract_json_array(raw)


def analyze_transcript(transcript: str, duration: str, model_name: str = None, num_clips: int = 5):
    """Analyze transcript using Ollama Cloud API."""
    try:
        num_clips = max(1, min(15, int(num_clips)))
    except (TypeError, ValueError):
        num_clips = 5
    prompt = GEMMA_PROMPT.format(transcript=transcript, duration=duration, num_clips=num_clips)

    cloud_model = model_name or OLLAMA_CLOUD_MODEL
    print(f"[analysis] calling model={cloud_model} num_clips={num_clips}")

    try:
        segments = _call_ollama_cloud(prompt, cloud_model)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[analysis] first attempt failed ({e}), retrying with stricter prompt")
        retry_prompt = prompt + "\n\nCRITICAL: Your response MUST start with [ and end with ]. Output ONLY the JSON array, nothing else."
        segments = _call_ollama_cloud(retry_prompt, cloud_model)

    print(f"[analysis] model returned {len(segments) if isinstance(segments, list) else 'non-list'} segments")
    return segments


def _parse_flexible_timestamp(val) -> float:
    """Parse a timestamp that may be HH:MM:SS, MM:SS, or a raw number (seconds)."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Remove surrounding quotes just in case
    s = s.strip('"\'')
    try:
        return parse_timestamp(s)
    except Exception:
        # Last resort: try float
        return float(s)


def validate_segments(segments: list, video_duration: float) -> list:
    """Validate and clamp segment timestamps. Logs reasons for rejection."""
    valid = []
    seen_ranges = []

    # Use a slightly relaxed minimum so models that pick 25-29s clips aren't
    # silently dropped — we still enforce a floor of 15s.
    min_dur = max(15.0, MIN_CLIP_DURATION - 10)
    max_dur = MAX_CLIP_DURATION + 30  # allow up to 120s; trim later if needed

    for i, seg in enumerate(segments):
        try:
            start = _parse_flexible_timestamp(seg.get("start", seg.get("start_time", "")))
            end   = _parse_flexible_timestamp(seg.get("end",   seg.get("end_time",   "")))
        except Exception as exc:
            print(f"[validate] seg {i}: timestamp parse failed — {exc} | seg={seg}")
            continue

        if end <= start:
            print(f"[validate] seg {i}: end ({end:.1f}s) <= start ({start:.1f}s) — skipped")
            continue

        # Clamp to video bounds
        orig_start, orig_end = start, end
        start = max(0.0, start)
        end   = min(video_duration, end)

        if orig_start != start or orig_end != end:
            print(f"[validate] seg {i}: clamped {orig_start:.1f}-{orig_end:.1f} → {start:.1f}-{end:.1f}")

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
                print(f"[validate] seg {i}: overlaps existing [{s:.1f}-{e:.1f}] — skipped")
                break
        if overlaps:
            continue

        # Normalise start/end to HH:MM:SS strings
        from utils.time_utils import seconds_to_timestamp
        seen_ranges.append((start, end))
        valid.append({
            "clip_index": len(valid) + 1,
            "start": seconds_to_timestamp(start),
            "end":   seconds_to_timestamp(end),
            "start_seconds": start,
            "end_seconds":   end,
            "duration": duration,
            "virality_score": min(100, max(0, int(seg.get("virality_score", 50)))),
            "hook":   seg.get("hook",   ""),
            "reason": seg.get("reason", ""),
        })

    print(f"[validate] accepted {len(valid)}/{len(segments)} segments")
    return valid
