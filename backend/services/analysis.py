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


def _call_ollama_cloud(prompt: str, model_name: str):
    """Call Ollama Cloud API (https://ollama.com/api/*)."""
    if not OLLAMA_CLOUD_API_KEY:
        raise RuntimeError("OLLAMA_CLOUD_API_KEY not set — get one at https://ollama.com/settings/keys")

    url = f"{OLLAMA_CLOUD_BASE_URL}/api/generate"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}"},
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 2000
            }
        },
        timeout=OLLAMA_CLOUD_TIMEOUT
    )
    response.raise_for_status()
    raw = response.json()["response"].strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def analyze_transcript(transcript: str, duration: str, model_name: str = None, num_clips: int = 5):
    """Analyze transcript using Ollama Cloud API."""
    try:
        num_clips = max(1, min(15, int(num_clips)))
    except (TypeError, ValueError):
        num_clips = 5
    prompt = GEMMA_PROMPT.format(transcript=transcript, duration=duration, num_clips=num_clips)

    cloud_model = model_name or OLLAMA_CLOUD_MODEL

    try:
        segments = _call_ollama_cloud(prompt, cloud_model)
    except json.JSONDecodeError:
        # Retry once with stricter prompt
        retry_prompt = prompt + "\n\nIMPORTANT: Respond with ONLY a valid JSON array. No other text."
        segments = _call_ollama_cloud(retry_prompt, cloud_model)

    return segments


def validate_segments(segments: list, video_duration: float) -> list:
    """Validate and clamp segment timestamps."""
    valid = []
    seen_ranges = []

    for seg in segments:
        try:
            start = parse_timestamp(seg["start"])
            end = parse_timestamp(seg["end"])

            if end <= start:
                continue
            if start < 0 or end > video_duration:
                start = max(0, start)
                end = min(video_duration, end)

            duration = end - start
            if duration < MIN_CLIP_DURATION or duration > MAX_CLIP_DURATION:
                continue

            overlaps = False
            for s, e in seen_ranges:
                if not (end <= s or start >= e):
                    overlaps = True
                    break
            if overlaps:
                continue

            seen_ranges.append((start, end))
            valid.append({
                "clip_index": len(valid) + 1,
                "start": seg["start"],
                "end": seg["end"],
                "start_seconds": start,
                "end_seconds": end,
                "duration": duration,
                "virality_score": min(100, max(0, int(seg.get("virality_score", 50)))),
                "hook": seg.get("hook", ""),
                "reason": seg.get("reason", "")
            })
        except (KeyError, ValueError):
            continue

    return valid
