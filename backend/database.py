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
    ai_model = Column(String, default="gemma4:31b-cloud")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    video_path = Column(String, nullable=False)
    transcript_path = Column(String, nullable=True)
    clips_count = Column(Integer, nullable=True)
    celery_task_id = Column(String, nullable=True)

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

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
