import os
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")
TRANSCRIPTS_DIR = os.path.join(STORAGE_DIR, "transcripts")
CLIPS_DIR = os.path.join(STORAGE_DIR, "clips")
TEMP_DIR = os.path.join(STORAGE_DIR, "temp")
MOTION_DIR = os.path.join(STORAGE_DIR, "motion")

# Ensure directories exist
for d in [UPLOADS_DIR, TRANSCRIPTS_DIR, CLIPS_DIR, TEMP_DIR, MOTION_DIR]:
    os.makedirs(d, exist_ok=True)

# Limits
MAX_VIDEO_SIZE_MB = 500
MAX_VIDEO_DURATION_MINUTES = 60
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# Whisper
WHISPER_MODEL = "base"

# Ollama Cloud — OpenAI-compatible endpoint: https://ollama.com/v1/chat/completions
# Model options: qwen3.5-cloud, gemma3:27b-cloud, llama3.1:70b-cloud, etc.
# See https://ollama.com/library/qwen3.5 for available Qwen models
OLLAMA_CLOUD_BASE_URL = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com")
OLLAMA_CLOUD_API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
OLLAMA_CLOUD_MODEL = os.getenv("OLLAMA_CLOUD_MODEL", "qwen3.5-cloud")
OLLAMA_CLOUD_TIMEOUT = int(os.getenv("OLLAMA_CLOUD_TIMEOUT", "120"))

# FFmpeg
FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    r"C:\Users\MARUF\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
)

# Redis / Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Clip settings
MIN_CLIP_DURATION = 30  # seconds
MAX_CLIP_DURATION = 90  # seconds
TARGET_CLIPS = 7  # how many clips to aim for
