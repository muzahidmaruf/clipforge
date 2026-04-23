import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import TRANSCRIPTS_DIR
from utils.time_utils import parse_timestamp

router = APIRouter(prefix="/api", tags=["clips"])


@router.get("/clips/{clip_id}/download")
def download_clip(clip_id: str):
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip or not os.path.exists(clip.file_path):
            raise HTTPException(404, detail="Clip not found")

        return FileResponse(
            clip.file_path,
            media_type="video/mp4",
            filename=clip.filename
        )
    finally:
        db.close()


@router.get("/clips/{clip_id}/stream")
def stream_clip(clip_id: str):
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip or not os.path.exists(clip.file_path):
            raise HTTPException(404, detail="Clip not found")

        return FileResponse(
            clip.file_path,
            media_type="video/mp4"
        )
    finally:
        db.close()


@router.get("/clips/{clip_id}/subtitles")
def get_clip_subtitles(clip_id: str):
    """
    Return word-level subtitles for a clip.
    Filters the job's full Whisper transcript to words within the clip's
    time range, then rebases timestamps to 0 (relative to clip start).
    """
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(404, detail="Clip not found")

        transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{clip.job_id}.json")
        if not os.path.exists(transcript_path):
            raise HTTPException(404, detail="Transcript not found")

        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = json.load(f)

        clip_start = parse_timestamp(clip.start_time)
        clip_end = parse_timestamp(clip.end_time)

        words = []
        for segment in transcript.get("segments", []):
            for w in segment.get("words", []):
                w_start = float(w["start"])
                w_end = float(w["end"])
                # Word overlaps the clip range
                if w_end >= clip_start and w_start <= clip_end:
                    rel_start = max(0.0, w_start - clip_start)
                    rel_end = max(rel_start, w_end - clip_start)
                    words.append({
                        "word": w["word"].strip(),
                        "start": round(rel_start, 3),
                        "end": round(rel_end, 3),
                    })

        return {
            "clip_id": clip_id,
            "duration": round(clip_end - clip_start, 3),
            "words": words,
        }
    finally:
        db.close()
