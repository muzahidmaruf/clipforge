import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db, Job, Clip, JobStatus
from models.schemas import (
    JobResponse, JobWithClipsResponse, ClipResponse, DeleteResponse, CleanedVideoInfo
)
from utils.file_utils import delete_job_files
from services.pipeline import process_video


def _cleaned_info(job: Job) -> CleanedVideoInfo:
    available = bool(job.cleaned_video_path and os.path.exists(job.cleaned_video_path))
    if not available:
        return CleanedVideoInfo(available=False)
    orig = job.original_duration
    cleaned = job.cleaned_duration
    return CleanedVideoInfo(
        available=True,
        original_duration=orig,
        cleaned_duration=cleaned,
        saved_seconds=(orig - cleaned) if (orig is not None and cleaned is not None) else None,
        fillers_removed=job.cleaned_fillers_removed,
    )

router = APIRouter(prefix="/api", tags=["jobs"])

@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    return [JobResponse(
        job_id=j.id,
        status=j.status,
        progress=j.progress,
        error_message=j.error_message,
        clips_count=j.clips_count,
        created_at=j.created_at,
        filename=j.filename,
        mode=j.mode,
        num_clips=j.num_clips,
    ) for j in jobs]

@router.get("/jobs/{job_id}", response_model=JobWithClipsResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    
    clips = db.query(Clip).filter(Clip.job_id == job_id).all()
    
    return JobWithClipsResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        clips_count=job.clips_count,
        created_at=job.created_at,
        filename=job.filename,
        mode=job.mode,
        num_clips=job.num_clips,
        cleaned=_cleaned_info(job),
        clips=[ClipResponse(
            id=c.id,
            clip_index=c.clip_index,
            filename=c.filename,
            start_time=c.start_time,
            end_time=c.end_time,
            duration=c.duration,
            virality_score=c.virality_score,
            hook=c.hook,
            reason=c.reason,
            file_size=c.file_size,
            created_at=c.created_at
        ) for c in clips]
    )

@router.get("/jobs/{job_id}/clips")
def get_job_clips(job_id: str, db: Session = Depends(get_db)):
    clips = db.query(Clip).filter(Clip.job_id == job_id).all()
    return [ClipResponse(
        id=c.id,
        clip_index=c.clip_index,
        filename=c.filename,
        start_time=c.start_time,
        end_time=c.end_time,
        duration=c.duration,
        virality_score=c.virality_score,
        hook=c.hook,
        reason=c.reason,
        file_size=c.file_size,
        created_at=c.created_at
    ) for c in clips]

@router.post("/jobs/{job_id}/resume", response_model=JobResponse)
def resume_job(job_id: str, db: Session = Depends(get_db)):
    """Re-queue the job. The pipeline will skip any stage that already has a
    checkpoint on disk (transcript, cleaned video, segments, individual clips)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job.status not in (JobStatus.FAILED, JobStatus.PENDING):
        raise HTTPException(400, detail="Job is already running or completed")
    if not job.video_path or not os.path.exists(job.video_path):
        raise HTTPException(400, detail="Original video file no longer exists")

    job.status        = JobStatus.PENDING
    job.error_message = None
    # Keep job.progress as-is so the UI shows where we left off until the
    # worker picks it up and starts updating again.
    db.commit()

    task = process_video.delay(job_id)
    job.celery_task_id = task.id
    db.commit()

    return JobResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        clips_count=job.clips_count,
        created_at=job.created_at,
        filename=job.filename,
        mode=job.mode,
        num_clips=job.num_clips,
    )


@router.post("/jobs/{job_id}/restart", response_model=JobResponse)
def restart_job(job_id: str, db: Session = Depends(get_db)):
    """Full restart from scratch — wipes all checkpoints and clips, then re-queues."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job.status not in (JobStatus.FAILED, JobStatus.PENDING):
        raise HTTPException(400, detail="Job is already running or completed")
    if not job.video_path or not os.path.exists(job.video_path):
        raise HTTPException(400, detail="Original video file no longer exists")

    # Wipe checkpoints from disk
    for attr in ("transcript_path", "segments_path", "cleaned_video_path"):
        path = getattr(job, attr, None)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    # Wipe clip files and DB rows
    existing_clips = db.query(Clip).filter(Clip.job_id == job_id).all()
    for c in existing_clips:
        if c.file_path and os.path.exists(c.file_path):
            try:
                os.remove(c.file_path)
            except OSError:
                pass
    db.query(Clip).filter(Clip.job_id == job_id).delete()

    # Reset job state
    job.status              = JobStatus.PENDING
    job.progress            = 0
    job.error_message       = None
    job.clips_count         = None
    job.transcript_path     = None
    job.segments_path       = None
    job.cleaned_video_path  = None
    job.cleaned_duration    = None
    job.original_duration   = None
    job.cleaned_fillers_removed = None
    db.commit()

    task = process_video.delay(job_id)
    job.celery_task_id = task.id
    db.commit()

    return JobResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        clips_count=job.clips_count,
        created_at=job.created_at,
        filename=job.filename,
        mode=job.mode,
        num_clips=job.num_clips,
    )


# Keep /retry as an alias for /resume so old calls still work
@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: str, db: Session = Depends(get_db)):
    return resume_job(job_id, db)

@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        raise HTTPException(400, detail="Job already finished")

    task_id = getattr(job, 'celery_task_id', None)
    if task_id:
        from services.pipeline import celery_app as _celery
        _celery.control.revoke(task_id, terminate=True, signal="SIGTERM")

    job.status = JobStatus.FAILED
    job.error_message = "Cancelled by user"
    job.progress = 0
    db.commit()

    return JobResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        clips_count=job.clips_count,
        created_at=job.created_at,
        filename=job.filename
    )

@router.delete("/jobs/{job_id}", response_model=DeleteResponse)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    
    delete_job_files(job_id)
    # Also blow away the cleaned video if one exists
    if job.cleaned_video_path and os.path.exists(job.cleaned_video_path):
        try:
            os.remove(job.cleaned_video_path)
        except OSError:
            pass
    db.query(Clip).filter(Clip.job_id == job_id).delete()
    db.delete(job)
    db.commit()

    return {"success": True}


@router.get("/jobs/{job_id}/cleaned/stream")
def stream_cleaned_video(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.cleaned_video_path or not os.path.exists(job.cleaned_video_path):
        raise HTTPException(404, detail="Cleaned video not available")
    return FileResponse(job.cleaned_video_path, media_type="video/mp4")


@router.get("/jobs/{job_id}/cleaned/download")
def download_cleaned_video(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.cleaned_video_path or not os.path.exists(job.cleaned_video_path):
        raise HTTPException(404, detail="Cleaned video not available")
    base = os.path.splitext(job.filename or "cleaned")[0]
    return FileResponse(
        job.cleaned_video_path,
        media_type="video/mp4",
        filename=f"{base}_cleaned.mp4",
    )
