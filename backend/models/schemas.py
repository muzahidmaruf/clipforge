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

class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    error_message: Optional[str] = None
    clips_count: Optional[int] = None
    created_at: datetime
    filename: Optional[str] = None

class JobWithClipsResponse(JobResponse):
    clips: List[ClipResponse] = []

class DeleteResponse(BaseModel):
    success: bool
