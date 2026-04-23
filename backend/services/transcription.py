import whisper
import os

WHISPER_MODELS = {"tiny", "base", "small", "medium", "large"}

def transcribe_video(video_path: str, job_id: str, model_name: str = "base") -> dict:
    """Transcribe video using OpenAI Whisper with word-level timestamps"""
    if model_name not in WHISPER_MODELS:
        model_name = "base"
    
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisper.load_model(model_name, device=device)
    result = model.transcribe(video_path, word_timestamps=True, fp16=(device == "cuda"))
    
    # Save transcript
    from config import TRANSCRIPTS_DIR
    import json
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{job_id}.json")
    with open(transcript_path, "w") as f:
        json.dump(result, f, indent=2)
    
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
