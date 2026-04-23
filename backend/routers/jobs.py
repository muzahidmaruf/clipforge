import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Job, Clip, JobStatus
from models.schemas import JobResponse, JobWithClipsResponse, ClipResponse, DeleteResponse
from utils.file_utils import delete_job_files
from services.pipeline import process_video

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
        filename=j.filename
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

@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    if not job.video_path or not os.path.exists(job.video_path):
        raise HTTPException(400, detail="Original video file no longer exists, cannot retry")

    db.query(Clip).filter(Clip.job_id == job_id).delete()
    job.status = JobStatus.PENDING
    job.progress = 0
    job.error_message = None
    job.clips_count = None
    job.transcript_path = None
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
        filename=job.filename
    )

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
    db.query(Clip).filter(Clip.job_id == job_id).delete()
    db.delete(job)
    db.commit()
    
    return {"success": True}
