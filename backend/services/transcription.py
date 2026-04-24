import whisper
import os

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
    if model_name not in WHISPER_MODELS:
        model_name = "base"

    # Resolve language code → Whisper language string (or None for auto)
    lang_code = language.strip().lower() if language else "auto"
    whisper_lang = SUPPORTED_LANGUAGES.get(lang_code)  # None = auto-detect

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model(model_name, device=device)

    transcribe_kwargs = {
        "word_timestamps": True,
        "fp16": (device == "cuda"),
    }
    if whisper_lang is not None:
        # Explicit language speeds up detection and prevents misidentification
        transcribe_kwargs["language"] = whisper_lang
        print(f"[transcription] language forced to '{whisper_lang}' ({lang_code})")
    else:
        print("[transcription] language auto-detect enabled")

    result = model.transcribe(video_path, **transcribe_kwargs)
    print(f"[transcription] detected/used language: {result.get('language', 'unknown')}")

    # Save transcript
    from config import TRANSCRIPTS_DIR
    import json
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{job_id}.json")
    with open(transcript_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)  # ensure_ascii=False preserves Unicode (Bangla script)

    return result

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
