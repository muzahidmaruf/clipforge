import whisper
import os
import torch

WHISPER_MODELS = {"tiny", "base", "small", "medium", "large"}

# Whisper language codes — subset of commonly used ones.
# Full list: https://github.com/openai/whisper/blob/main/whisper/tokenizer.py
SUPPORTED_LANGUAGES = {
    "auto":  None,       # let Whisper detect (default)
    "en":    "english",
    "bn":    "bengali",  # Bangla
    "hi":    "hindi",
    "ur":    "urdu",
    "ar":    "arabic",
    "zh":    "chinese",
    "es":    "spanish",
    "fr":    "french",
    "de":    "german",
    "pt":    "portuguese",
    "ru":    "russian",
    "ja":    "japanese",
    "ko":    "korean",
    "tr":    "turkish",
    "it":    "italian",
}


def transcribe_video(video_path: str, job_id: str, model_name: str = "base", language: str = "auto") -> dict:
    """Transcribe video using OpenAI Whisper with word-level timestamps.

    Args:
        video_path:  Path to the video file.
        job_id:      Used for naming the saved transcript JSON.
        model_name:  Whisper model size (tiny/base/small/medium/large).
                     Use 'small' or above for non-English languages.
        language:    ISO 639-1 code (e.g. 'bn' for Bangla, 'en' for English).
                     'auto' lets Whisper detect — unreliable for Bangla/Hindi.
    """
    import time
    start_time = time.time()

    if model_name not in WHISPER_MODELS:
        model_name = "base"

    # Resolve language code → Whisper language string (or None for auto)
    lang_code = language.strip().lower() if language else "auto"
    whisper_lang = SUPPORTED_LANGUAGES.get(lang_code)  # None = auto-detect

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[transcription] loading model '{model_name}' on {device}...")
    model = whisper.load_model(model_name, device=device)
    print(f"[transcription] model loaded, starting transcription...")

    transcribe_kwargs = {
        "word_timestamps": True,
        "fp16": (device == "cuda"),
        "verbose": False,  # Suppress Whisper's built-in progress output
    }
    if whisper_lang is not None:
        # Explicit language speeds up detection and prevents misidentification
        transcribe_kwargs["language"] = whisper_lang
        print(f"[transcription] language forced to '{whisper_lang}' ({lang_code})")
    else:
        print("[transcription] language auto-detect enabled")

    # Log progress periodically during transcription
    print(f"[transcription] video: {video_path}, duration: {get_video_duration(video_path):.1f}s")

    result = model.transcribe(video_path, **transcribe_kwargs)
    elapsed = time.time() - start_time
    print(f"[transcription] completed in {elapsed:.1f}s, detected language: {result.get('language', 'unknown')}")

    # Save transcript
    from config import TRANSCRIPTS_DIR
    import json
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{job_id}.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)  # ensure_ascii=False preserves Unicode (Bangla script)

    print(f"[transcription] saved to {transcript_path}")
    return result


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    import subprocess
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[transcription] warning: could not get video duration: {e}")
        return 0.0

def format_transcript(transcript_result: dict) -> str:
    """Format transcript as timestamped text for Gemma"""
    lines = []
    for segment in transcript_result.get("segments", []):
        start = segment["start"]
        hours = int(start // 3600)
        minutes = int((start % 3600) // 60)
        seconds = start % 60
        timestamp = f"[{hours:02d}:{minutes:02d}:{seconds:06.3f}]"
        text = segment["text"].strip()
        lines.append(f"{timestamp} {text}")
    return "\n".join(lines)
