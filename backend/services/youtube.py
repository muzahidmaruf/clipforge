"""
YouTube video download using yt-dlp.
Uses the tv_embed / android player clients to bypass bot-detection.
"""
import os
import re
import uuid
import subprocess

from config import UPLOADS_DIR, MAX_VIDEO_DURATION_MINUTES


def _sanitize_title(title: str, max_len: int = 80) -> str:
    """Strip characters unsafe in filenames, truncate."""
    safe = re.sub(r'[\\/:*?"<>|]', "_", title)
    return safe[:max_len].strip()


def download_youtube(
    url: str,
    job_id: str | None = None,
    max_height: int = 1080,
) -> dict:
    """Download a YouTube video with yt-dlp.

    Returns:
        {
            "file_path": str,
            "filename":  str,   # original title + ext
            "title":     str,
            "duration":  float, # seconds
        }

    Raises RuntimeError on failure.
    """
    if job_id is None:
        job_id = str(uuid.uuid4())

    # yt-dlp format: best video+audio up to max_height, prefer mp4
    fmt = f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_height}][ext=mp4]/best"

    out_template = os.path.join(UPLOADS_DIR, f"{job_id}_%(title)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--format", fmt,
        "--merge-output-format", "mp4",
        "--output", out_template,
        # bypass bot-detection
        "--extractor-args", "youtube:player_client=tv_embed,android",
        "--no-playlist",
        # write metadata so we can read title/duration without probing
        "--print-json",
        "--no-simulate",
        url,
    ]

    print(f"[youtube] downloading: {url}")
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=MAX_VIDEO_DURATION_MINUTES * 60 * 3,  # generous timeout
    )

    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")
        print(f"[youtube] yt-dlp error: {err}")
        raise RuntimeError(f"yt-dlp failed: {err[:400]}")

    # yt-dlp --print-json writes one JSON line per video to stdout
    import json
    try:
        info = json.loads(result.stdout.decode(errors="replace").strip().splitlines()[-1])
    except Exception:
        info = {}

    title     = info.get("title", "youtube_video")
    duration  = float(info.get("duration") or 0)
    ext       = info.get("ext", "mp4")
    safe_title = _sanitize_title(title)
    filename  = f"{safe_title}.{ext}"

    # Resolve the actual file path — yt-dlp may have renamed it
    expected = os.path.join(UPLOADS_DIR, f"{job_id}_{safe_title}.{ext}")
    if not os.path.exists(expected):
        # Scan the uploads dir for the job_id prefix
        for f in os.listdir(UPLOADS_DIR):
            if f.startswith(job_id) and f.endswith(".mp4"):
                expected = os.path.join(UPLOADS_DIR, f)
                filename = f[len(job_id) + 1:]  # strip "JOB_ID_" prefix
                break

    if not os.path.exists(expected):
        raise RuntimeError(f"Downloaded file not found at {expected}")

    print(f"[youtube] downloaded → {expected} ({duration:.0f}s)")
    return {
        "file_path": expected,
        "filename":  filename,
        "title":     title,
        "duration":  duration,
    }
