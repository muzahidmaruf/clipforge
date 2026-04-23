import os
_ffmpeg_bin = r"C:\Users\MARUF\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
os.environ["PATH"] = _ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

from services.pipeline import celery_app

# This file is used to start the Celery worker:
# celery -A celery_app worker --loglevel=info
