import subprocess
import os
import ffmpeg
from config import CLIPS_DIR, TEMP_DIR, FFMPEG_PATH

def get_video_info(video_path: str):
    """Get video dimensions and duration"""
    probe = ffmpeg.probe(video_path, cmd=FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe"))
    video_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    duration = float(probe["format"]["duration"])
    return width, height, duration

def is_landscape(width: int, height: int) -> bool:
    return width > height

def find_nearest_silence(video_path: str, target_time: float, search_window: float = 2.0) -> float:
    """Find nearest silence point to target_time for clean cuts"""
    try:
        cmd = [
            FFMPEG_PATH, "-i", video_path,
            "-ss", str(max(0, target_time - search_window)),
            "-t", str(search_window * 2),
            "-af", "silencedetect=noise=-30dB:duration=0.3",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr = result.stderr
        
        # Parse silence_start timestamps
        silence_starts = []
        for line in stderr.split("\n"):
            if "silence_start:" in line:
                try:
                    ts = float(line.split("silence_start:")[1].strip())
                    # Adjust for the offset
                    actual_ts = max(0, target_time - search_window) + ts
                    silence_starts.append(actual_ts)
                except (ValueError, IndexError):
                    continue
        
        if not silence_starts:
            return target_time
        
        # Find nearest silence to target
        nearest = min(silence_starts, key=lambda x: abs(x - target_time))
        return nearest
    except Exception:
        return target_time

def cut_clip(input_path: str, output_path: str, start_seconds: float, end_seconds: float, 
             add_captions: bool = True) -> str:
    """Cut a clip from video with padding and optional captions"""
    duration = end_seconds - start_seconds
    
    # Add padding
    start = max(0, start_seconds - 0.3)
    end_pad = end_seconds + 0.5
    total_duration = (end_pad - start)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    cmd = [
        FFMPEG_PATH, "-y",
        "-ss", str(start),
        "-i", input_path,
        "-t", str(total_duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr}")
    
    return output_path

def reframe_to_vertical(input_path: str, output_path: str, use_face_tracking: bool = True) -> str:
    """Reframe landscape video to 9:16 vertical.

    When use_face_tracking=True (default) tries AI face-tracking crop first.
    Falls back to centre crop if face_tracker deps are not installed.
    """
    width, height, _ = get_video_info(input_path)

    if not is_landscape(width, height):
        # Already vertical or square, just copy
        os.rename(input_path, output_path)
        return output_path

    if use_face_tracking:
        try:
            from services.face_tracker import reframe_with_face_tracking
            return reframe_with_face_tracking(input_path, output_path)
        except ImportError:
            print("[video_processor] face_tracker deps not installed, falling back to centre crop")
        except Exception as e:
            print(f"[video_processor] face_tracker failed ({e}), falling back to centre crop")

    # Centre crop fallback
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", input_path,
        "-vf", "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg reframe error: {result.stderr}")

    return output_path

def extract_thumbnail(video_path: str, output_path: str, time: float = 0.0):
    """Extract thumbnail from video at given time"""
    cmd = [
        FFMPEG_PATH, "-y",
        "-ss", str(time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, text=True)

def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds"""
    probe = ffmpeg.probe(video_path, cmd=FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe"))
    return float(probe["format"]["duration"])
