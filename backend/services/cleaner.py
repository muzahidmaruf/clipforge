"""
Silent-cut / filler-removal service.

Takes the original long video + the word-level Whisper transcript and produces
a single cleaned video with filler words ("um", "uh", "like", etc.) and long
silent gaps removed.

Strategy:
  1. Walk the word list. Drop words that match the filler set.
  2. For the words that remain, build "keep" time ranges. Between consecutive
     kept words, if the gap is longer than MAX_GAP, collapse it to KEEP_GAP
     (a tiny breathing room so speech doesn't sound spliced).
  3. Merge adjacent keep ranges, then render via ffmpeg filter_complex:
     one trim+atrim per range → concat filter → single output file.

The cleaned file is written to storage/cleaned/{job_id}.mp4 and streamed back
via the /api/jobs/{id}/cleaned endpoints.
"""

import os
import re
import subprocess
import tempfile
from typing import List, Tuple

from config import FFMPEG_PATH, STORAGE_DIR

CLEANED_DIR = os.path.join(STORAGE_DIR, "cleaned")
os.makedirs(CLEANED_DIR, exist_ok=True)

# Single-word fillers (matched after stripping punctuation + lowercasing)
FILLER_WORDS = {
    "um", "umm", "uh", "uhh", "uhm", "er", "err", "erm",
    "ah", "ahh", "eh", "hmm", "hm", "mm", "mmm", "mhm",
    "like",  # conservative: only strip when surrounded by other speech
    "basically", "literally", "actually", "honestly",
    "right", "okay", "ok",
    "anyway", "anyways",
}
# Multi-word filler phrases (matched on the normalized word stream)
FILLER_PHRASES = [
    ("you", "know"),
    ("i", "mean"),
    ("kind", "of"),
    ("sort", "of"),
    ("you", "see"),
]

# Silence / gap handling (seconds)
MAX_GAP = 0.45        # if gap between kept words is longer than this...
KEEP_GAP = 0.15       # ...collapse it to this (breath room)
EDGE_PAD = 0.06       # pad each kept range this much on both sides
MIN_RANGE = 0.08      # drop ranges shorter than this (noise)


def _normalize(word: str) -> str:
    return re.sub(r"[^\w']", "", (word or "").lower()).strip()


def _extract_words(transcript_result: dict) -> List[dict]:
    """Flatten Whisper segments into a single list of word dicts with start/end."""
    out = []
    for seg in transcript_result.get("segments", []):
        for w in seg.get("words", []) or []:
            if "start" not in w or "end" not in w:
                continue
            start = float(w["start"])
            end = float(w["end"])
            if end <= start:
                continue
            out.append({
                "word": w.get("word", "").strip(),
                "start": start,
                "end": end,
                "norm": _normalize(w.get("word", "")),
            })
    out.sort(key=lambda x: x["start"])
    return out


def _mark_fillers(words: List[dict]) -> List[bool]:
    """Return a parallel list where True = this word should be dropped."""
    n = len(words)
    drop = [False] * n

    # Multi-word phrases first (greedy, non-overlapping)
    for phrase in FILLER_PHRASES:
        L = len(phrase)
        i = 0
        while i <= n - L:
            if all(words[i + k]["norm"] == phrase[k] for k in range(L)):
                for k in range(L):
                    drop[i + k] = True
                i += L
            else:
                i += 1

    # Single-word fillers — require the word to be standalone (i.e. short
    # utterance), not embedded in a meaningful clause. For "like" specifically
    # we only drop when it's sandwiched between non-fillers on both sides (i.e.
    # a disfluency, not the verb "like").
    for i, w in enumerate(words):
        if drop[i]:
            continue
        norm = w["norm"]
        if norm in FILLER_WORDS:
            if norm == "like":
                # Drop "like" only if it's a standalone disfluency:
                # flanked by a pause on at least one side, OR repeated.
                prev_gap = w["start"] - words[i - 1]["end"] if i > 0 else 1.0
                next_gap = words[i + 1]["start"] - w["end"] if i + 1 < n else 1.0
                if prev_gap < 0.15 and next_gap < 0.15:
                    continue  # likely real "I like pizza" verb
            drop[i] = True

    return drop


def _build_keep_ranges(
    words: List[dict],
    drop: List[bool],
    video_duration: float,
) -> List[Tuple[float, float]]:
    """Build merged keep-ranges from non-dropped words, collapsing long gaps."""
    ranges: List[Tuple[float, float]] = []
    for w, d in zip(words, drop):
        if d:
            continue
        s = max(0.0, w["start"] - EDGE_PAD)
        e = min(video_duration, w["end"] + EDGE_PAD)
        if ranges and s - ranges[-1][1] <= MAX_GAP:
            # Within allowable gap — merge (keeps the natural pause)
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], e))
        else:
            # Gap is too long — close the previous range cleanly and start new.
            # Collapse by inserting a KEEP_GAP-sized buffer *inside* the new range
            # start so the cut doesn't feel abrupt.
            if ranges:
                # Extend previous range by KEEP_GAP if room (breath room)
                prev_s, prev_e = ranges[-1]
                ranges[-1] = (prev_s, min(prev_e + KEEP_GAP, s))
            ranges.append((s, e))

    # Drop noise-short ranges
    return [(s, e) for (s, e) in ranges if (e - s) >= MIN_RANGE]


def _render_concat(input_path: str, ranges: List[Tuple[float, float]], output_path: str) -> None:
    """Render the kept ranges into a single MP4 via ffmpeg filter_complex."""
    if not ranges:
        raise ValueError("No content to keep after filler/pause removal")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Build filter_complex: trim/atrim each range, concat video+audio streams.
    parts = []
    for i, (s, e) in enumerate(ranges):
        parts.append(
            f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )
    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(ranges)))
    filter_complex = ";".join(parts) + f";{concat_inputs}concat=n={len(ranges)}:v=1:a=1[outv][outa]"

    # filter_complex can get very long; write to a script file for ffmpeg -/
    # (some ffmpeg builds cap argv length). Use a temp file.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(filter_complex)
        script_path = fh.name

    try:
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-filter_complex_script", script_path,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "22",
            "-movflags", "+faststart",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg cleaner error: {result.stderr[-1500:]}"
            )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def clean_video(
    job_id: str,
    input_path: str,
    transcript_result: dict,
    video_duration: float,
) -> dict:
    """
    High-level entry point. Runs the whole pipeline and returns a stats dict.

    Returns:
      {
        "output_path": str,
        "original_duration": float,
        "cleaned_duration": float,
        "saved_seconds": float,
        "filler_words_removed": int,
        "segments": int,
      }
    """
    words = _extract_words(transcript_result)
    if not words:
        raise ValueError("Transcript has no word-level timestamps; re-run transcription")

    drop = _mark_fillers(words)
    fillers_removed = sum(1 for d in drop if d)

    ranges = _build_keep_ranges(words, drop, video_duration)
    if not ranges:
        raise ValueError("Nothing to keep — transcript produced no usable ranges")

    output_path = os.path.join(CLEANED_DIR, f"{job_id}.mp4")
    _render_concat(input_path, ranges, output_path)

    cleaned_duration = sum(e - s for s, e in ranges)
    return {
        "output_path": output_path,
        "original_duration": video_duration,
        "cleaned_duration": cleaned_duration,
        "saved_seconds": max(0.0, video_duration - cleaned_duration),
        "filler_words_removed": fillers_removed,
        "segments": len(ranges),
    }
