from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UploadResponse(BaseModel):
    job_id: str
    status: str
    message: str

class ClipResponse(BaseModel):
    id: str
    clip_index: int
    filename: str
    start_time: str
    end_time: str
    duration: float
    virality_score: int
    hook: str
    reason: str
    file_size: int
    created_at: datetime
    viral_hook_text: Optional[str] = None
    tiktok_description: Optional[str] = None
    instagram_description: Optional[str] = None
    youtube_title: Optional[str] = None

class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    error_message: Optional[str] = None
    clips_count: Optional[int] = None
    created_at: datetime
    filename: Optional[str] = None
    mode: Optional[str] = None
    num_clips: Optional[int] = None

class CleanedVideoInfo(BaseModel):
    available: bool
    original_duration: Optional[float] = None
    cleaned_duration: Optional[float] = None
    saved_seconds: Optional[float] = None
    fillers_removed: Optional[int] = None

class JobWithClipsResponse(JobResponse):
    clips: List[ClipResponse] = []
    cleaned: Optional[CleanedVideoInfo] = None

class DeleteResponse(BaseModel):
    success: bool
