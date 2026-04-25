"""
AI face-tracking vertical crop — ported from OpenShorts.

Strategy:
  • TRACK  — single dominant speaker on screen.  MediaPipe BlazeFace detects
             faces each frame → SmoothedCameraman only moves when face leaves
             the "safe zone", giving a stable "heavy tripod" feel.
  • GENERAL — group shot / wide shot / no clear speaker.  Blur-background
             treatment: speaker region in 9:16 window, blurred full-frame
             as background fill.

Fall-back chain: MediaPipe → YOLOv8 → centre crop (no deps crash).
"""

from __future__ import annotations
import os
import subprocess
import tempfile
from typing import Optional

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Optional imports — degrade gracefully if not installed
# ---------------------------------------------------------------------------
try:
    import mediapipe as mp
    _MP_AVAILABLE = True
    _mp_face = mp.solutions.face_detection
except ImportError:
    _MP_AVAILABLE = False
    _mp_face = None

try:
    from ultralytics import YOLO as _YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False
    _YOLO = None

try:
    from scenedetect import SceneManager, open_video, ContentDetector
    _SCENE_AVAILABLE = True
except ImportError:
    _SCENE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET_W, TARGET_H = 1080, 1920      # 9:16 output
SAFE_ZONE = 0.65                     # face centre stays within ±65% of crop centre
SMOOTHING = 0.07                     # EMA coefficient — lower = smoother camera
SPEAKER_COOLDOWN = 1.5               # seconds before switching tracked speaker
MIN_FACE_AREA = 0.002                # fraction of frame area — ignore tiny faces


# ---------------------------------------------------------------------------
# Scene detection
# ---------------------------------------------------------------------------

def _detect_scene_boundaries(video_path: str) -> list[float]:
    """Return list of scene-change timestamps (seconds)."""
    if not _SCENE_AVAILABLE:
        return []
    try:
        video = open_video(video_path)
        manager = SceneManager()
        manager.add_detector(ContentDetector(threshold=27.0))
        manager.detect_scenes(video, show_progress=False)
        scenes = manager.get_scene_list()
        # Return start time of every scene except the first
        return [s[0].get_seconds() for s in scenes[1:]]
    except Exception as e:
        print(f"[face_tracker] scene detection failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Face detectors
# ---------------------------------------------------------------------------

class _MediaPipeDetector:
    def __init__(self):
        self._det = _mp_face.FaceDetection(
            model_selection=0,          # 0 = short-range, faster
            min_detection_confidence=0.5,
        )

    def detect(self, bgr_frame: np.ndarray) -> list[tuple[float, float, float, float]]:
        """Returns list of (cx_norm, cy_norm, w_norm, h_norm) bboxes."""
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        result = self._det.process(rgb)
        faces = []
        if result.detections:
            for det in result.detections:
                bb = det.location_data.relative_bounding_box
                cx = bb.xmin + bb.width / 2
                cy = bb.ymin + bb.height / 2
                faces.append((cx, cy, bb.width, bb.height))
        return faces

    def close(self):
        self._det.close()


class _YoloDetector:
    def __init__(self):
        self._model = _YOLO("yolov8n.pt")  # nano — fastest

    def detect(self, bgr_frame: np.ndarray) -> list[tuple[float, float, float, float]]:
        results = self._model(bgr_frame, classes=[0], verbose=False)  # class 0 = person
        faces = []
        h, w = bgr_frame.shape[:2]
        for r in results:
            for box in r.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = box
                cx = ((x1 + x2) / 2) / w
                cy = ((y1 + y2) / 2) / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h
                faces.append((cx, cy, bw, bh))
        return faces

    def close(self):
        pass


def _build_detector():
    if _MP_AVAILABLE:
        try:
            return _MediaPipeDetector()
        except Exception as e:
            print(f"[face_tracker] MediaPipe init failed ({e}), trying YOLO")
    if _YOLO_AVAILABLE:
        try:
            return _YoloDetector()
        except Exception as e:
            print(f"[face_tracker] YOLO init failed ({e}), falling back to centre crop")
    return None


# ---------------------------------------------------------------------------
# SmoothedCameraman — "Heavy Tripod" pattern
# ---------------------------------------------------------------------------

class SmoothedCameraman:
    """EMA-smoothed camera that only moves when the face leaves the safe zone.

    Coordinates are in normalised space (0..1 relative to source frame).
    crop_cx / crop_cy is the centre of the 9:16 crop window.
    """

    def __init__(self, initial_cx: float = 0.5, initial_cy: float = 0.5):
        self.crop_cx = initial_cx
        self.crop_cy = initial_cy
        # How much of the source height the crop window covers
        # (the width is crop_h * 9/16)

    def update(self, face_cx: float, face_cy: float, crop_w_norm: float, crop_h_norm: float) -> tuple[float, float]:
        """Feed a face position, return new (crop_cx, crop_cy) in normalised coords."""
        # Safe zone half-sizes in normalised units
        sx = crop_w_norm * SAFE_ZONE / 2
        sy = crop_h_norm * SAFE_ZONE / 2

        dx = face_cx - self.crop_cx
        dy = face_cy - self.crop_cy

        # Only move if outside safe zone
        if abs(dx) > sx:
            self.crop_cx += SMOOTHING * (dx - (sx if dx > 0 else -sx))
        if abs(dy) > sy:
            self.crop_cy += SMOOTHING * (dy - (sy if dy > 0 else -sy))

        # Clamp so the crop window stays inside the frame
        half_w = crop_w_norm / 2
        half_h = crop_h_norm / 2
        self.crop_cx = max(half_w, min(1.0 - half_w, self.crop_cx))
        self.crop_cy = max(half_h, min(1.0 - half_h, self.crop_cy))

        return self.crop_cx, self.crop_cy


# ---------------------------------------------------------------------------
# SpeakerTracker — prevents rapid face switching
# ---------------------------------------------------------------------------

class SpeakerTracker:
    def __init__(self, fps: float):
        self._current_id: Optional[int] = None
        self._frames_until_switch = 0
        self._cooldown_frames = int(fps * SPEAKER_COOLDOWN)

    def pick_face(self, faces: list[tuple[float, float, float, float]]) -> Optional[tuple[float, float, float, float]]:
        """Select the largest face, with hysteresis to avoid jitter."""
        if not faces:
            return None

        # Sort by area descending
        sorted_faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)

        if self._current_id is None:
            self._current_id = 0
            return sorted_faces[0]

        if self._frames_until_switch > 0:
            self._frames_until_switch -= 1
            idx = min(self._current_id, len(sorted_faces) - 1)
            return sorted_faces[idx]

        # Check if best face changed
        if self._current_id != 0:
            self._current_id = 0
            self._frames_until_switch = self._cooldown_frames

        return sorted_faces[0]


