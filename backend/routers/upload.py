import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Job, JobStatus
from config import UPLOADS_DIR, MAX_VIDEO_SIZE_MB, MAX_VIDEO_DURATION_MINUTES, ALLOWED_EXTENSIONS
from services.pipeline import process_video
from services.video_processor import get_video_duration
from services.supabase_auth import require_user, AuthUser

router = APIRouter(prefix="/api", tags=["upload"])

CHUNK_SIZE = 1024 * 1024  # 1 MB


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    whisper_model: str = Form("base"),
    whisper_language: str = Form("auto"),
    ai_model: str = Form("qwen3.5:32b-cloud"),
    mode: str = Form("clips"),
    num_clips: int = Form(5),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail=f"Invalid file type. Allowed: {ALLOWED_EXTENSIONS}")

    # Validate whisper model — allow plain sizes and "-fast" variants
    valid_whisper = {"tiny", "base", "small", "medium", "large",
                     "tiny-fast", "base-fast", "small-fast", "medium-fast", "large-fast"}
    if whisper_model not in valid_whisper:
        whisper_model = "base"  # safe fallback

    # Validate whisper language (accept anything — Whisper will error at runtime for unknown codes)
    from services.transcription import SUPPORTED_LANGUAGES
    whisper_language = (whisper_language or "auto").strip().lower()
    if whisper_language not in SUPPORTED_LANGUAGES:
        whisper_language = "auto"  # fall back gracefully

    # Validate mode & clip count
    mode = (mode or "clips").lower()
    if mode not in {"clips", "clean", "both"}:
        raise HTTPException(400, detail="mode must be one of: clips, clean, both")
    try:
        num_clips = max(1, min(15, int(num_clips)))
    except (TypeError, ValueError):
        num_clips = 5

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
        user_id=user.id,
        filename=file.filename,
        status=JobStatus.PENDING,
        video_path=file_path,
        whisper_model=whisper_model,
        whisper_language=whisper_language,
        ai_model=ai_model,
        mode=mode,
        num_clips=num_clips,
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


# ---------------------------------------------------------------------------
# YouTube import
# ---------------------------------------------------------------------------

class YouTubeImportRequest(BaseModel):
    url: str
    whisper_model: str = "base"
    whisper_language: str = "auto"
    ai_model: str = "qwen3.5:32b-cloud"
    mode: str = "clips"
    num_clips: int = 5


@router.post("/import-youtube")
async def import_youtube(
    body: YouTubeImportRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """Download a YouTube video with yt-dlp and start processing."""
    from services.youtube import download_youtube
    from services.transcription import SUPPORTED_LANGUAGES

    # Basic URL check
    url = body.url.strip()
    if not url.startswith("http"):
        raise HTTPException(400, detail="Invalid URL")

    # Validate params
    valid_whisper = {"tiny", "base", "small", "medium", "large",
                     "tiny-fast", "base-fast", "small-fast", "medium-fast", "large-fast"}
    whisper_model = body.whisper_model if body.whisper_model in valid_whisper else "base"
    whisper_language = (body.whisper_language or "auto").strip().lower()
    if whisper_language not in SUPPORTED_LANGUAGES:
        whisper_language = "auto"
    mode = (body.mode or "clips").lower()
    if mode not in {"clips", "clean", "both"}:
        mode = "clips"
    num_clips = max(1, min(15, int(body.num_clips or 5)))

    job_id = str(uuid.uuid4())
    try:
        info = download_youtube(url, job_id=job_id)
    except Exception as e:
        raise HTTPException(400, detail=f"YouTube download failed: {e}")

    # Duration check
    if info["duration"] and info["duration"] > MAX_VIDEO_DURATION_MINUTES * 60:
        try:
            os.remove(info["file_path"])
        except OSError:
            pass
        raise HTTPException(400, detail=f"Video too long. Max: {MAX_VIDEO_DURATION_MINUTES} minutes")

    job = Job(
        id=job_id,
        user_id=user.id,
        filename=info["filename"],
        status=JobStatus.PENDING,
        video_path=info["file_path"],
        whisper_model=whisper_model,
        whisper_language=whisper_language,
        ai_model=body.ai_model or "qwen3.5:32b-cloud",
        mode=mode,
        num_clips=num_clips,
    )
    db.add(job)
    db.commit()

    task = process_video.delay(job_id)
    job.celery_task_id = task.id
    db.commit()

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"YouTube video '{info['title']}' downloaded and processing started",
        "title": info["title"],
        "duration": info["duration"],
    }
