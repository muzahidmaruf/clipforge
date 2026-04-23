import os
import shutil
from datetime import datetime, timedelta

from config import UPLOADS_DIR, TEMP_DIR, CLIPS_DIR

def get_file_size(path: str) -> int:
    return os.path.getsize(path)

def cleanup_old_files():
    """Delete files older than 24h from uploads/temp, 48h from clips"""
    now = datetime.utcnow()

    for directory, max_age_hours in [(UPLOADS_DIR, 24), (TEMP_DIR, 24), (CLIPS_DIR, 48)]:
        if not os.path.exists(directory):
            continue
        cutoff = now - timedelta(hours=max_age_hours)
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            try:
                if os.path.isfile(filepath):
                    mtime = datetime.utcfromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff:
                        os.remove(filepath)
                elif os.path.isdir(filepath):
                    mtime = datetime.utcfromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff:
                        shutil.rmtree(filepath)
            except Exception:
                pass

def delete_job_files(job_id: str):
    """Delete all files associated with a job"""
    # Delete uploaded video
    uploads = os.listdir(UPLOADS_DIR)
    for f in uploads:
        if f.startswith(job_id):
            os.remove(os.path.join(UPLOADS_DIR, f))

    # Delete transcript
    transcript_path = os.path.join(os.path.dirname(UPLOADS_DIR), "transcripts", f"{job_id}.json")
    if os.path.exists(transcript_path):
        os.remove(transcript_path)

    # Delete clips
    clips_job_dir = os.path.join(CLIPS_DIR, job_id)
    if os.path.exists(clips_job_dir):
        shutil.rmtree(clips_job_dir)
