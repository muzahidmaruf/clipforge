import os
_ffmpeg_bin = r"C:\Users\MARUF\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = _ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import upload, jobs, clips, fonts
from config import UPLOADS_DIR, TRANSCRIPTS_DIR, CLIPS_DIR, TEMP_DIR
import os

# Ensure storage directories exist
for d in [UPLOADS_DIR, TRANSCRIPTS_DIR, CLIPS_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

app = FastAPI(title="ClipForge API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(clips.router)
app.include_router(fonts.router)

@app.get("/")
def root():
    return {"message": "ClipForge API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
