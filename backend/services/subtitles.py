"""
Subtitle generation and burning — ported from OpenShorts subtitles.py.
Generates word-grouped SRT files from Whisper transcripts and burns
them into clips via ffmpeg with ASS style overrides.
"""
import os
import json
import subprocess


# ---------------------------------------------------------------------------
# SRT helpers
# ---------------------------------------------------------------------------

def _format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_srt_block(index: int, start: float, end: float, text: str) -> str:
    return f"{index}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{text}\n\n"


def generate_srt(
    transcript: dict,
    clip_start: float,
    clip_end: float,
    output_path: str,
    max_chars: int = 20,
    max_duration: float = 2.0,
) -> bool:
    """Generate an SRT file from a Whisper transcript for a specific time window.

    Words are grouped into short lines suitable for vertical (9:16) video.
    Times are relative to clip_start so they start at 0 in the output file.

    Returns True on success, False if no words found in range.
    """
    words = []
    for segment in transcript.get("segments", []):
        for word_info in segment.get("words", []):
            if word_info["end"] > clip_start and word_info["start"] < clip_end:
                words.append(word_info)

    if not words:
        return False

    srt_content = ""
    index = 1
    current_block: list = []
    block_start: float = 0.0

    for word in words:
        start = max(0.0, word["start"] - clip_start)
        end   = max(0.0, word["end"]   - clip_start)

        if not current_block:
            current_block.append(word)
            block_start = start
        else:
            current_text_len = sum(len(w["word"]) + 1 for w in current_block)
            duration = end - block_start

            if current_text_len + len(word["word"]) > max_chars or duration > max_duration:
                block_end = current_block[-1]["end"] - clip_start
                text = " ".join(w["word"] for w in current_block).strip()
                srt_content += _format_srt_block(index, block_start, block_end, text)
                index += 1
                current_block = [word]
                block_start = start
            else:
                current_block.append(word)

    if current_block:
        block_end = current_block[-1]["end"] - clip_start
        text = " ".join(w["word"] for w in current_block).strip()
        srt_content += _format_srt_block(index, block_start, block_end, text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    return True


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _hex_to_ass_color(hex_color: str, opacity: float = 1.0) -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR format."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    alpha = round((1.0 - opacity) * 255)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


# ---------------------------------------------------------------------------
# Burn subtitles
# ---------------------------------------------------------------------------

def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    alignment: str = "bottom",
    fontsize: int = 16,
    font_name: str = "Verdana",
    font_color: str = "#FFFFFF",
    border_color: str = "#000000",
    border_width: int = 2,
    bg_color: str = "#000000",
    bg_opacity: float = 0.0,
) -> bool:
    """Burn SRT subtitles into a video using ffmpeg with ASS style overrides.

    Two modes:
    - Outline mode (bg_opacity=0): Text with coloured outline/border.
    - Box mode (bg_opacity>0): Text with semi-transparent background box.

    Returns True on success, raises on failure.
    """
    # ASS alignment codes: 2=bottom-centre, 6=top-centre, 10=middle-centre
    align_map = {"top": 6, "middle": 10, "bottom": 2}
    ass_alignment = align_map.get(str(alignment).lower(), 2)

    final_fontsize = max(10, int(fontsize * 0.85))

    # FFmpeg expects forward-slashes and escaped colons in the filter string
    safe_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")

    primary_colour = _hex_to_ass_color(font_color, 1.0)

    if bg_opacity > 0:
        border_style  = 3
        outline_colour = _hex_to_ass_color(bg_color, bg_opacity)
        outline_width  = 1
    else:
        border_style  = 1
        outline_colour = _hex_to_ass_color(border_color, 1.0)
        outline_width  = max(1, border_width)

    back_colour = _hex_to_ass_color("#000000", 0.0)

    style_string = (
        f"Alignment={ass_alignment},"
        f"Fontname={font_name},"
        f"Fontsize={final_fontsize},"
        f"PrimaryColour={primary_colour},"
        f"OutlineColour={outline_colour},"
        f"BackColour={back_colour},"
        f"BorderStyle={border_style},"
        f"Outline={outline_width},"
        f"Shadow=0,"
        f"MarginV=25,"
        f"Bold=1"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{safe_srt_path}':force_style='{style_string}'",
        "-c:a", "copy",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        output_path,
    ]

    print(f"[subtitles] burning: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")
        print(f"[subtitles] ffmpeg error: {err}")
        raise RuntimeError(f"ffmpeg subtitle burn failed: {err}")

    return True


# ---------------------------------------------------------------------------
# High-level helper used by the API endpoint
# ---------------------------------------------------------------------------

def generate_and_burn(
    clip_video_path: str,
    transcript: dict,
    clip_start_seconds: float,
    clip_end_seconds: float,
    output_path: str,
    subtitle_options: dict | None = None,
) -> str:
    """Generate an SRT for the clip window, burn it in, return output_path."""
    opts = subtitle_options or {}

    # SRT file sits next to the output video
    srt_path = output_path.replace(".mp4", ".srt")

    ok = generate_srt(
        transcript,
        clip_start_seconds,
        clip_end_seconds,
        srt_path,
        max_chars=opts.get("max_chars", 20),
        max_duration=opts.get("max_duration", 2.0),
    )
    if not ok:
        raise ValueError("No words found in clip time range — cannot generate subtitles")

    burn_subtitles(
        video_path=clip_video_path,
        srt_path=srt_path,
        output_path=output_path,
        alignment=opts.get("alignment", "bottom"),
        fontsize=opts.get("fontsize", 16),
        font_name=opts.get("font_name", "Verdana"),
        font_color=opts.get("font_color", "#FFFFFF"),
        border_color=opts.get("border_color", "#000000"),
        border_width=opts.get("border_width", 2),
        bg_color=opts.get("bg_color", "#000000"),
        bg_opacity=opts.get("bg_opacity", 0.0),
    )

    # Clean up the intermediate SRT
    try:
        os.remove(srt_path)
    except OSError:
        pass

    return output_path
