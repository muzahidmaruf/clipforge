import os
import traceback
import threading
import time
from celery import Celery
from sqlalchemy.orm import Session

from config import REDIS_URL, UPLOADS_DIR, TRANSCRIPTS_DIR, CLIPS_DIR
from database import SessionLocal, Job, Clip, JobStatus, DB_PATH
from services.transcription import transcribe_video, format_transcript
from services.analysis import analyze_transcript, validate_segments
from services.video_processor import (
    get_video_info, cut_clip, reframe_to_vertical, 
    find_nearest_silence, get_video_duration
)
from utils.time_utils import seconds_to_timestamp, parse_timestamp
from utils.file_utils import get_file_size

celery_app = Celery(
    "clipforge",
    broker=REDIS_URL,
    backend=f"db+sqlite:///{DB_PATH}",
)

@celery_app.task(bind=True, max_retries=3)
def process_video(self, job_id: str):
    """Main Celery task that processes a video through the full pipeline"""
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Clean up any clips from previous attempts (prevents duplicates on retry)
        db.query(Clip).filter(Clip.job_id == job_id).delete()
        db.commit()

        whisper_model = job.whisper_model or "base"
        ai_model = job.ai_model or "gemma4:31b-cloud"
        
        # STEP 1: Transcribing
        job.status = JobStatus.TRANSCRIBING
        job.progress = 10
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 10, "status": "transcribing"})

        # Tick progress from 10→34 while whisper runs (it gives no callbacks)
        stop_ticker = threading.Event()
        def _tick():
            p = 11
            while not stop_ticker.is_set() and p < 34:
                time.sleep(6)
                if stop_ticker.is_set():
                    break
                try:
                    tick_db = SessionLocal()
                    tick_job = tick_db.query(Job).filter(Job.id == job_id).first()
                    if tick_job and tick_job.status == JobStatus.TRANSCRIBING:
                        tick_job.progress = p
                        tick_db.commit()
                    tick_db.close()
                except Exception:
                    pass
                p = min(p + 1, 33)
        ticker = threading.Thread(target=_tick, daemon=True)
        ticker.start()

        try:
            transcript_result = transcribe_video(job.video_path, job_id, whisper_model)
        finally:
            stop_ticker.set()

        transcript_text = format_transcript(transcript_result)
        job.transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{job_id}.json")
        job.progress = 35
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 35, "status": "transcribing"})
        
        # Get video duration
        video_duration = get_video_duration(job.video_path)
        duration_str = seconds_to_timestamp(video_duration)
        
        # STEP 2: Analyzing
        job.status = JobStatus.ANALYZING
        job.progress = 40
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 40, "status": "analyzing"})
        
        segments = analyze_transcript(transcript_text, duration_str, ai_model)
        valid_segments = validate_segments(segments, video_duration)
        
        if not valid_segments:
            raise ValueError("No valid segments found after analysis")
        
        job.progress = 65
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 65, "status": "analyzing"})
        
        # STEP 3: Cutting
        job.status = JobStatus.CUTTING
        job.progress = 70
        db.commit()
        self.update_state(state="PROGRESS", meta={"progress": 70, "status": "cutting"})
        
        clips_job_dir = os.path.join(CLIPS_DIR, job_id)
        os.makedirs(clips_job_dir, exist_ok=True)
        
        total_segments = len(valid_segments)
        for i, seg in enumerate(valid_segments):
            progress = 70 + int((i / total_segments) * 25)
            self.update_state(state="PROGRESS", meta={"progress": progress, "status": "cutting"})
            
            start = seg["start_seconds"]
            end = seg["end_seconds"]
            
            # Snap to silence for clean cuts
            start = find_nearest_silence(job.video_path, start, 1.5)
            end = find_nearest_silence(job.video_path, end, 1.5)
            
            # Ensure valid range after snapping
            if end <= start:
                end = seg["end_seconds"]
            if end - start < 30:
                end = min(start + 45, video_duration)
            
            clip_filename = f"clip_{seg['clip_index']:02d}.mp4"
            clip_path = os.path.join(clips_job_dir, clip_filename)
            temp_path = os.path.join(clips_job_dir, f"temp_{seg['clip_index']:02d}.mp4")
            
            try:
                # Cut the clip
                cut_clip(job.video_path, temp_path, start, end)
                
                # Reframe to vertical if needed
                reframe_to_vertical(temp_path, clip_path)
                
                # Clean up temp file
                if os.path.exists(temp_path) and temp_path != clip_path:
                    os.remove(temp_path)
                
                # Save to DB — use the SNAPPED (actual) times so subtitles
                # align with the cut clip, not the AI's original guess.
                clip = Clip(
                    job_id=job_id,
                    clip_index=seg["clip_index"],
                    filename=clip_filename,
                    start_time=seconds_to_timestamp(start),
                    end_time=seconds_to_timestamp(end),
                    duration=end - start,
                    virality_score=seg["virality_score"],
                    hook=seg["hook"],
                    reason=seg["reason"],
                    file_path=clip_path,
                    file_size=get_file_size(clip_path)
                )
                db.add(clip)
                db.commit()
                
            except Exception as e:
                print(f"Warning: Failed to cut clip {seg['clip_index']}: {e}")
                continue
        
        # STEP 4: Completed
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.clips_count = db.query(Clip).filter(Clip.job_id == job_id).count()
        db.commit()
        self.update_state(state="SUCCESS", meta={"progress": 100, "status": "completed"})
        
    except Exception as e:
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"Pipeline error: {error_msg}\n{traceback_str}")
        
        if job:
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            job.progress = 0
            db.commit()
        
        self.update_state(state="FAILURE", meta={"error": error_msg})
        raise self.retry(exc=e, countdown=5)
    
    finally:
        db.close()
