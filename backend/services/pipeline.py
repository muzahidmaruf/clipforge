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
from services.cleaner import clean_video
from utils.time_utils import seconds_to_timestamp, parse_timestamp
from utils.file_utils import get_file_size

celery_app = Celery(
    "clipforge",
    broker=REDIS_URL,
    backend=f"db+sqlite:///{DB_PATH}",
)

@celery_app.task(bind=True, max_retries=3)
def process_video(self, job_id: str):
    """Main Celery task — resumes from the last checkpoint automatically.

    Checkpoints (skipped if already on disk / in DB):
      1. Transcript JSON  → storage/transcripts/{job_id}.json
      2. Cleaned video    → job.cleaned_video_path
      3. Segments JSON    → storage/transcripts/{job_id}_segments.json
      4. Individual clips → storage/clips/{job_id}/clip_NN.mp4  (skipped per-clip)
    """
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        whisper_model    = job.whisper_model    or "base"
        whisper_language = job.whisper_language or "auto"
        ai_model         = job.ai_model         or "qwen3.5:32b-cloud"
        mode             = (job.mode or "clips").lower()
        if mode not in {"clips", "clean", "both"}:
            mode = "clips"
        num_clips = int(job.num_clips or 5)

        # ------------------------------------------------------------------
        # STAGE 1: Transcription
        # ------------------------------------------------------------------
        transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{job_id}.json")
        transcript_result = None

        if job.transcript_path and os.path.exists(job.transcript_path):
            # Resume: load from disk
            print(f"[pipeline] RESUME — transcript checkpoint found, skipping Whisper")
            import json as _json
            with open(job.transcript_path, "r", encoding="utf-8") as f:
                transcript_result = _json.load(f)
            job.progress = max(job.progress or 0, 35)
            db.commit()
        else:
            job.status = JobStatus.TRANSCRIBING
            job.progress = 10
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": 10, "status": "transcribing"})

            # Tick progress 10→34 while Whisper runs (no callbacks from Whisper)
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
                # Set a reasonable timeout based on video duration ( Whisper ~0.1-0.5x realtime on CPU)
                # For a 60 min video with base model: expect ~6-30 min on CPU, ~1-5 min on GPU
                video_dur = get_video_duration(job.video_path)
                max_transcribe_time = max(300, video_dur * 2)  # 2x video duration, min 5 min
                print(f"[pipeline] Whisper timeout set to {max_transcribe_time:.0f}s for {video_dur:.1f}s video")

                # Use a simple timer to track progress based on actual Whisper output
                import time
                transcribe_start = time.time()

                transcript_result = transcribe_video(
                    job.video_path, job_id, whisper_model, whisper_language
                )

                elapsed = time.time() - transcribe_start
                print(f"[pipeline] Whisper completed in {elapsed:.1f}s")

            except Exception as e:
                print(f"[pipeline] Whisper transcription failed: {e}")
                raise
            finally:
                stop_ticker.set()

            job.transcript_path = transcript_path
            job.progress = 35
            db.commit()
            self.update_state(state="PROGRESS", meta={"progress": 35, "status": "transcribed"})

        transcript_text = format_transcript(transcript_result)
        video_duration  = get_video_duration(job.video_path)
        duration_str    = seconds_to_timestamp(video_duration)

        # ------------------------------------------------------------------
        # STAGE 2: Clean video  (mode = clean | both)
        # ------------------------------------------------------------------
        if mode in ("clean", "both"):
            if job.cleaned_video_path and os.path.exists(job.cleaned_video_path):
                print("[pipeline] RESUME — cleaned video checkpoint found, skipping cleaner")
                job.progress = max(job.progress or 0, 60)
                db.commit()
            else:
                job.status   = JobStatus.CUTTING
                job.progress = max(job.progress or 0, 45)
                db.commit()
                self.update_state(state="PROGRESS", meta={"progress": job.progress, "status": "cleaning"})

                try:
                    stats = clean_video(
                        job_id=job_id,
                        input_path=job.video_path,
                        transcript_result=transcript_result,
                        video_duration=video_duration,
                    )
                    job.cleaned_video_path    = stats["output_path"]
                    job.cleaned_duration      = stats["cleaned_duration"]
                    job.original_duration     = stats["original_duration"]
                    job.cleaned_fillers_removed = stats["filler_words_removed"]
                    db.commit()
                except Exception as e:
                    if mode == "clean":
                        raise
                    print(f"[pipeline] Warning: clean step failed, continuing with clips: {e}")

                job.progress = 60
                db.commit()

        # ------------------------------------------------------------------
        # STAGE 3 + 4: Analyze → Cut clips  (mode = clips | both)
        # ------------------------------------------------------------------
        if mode in ("clips", "both"):
            segments_path = os.path.join(TRANSCRIPTS_DIR, f"{job_id}_segments.json")

            # ---- Stage 3: Analysis ----------------------------------------
            if job.segments_path and os.path.exists(job.segments_path):
                print("[pipeline] RESUME — segments checkpoint found, skipping AI analysis")
                import json as _json
                with open(job.segments_path, "r", encoding="utf-8") as f:
                    valid_segments = _json.load(f)
                job.progress = max(job.progress or 0, 70)
                db.commit()
            else:
                job.status   = JobStatus.ANALYZING
                job.progress = max(job.progress or 0, 65 if mode == "both" else 40)
                db.commit()
                self.update_state(state="PROGRESS", meta={"progress": job.progress, "status": "analyzing"})

                segments       = analyze_transcript(transcript_text, duration_str, ai_model, num_clips=num_clips)
                valid_segments = validate_segments(segments, video_duration)

                if not valid_segments:
                    raise ValueError("No valid segments found after analysis")

                # Sort by virality and cap to requested count
                valid_segments = sorted(valid_segments, key=lambda s: -s["virality_score"])[:num_clips]
                for i, s in enumerate(valid_segments, start=1):
                    s["clip_index"] = i

                # Save checkpoint so a resume skips this expensive API call
                import json as _json
                with open(segments_path, "w", encoding="utf-8") as f:
                    _json.dump(valid_segments, f, indent=2)
                job.segments_path = segments_path
                job.progress = 70
                db.commit()
                self.update_state(state="PROGRESS", meta={"progress": 70, "status": "cutting"})

            # ---- Stage 4: Cutting -----------------------------------------
            job.status = JobStatus.CUTTING
            clips_job_dir = os.path.join(CLIPS_DIR, job_id)
            os.makedirs(clips_job_dir, exist_ok=True)

            # Build index of clips already fully cut (file on disk + DB row)
            existing = {
                c.clip_index
                for c in db.query(Clip).filter(Clip.job_id == job_id).all()
                if c.file_path and os.path.exists(c.file_path)
            }
            if existing:
                print(f"[pipeline] RESUME — {len(existing)} clip(s) already cut: {sorted(existing)}")

            pending_segments = [s for s in valid_segments if s["clip_index"] not in existing]
            total_segments   = len(valid_segments)

            for i, seg in enumerate(pending_segments):
                done_so_far = len(existing) + i
                progress = 70 + int((done_so_far / total_segments) * 25)
                self.update_state(state="PROGRESS", meta={"progress": progress, "status": "cutting"})

                start = seg["start_seconds"]
                end   = seg["end_seconds"]

                # Snap to silence for clean cuts
                start = find_nearest_silence(job.video_path, start, 1.5)
                end   = find_nearest_silence(job.video_path, end,   1.5)

                # Ensure valid range after snapping
                if end <= start:
                    end = seg["end_seconds"]
                if end - start < 30:
                    end = min(start + 45, video_duration)

                clip_filename = f"clip_{seg['clip_index']:02d}.mp4"
                clip_path     = os.path.join(clips_job_dir, clip_filename)
                temp_path     = os.path.join(clips_job_dir, f"temp_{seg['clip_index']:02d}.mp4")

                try:
                    cut_clip(job.video_path, temp_path, start, end)
                    reframe_to_vertical(temp_path, clip_path)
                    if os.path.exists(temp_path) and temp_path != clip_path:
                        os.remove(temp_path)

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
                        file_size=get_file_size(clip_path),
                    )
                    db.add(clip)
                    db.commit()
                except Exception as e:
                    print(f"[pipeline] Warning: failed to cut clip {seg['clip_index']}: {e}")
                    continue

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        job.status     = JobStatus.COMPLETED
        job.progress   = 100
        job.clips_count = db.query(Clip).filter(Clip.job_id == job_id).count()
        db.commit()
        self.update_state(state="SUCCESS", meta={"progress": 100, "status": "completed"})

    except Exception as e:
        error_msg    = str(e)
        traceback_str = traceback.format_exc()
        print(f"[pipeline] error: {error_msg}\n{traceback_str}")

        if job:
            job.status        = JobStatus.FAILED
            job.error_message = error_msg
            job.progress      = 0
            db.commit()

        self.update_state(state="FAILURE", meta={"error": error_msg})
        raise self.retry(exc=e, countdown=5)

    finally:
        db.close()