# ---------------------------------------------------------------------------
# Strategy classifier
# ---------------------------------------------------------------------------

def _classify_strategy(video_path: str, sample_frames: int = 20) -> str:
    """Return 'TRACK' or 'GENERAL' based on face presence."""
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS) or 25

    detector = _build_detector()
    if detector is None:
        cap.release()
        return "GENERAL"

    face_frame_count = 0
    step = max(1, total // sample_frames)

    for i in range(sample_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * step)
        ret, frame = cap.read()
        if not ret:
            break
        faces = detector.detect(frame)
        if faces:
            # Count frames where at least one face is reasonably large
            h, w = frame.shape[:2]
            big = [f for f in faces if f[2] * f[3] > MIN_FACE_AREA]
            if big:
                face_frame_count += 1

    cap.release()
    try:
        detector.close()
    except Exception:
        pass

    ratio = face_frame_count / max(sample_frames, 1)
    strategy = "TRACK" if ratio >= 0.4 else "GENERAL"
    print(f"[face_tracker] face ratio={ratio:.2f} → strategy={strategy}")
    return strategy


# ---------------------------------------------------------------------------
# Per-scene processing
# ---------------------------------------------------------------------------

def _process_track_scene(
    cap: cv2.VideoCapture,
    out: cv2.VideoWriter,
    detector,
    start_frame: int,
    end_frame: int,
    src_w: int,
    src_h: int,
):
    """Write face-tracked 9:16 frames for a single scene."""
    fps   = cap.get(cv2.CAP_PROP_FPS) or 25
    tracker = SpeakerTracker(fps)
    camera  = SmoothedCameraman(initial_cx=0.5, initial_cy=0.4)

    # Compute crop window size in pixels
    crop_h_px = src_h
    crop_w_px = int(src_h * 9 / 16)
    if crop_w_px > src_w:
        crop_w_px = src_w
        crop_h_px = int(src_w * 16 / 9)

    crop_w_norm = crop_w_px / src_w
    crop_h_norm = crop_h_px / src_h

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    for _ in range(end_frame - start_frame):
        ret, frame = cap.read()
        if not ret:
            break

        faces = detector.detect(frame) if detector else []
        # Filter tiny faces
        faces = [f for f in faces if f[2] * f[3] > MIN_FACE_AREA]

        chosen = tracker.pick_face(faces)
        if chosen:
            face_cx, face_cy = chosen[0], chosen[1]
        else:
            face_cx, face_cy = 0.5, 0.4   # fallback: upper-centre

        cx, cy = camera.update(face_cx, face_cy, crop_w_norm, crop_h_norm)

        # Pixel crop coordinates
        x1 = int((cx - crop_w_norm / 2) * src_w)
        y1 = int((cy - crop_h_norm / 2) * src_h)
        x1 = max(0, min(src_w - crop_w_px, x1))
        y1 = max(0, min(src_h - crop_h_px, y1))

        cropped = frame[y1:y1+crop_h_px, x1:x1+crop_w_px]
        resized = cv2.resize(cropped, (TARGET_W, TARGET_H), interpolation=cv2.INTER_LANCZOS4)
        out.write(resized)


def _process_general_scene(
    cap: cv2.VideoCapture,
    out: cv2.VideoWriter,
    start_frame: int,
    end_frame: int,
    src_w: int,
    src_h: int,
):
    """Write blur-background 9:16 frames for a scene with no clear speaker."""
    # Centre crop for main layer
    crop_h_px = src_h
    crop_w_px = int(src_h * 9 / 16)
    if crop_w_px > src_w:
        crop_w_px = src_w
        crop_h_px = int(src_w * 16 / 9)
    x1 = (src_w - crop_w_px) // 2
    y1 = (src_h - crop_h_px) // 2

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    for _ in range(end_frame - start_frame):
        ret, frame = cap.read()
        if not ret:
            break

        # Background: full-frame scaled + heavily blurred
        bg = cv2.resize(frame, (TARGET_W, TARGET_H), interpolation=cv2.INTER_LINEAR)
        bg = cv2.GaussianBlur(bg, (75, 75), 0)

        # Foreground: centred crop
        fg_crop = frame[y1:y1+crop_h_px, x1:x1+crop_w_px]
        # Fit to width, letterbox vertically
        scale = TARGET_W / crop_w_px
        fg_h = int(crop_h_px * scale)
        fg = cv2.resize(fg_crop, (TARGET_W, fg_h), interpolation=cv2.INTER_LANCZOS4)

        # Composite fg over bg, vertically centred
        paste_y = (TARGET_H - fg_h) // 2
        paste_y = max(0, paste_y)
        end_y = min(TARGET_H, paste_y + fg_h)
        bg[paste_y:end_y] = fg[:end_y - paste_y]

        out.write(bg)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reframe_with_face_tracking(input_path: str, output_path: str) -> str:
    """Reframe a clip to 9:16 using AI face tracking.

    Falls back to centre crop silently if deps are missing.
    Returns output_path.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    src_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps     = cap.get(cv2.CAP_PROP_FPS) or 25
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Already vertical — nothing to do
    if src_h > src_w:
        cap.release()
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path

    # Temp output — we'll add audio back with ffmpeg
    tmp_video = output_path.replace(".mp4", "_noaudio.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (TARGET_W, TARGET_H))

    # Decide strategy
    strategy = _classify_strategy(input_path)

    # Scene boundaries
    boundaries_sec = _detect_scene_boundaries(input_path)
    boundaries_frames = [0] + [int(t * fps) for t in boundaries_sec] + [n_frames]
    boundaries_frames = sorted(set(boundaries_frames))

    # Build detector once for TRACK
    detector = _build_detector() if strategy == "TRACK" else None

    print(f"[face_tracker] {src_w}x{src_h} → {TARGET_W}x{TARGET_H} | strategy={strategy} | scenes={len(boundaries_frames)-1}")

    for i in range(len(boundaries_frames) - 1):
        s = boundaries_frames[i]
        e = boundaries_frames[i + 1]
        if strategy == "TRACK":
            _process_track_scene(cap, writer, detector, s, e, src_w, src_h)
        else:
            _process_general_scene(cap, writer, s, e, src_w, src_h)

    cap.release()
    writer.release()

    if detector:
        try:
            detector.close()
        except Exception:
            pass

    # Mux audio back in
    from config import FFMPEG_PATH
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", tmp_video,
        "-i", input_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",  # ? = optional — silent clips OK
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    os.remove(tmp_video)

    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")
        raise RuntimeError(f"ffmpeg audio mux failed: {err}")

    print(f"[face_tracker] done → {output_path}")
    return output_path
