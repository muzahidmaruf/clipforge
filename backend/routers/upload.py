import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session

from database import get_db, Job, JobStatus
from config import UPLOADS_DIR, MAX_VIDEO_SIZE_MB, MAX_VIDEO_DURATION_MINUTES, ALLOWED_EXTENSIONS
from services.pipeline import process_video
from services.video_processor import get_video_duration

router = APIRouter(prefix="/api", tags=["upload"])

CHUNK_SIZE = 1024 * 1024  # 1 MB


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    whisper_model: str = Form("base"),
    ai_model: str = Form("gemma4:31b-cloud"),
    db: Session = Depends(get_db)
):
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail=f"Invalid file type. Allowed: {ALLOWED_EXTENSIONS}")

    # Validate whisper model
    valid_whisper = {"tiny", "base", "small", "medium", "large"}
    if whisper_model not in valid_whisper:
        raise HTTPException(400, detail=f"Invalid whisper model. Allowed: {valid_whisper}")

    # Stream file to disk chunk-by-chunk (avoids loading entire video into RAM)
    job_id = str(uuid.uuid4())
    filename = f"{job_id}_{file.filename}"
    file_path = os.path.join(UPLOADS_DIR, filename)

    try:
        size_bytes = 0
        max_bytes = MAX_VIDEO_SIZE_MB * 1024 * 1024
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(400, detail=f"File too large. Max: {MAX_VIDEO_SIZE_MB}MB")
                f.write(chunk)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(500, detail=f"Failed to save file: {e}")

    # Validate duration
    try:
        duration = get_video_duration(file_path)
        if duration > MAX_VIDEO_DURATION_MINUTES * 60:
            os.remove(file_path)
            raise HTTPException(400, detail=f"Video too long. Max: {MAX_VIDEO_DURATION_MINUTES} minutes")
    except HTTPException:
        raise
    except Exception:
        pass  # duration check is best-effort

    # Create job only after file is confirmed on disk
    job = Job(
        id=job_id,
        filename=file.filename,
        status=JobStatus.PENDING,
        video_path=file_path,
        whisper_model=whisper_model,
        ai_model=ai_model
    )
    db.add(job)
    db.commit()

    task = process_video.delay(job_id)
    job.celery_task_id = task.id
    db.commit()

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Video uploaded and processing started"
    }
