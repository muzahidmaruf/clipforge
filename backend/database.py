import os
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class JobStatus(str, Enum):
    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    CUTTING = "cutting"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    status = Column(String, default=JobStatus.PENDING)
    progress = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    whisper_model = Column(String, default="base")
    whisper_language = Column(String, default="auto")  # ISO 639-1 code or "auto"
    ai_model = Column(String, default="qwen3.5:32b-cloud")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    video_path = Column(String, nullable=False)
    transcript_path = Column(String, nullable=True)
    clips_count = Column(Integer, nullable=True)
    celery_task_id = Column(String, nullable=True)

    # "clips" = only viral clips (default), "clean" = only cleaned full-length
    # video with fillers/pauses stripped, "both" = run both pipelines.
    mode = Column(String, default="clips")
    # How many short clips to aim for (only used when mode in {clips, both})
    num_clips = Column(Integer, default=5)

    # Cleaned video pipeline outputs
    cleaned_video_path = Column(String, nullable=True)
    cleaned_duration = Column(Float, nullable=True)
    original_duration = Column(Float, nullable=True)
    cleaned_fillers_removed = Column(Integer, nullable=True)

    # Checkpoint: validated segments saved after analysis so resume skips re-analysis
    segments_path = Column(String, nullable=True)

    clips = relationship("Clip", back_populates="job", cascade="all, delete-orphan")

class Clip(Base):
    __tablename__ = "clips"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    clip_index = Column(Integer, nullable=False)
    filename = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    duration = Column(Float, nullable=False)
    virality_score = Column(Integer, nullable=False)
    hook = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="clips")

# SQLite database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipforge.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def _migrate_sqlite_add_columns():
    """Tiny forward-only migration: add new columns to `jobs` if they're missing.
    SQLAlchemy's create_all() does NOT add columns to existing tables, so this
    backfills them for dev databases that predate the column additions."""
    from sqlalchemy import text
    want = {
        "mode": "VARCHAR DEFAULT 'clips'",
        "num_clips": "INTEGER DEFAULT 5",
        "cleaned_video_path": "VARCHAR",
        "cleaned_duration": "FLOAT",
        "original_duration": "FLOAT",
        "cleaned_fillers_removed": "INTEGER",
        "whisper_language": "VARCHAR DEFAULT 'auto'",
        "segments_path": "VARCHAR",
    }
    try:
        with engine.begin() as conn:
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(jobs)").fetchall()}
            for col, decl in want.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE jobs ADD COLUMN {col} {decl}")
    except Exception as e:
        print(f"[db migration] warning: {e}")


_migrate_sqlite_add_columns()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
