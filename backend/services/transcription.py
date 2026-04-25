"""
Transcription service — supports two backends:

  openai-whisper  (default)  — original PyTorch model, GPU-accelerated when available
  faster-whisper  (optional) — CTranslate2-based INT8 model, 3-5× faster on CPU

Backend selection: pass model_name with a "-fast" suffix, e.g. "base-fast", "small-fast".
The "-fast" suffix is stripped before loading the model so valid sizes are the same.
"""

import os
import json
import time

WHISPER_MODELS = {"tiny", "base", "small", "medium", "large"}

# ISO 639-1 → Whisper language string (None = auto-detect)
SUPPORTED_LANGUAGES = {
    "auto": None,
    "en":   "english",
    "bn":   "bengali",
    "hi":   "hindi",
    "ur":   "urdu",
    "ar":   "arabic",
    "zh":   "chinese",
    "es":   "spanish",
    "fr":   "french",
    "de":   "german",
    "pt":   "portuguese",
    "ru":   "russian",
    "ja":   "japanese",
    "ko":   "korean",
    "tr":   "turkish",
    "it":   "italian",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_model_name(model_name: str) -> tuple[str, bool]:
    """Return (clean_model_size, use_faster_whisper)."""
    name = (model_name or "base").strip().lower()
    use_fast = name.endswith("-fast")
    size = name.removesuffix("-fast")
    if size not in WHISPER_MODELS:
        size = "base"
    return size, use_fast


def _normalize_faster_whisper(segments_gen, info) -> dict:
    """Convert faster-whisper output (generators) to openai-whisper dict format."""
    segments_list = []
    for seg in segments_gen:
        seg_dict = {
            "id":    len(segments_list),
            "start": seg.start,
            "end":   seg.end,
            "text":  seg.text,
            "words": [],
        }
        if seg.words:
            for w in seg.words:
                seg_dict["words"].append({
                    "word":  w.word.strip(),
                    "start": w.start,
                    "end":   w.end,
                    "probability": getattr(w, "probability", 1.0),
                })
        segments_list.append(seg_dict)

    return {
        "text":     " ".join(s["text"].strip() for s in segments_list),
        "segments": segments_list,
        "language": info.language,
    }


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

def _transcribe_openai(video_path: str, model_size: str, whisper_lang) -> dict:
    """Transcribe using openai-whisper (PyTorch)."""
    import torch
    import whisper

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[transcription/openai] loading '{model_size}' on {device} …")
    model = whisper.load_model(model_size, device=device)

    kwargs = {
        "word_timestamps": True,
        "fp16": (device == "cuda"),
        "verbose": False,
    }
    if whisper_lang is not None:
        kwargs["language"] = whisper_lang

    result = model.transcribe(video_path, **kwargs)
    return result


def _transcribe_faster(video_path: str, model_size: str, whisper_lang) -> dict:
    """Transcribe using faster-whisper (CTranslate2 INT8)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper is not installed. "
            "Run: pip install faster-whisper"
        )

    import torch
    device      = "cuda" if torch.cuda.is_available() else "cpu"
    compute     = "float16" if device == "cuda" else "int8"
    print(f"[transcription/faster] loading '{model_size}' on {device} ({compute}) …")
    model = WhisperModel(model_size, device=device, compute_type=compute)

    kwargs: dict = {"word_timestamps": True}
    if whisper_lang is not None:
        kwargs["language"] = whisper_lang

    segments, info = model.transcribe(video_path, **kwargs)
    return _normalize_faster_whisper(segments, info)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_video(
    video_path: str,
    job_id: str,
    model_name: str = "base",
    language: str = "auto",
) -> dict:
    """Transcribe *video_path* and save the result JSON.

    model_name examples
    -------------------
    "base"        → openai-whisper, base model
    "small"       → openai-whisper, small model
    "base-fast"   → faster-whisper INT8, base model  (3-5× faster on CPU)
    "small-fast"  → faster-whisper INT8, small model
    """
    t0 = time.time()

    model_size, use_fast = _parse_model_name(model_name)
    lang_code   = (language or "auto").strip().lower()
    whisper_lang = SUPPORTED_LANGUAGES.get(lang_code)  # None = auto-detect

    backend_label = "faster-whisper INT8" if use_fast else "openai-whisper"
    print(f"[transcription] backend={backend_label}  model={model_size}  lang={lang_code}")
    if whisper_lang:
        print(f"[transcription] language forced → '{whisper_lang}'")
    else:
        print("[transcription] language auto-detect")

    if use_fast:
        result = _transcribe_faster(video_path, model_size, whisper_lang)
    else:
        result = _transcribe_openai(video_path, model_size, whisper_lang)

    elapsed = time.time() - t0
    print(f"[transcription] done in {elapsed:.1f}s  detected={result.get('language','?')}")

    # Save transcript JSON (ensure_ascii=False preserves Bangla/CJK script)
    from config import TRANSCRIPTS_DIR
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{job_id}.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[transcription] saved → {transcript_path}")
    return result


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    import subprocess
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[transcription] warning: could not get video duration: {e}")
        return 0.0


def format_transcript(transcript_result: dict) -> str:
    """Format transcript as timestamped text for the AI prompt."""
    lines = []
    for segment in transcript_result.get("segments", []):
        start = segment["start"]
        hours   = int(start // 3600)
        minutes = int((start % 3600) // 60)
        secs    = start % 60
        timestamp = f"[{hours:02d}:{minutes:02d}:{secs:06.3f}]"
        lines.append(f"{timestamp} {segment['text'].strip()}")
    return "\n".join(lines)
