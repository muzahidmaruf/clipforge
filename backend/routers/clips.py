import os
import re
import json
import random
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import TRANSCRIPTS_DIR
from utils.time_utils import parse_timestamp
from services.director import generate_motion

router = APIRouter(prefix="/api", tags=["clips"])


# Keyword → emoji map. Regex patterns match word stems; first match wins.
# Key is the emoji, value is a regex matched against the lowercased, punctuation-stripped word.
EMOJI_TRIGGERS = [
    ("💰", r"\b(money|cash|dollar|dollars|rich|wealth|wealthy|million|millions|billion|billions|profit|revenue|earn|earning|earnings|paid|paycheck|salary)\b"),
    ("🔥", r"\b(fire|lit|hot|blazing|flaming|amazing|incredible|awesome|insane|crazy|wild)\b"),
    ("🚀", r"\b(rocket|launch|launched|launching|takeoff|skyrocket|skyrocketed|explode|exploded|exploding)\b"),
    ("🧠", r"\b(brain|brains|mind|minds|think|thinking|thought|thoughts|genius|intelligent|smart|intellect|neuroscience)\b"),
    ("❤️", r"\b(love|loved|loving|heart|hearts|adore|passion)\b"),
    ("😂", r"\b(funny|hilarious|laugh|laughing|laughed|joke|jokes|lol|hahaha)\b"),
    ("😱", r"\b(shocking|shocked|shock|terrifying|scary|horrifying|omg)\b"),
    ("💡", r"\b(idea|ideas|insight|insights|realize|realized|epiphany|discover|discovered|eureka)\b"),
    ("📈", r"\b(grow|growing|growth|increase|increased|rise|rising|boom|booming|scale|scaling)\b"),
    ("📉", r"\b(decline|declined|drop|dropped|crash|crashed|fall|falling|fell|decrease|decreased|lose|lost)\b"),
    ("⚡", r"\b(fast|faster|fastest|quick|quickly|rapid|speed|instant|instantly|lightning)\b"),
    ("⏰", r"\b(time|hours|hour|minute|minutes|deadline|late|early|morning|night|schedule)\b"),
    ("🎯", r"\b(target|targets|goal|goals|aim|focus|focused|precise|precision|mission)\b"),
    ("🏆", r"\b(win|wins|winning|won|winner|champion|trophy|victory|victorious|success|succeed|successful)\b"),
    ("💀", r"\b(dead|dying|die|death|killed|kill|destroy|destroyed|ruined)\b"),
    ("🤔", r"\b(why|how|what|really|seriously|maybe|perhaps|question|questions|wonder|wondering)\b"),
    ("👀", r"\b(watch|watching|see|seeing|look|looking|notice|noticed|spot|spotted)\b"),
    ("🤯", r"\b(mindblown|mindblowing|unreal|unbelievable|wow|jaw)\b"),
    ("💪", r"\b(strong|strength|strongest|power|powerful|muscle|train|training|workout|fitness)\b"),
    ("🍕", r"\b(pizza|food|eat|eating|hungry|dinner|lunch|breakfast|meal)\b"),
    ("✨", r"\b(magic|magical|special|beautiful|stunning|gorgeous|perfect|perfection)\b"),
    ("⚠️", r"\b(warning|warn|danger|dangerous|careful|caution|risk|risky|beware)\b"),
    ("🎬", r"\b(film|films|movie|movies|director|scene|action|cut|camera)\b"),
    ("📱", r"\b(phone|phones|iphone|android|app|apps|smartphone|device)\b"),
    ("💻", r"\b(computer|computers|laptop|software|code|coding|coder|developer|programmer|tech)\b"),
    ("🤖", r"\b(ai|robot|robots|machine|machines|algorithm|algorithms|chatbot|automation)\b"),
]


# Word that triggers a "punch" (video zoom + slight shake)
def _is_punch_word(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if t.endswith("!") or t.endswith("?!"):
        return True
    if re.search(r"\d", t):
        return True
    letters = re.sub(r"[^A-Za-z]", "", t)
    if len(letters) >= 3 and letters == letters.upper():
        return True
    return False


@router.get("/clips/{clip_id}/download")
def download_clip(clip_id: str):
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip or not os.path.exists(clip.file_path):
            raise HTTPException(404, detail="Clip not found")

        return FileResponse(
            clip.file_path,
            media_type="video/mp4",
            filename=clip.filename
        )
    finally:
        db.close()


@router.get("/clips/{clip_id}/stream")
def stream_clip(clip_id: str):
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip or not os.path.exists(clip.file_path):
            raise HTTPException(404, detail="Clip not found")

        return FileResponse(
            clip.file_path,
            media_type="video/mp4"
        )
    finally:
        db.close()


@router.get("/clips/{clip_id}/subtitles")
def get_clip_subtitles(clip_id: str):
    """
    Return word-level subtitles for a clip.
    Filters the job's full Whisper transcript to words within the clip's
    time range, then rebases timestamps to 0 (relative to clip start).
    """
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(404, detail="Clip not found")

        transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{clip.job_id}.json")
        if not os.path.exists(transcript_path):
            raise HTTPException(404, detail="Transcript not found")

        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = json.load(f)

        clip_start = parse_timestamp(clip.start_time)
        clip_end = parse_timestamp(clip.end_time)

        words = []
        for segment in transcript.get("segments", []):
            for w in segment.get("words", []):
                w_start = float(w["start"])
                w_end = float(w["end"])
                # Word overlaps the clip range
                if w_end >= clip_start and w_start <= clip_end:
                    rel_start = max(0.0, w_start - clip_start)
                    rel_end = max(rel_start, w_end - clip_start)
                    words.append({
                        "word": w["word"].strip(),
                        "start": round(rel_start, 3),
                        "end": round(rel_end, 3),
                    })

        return {
            "clip_id": clip_id,
            "duration": round(clip_end - clip_start, 3),
            "words": words,
        }
    finally:
        db.close()


@router.get("/clips/{clip_id}/effects")
def get_clip_effects(clip_id: str):
    """
    Scan the clip's transcript for keyword matches and return a timeline of
    visual effects (emoji bursts + zoom punches) that the frontend can render
    over the video.
    """
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(404, detail="Clip not found")

        transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{clip.job_id}.json")
        if not os.path.exists(transcript_path):
            raise HTTPException(404, detail="Transcript not found")

        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = json.load(f)

        clip_start = parse_timestamp(clip.start_time)
        clip_end = parse_timestamp(clip.end_time)

        effects = []
        # Keep random positions deterministic per clip so a re-fetch is stable
        rng = random.Random(clip_id)
        last_emoji_time = -10.0  # debounce so emojis don't stack

        for segment in transcript.get("segments", []):
            for w in segment.get("words", []):
                w_start = float(w["start"])
                w_end = float(w["end"])
                if w_end < clip_start or w_start > clip_end:
                    continue

                rel_start = max(0.0, w_start - clip_start)
                rel_end = max(rel_start, w_end - clip_start)
                text = w["word"].strip()
                clean = re.sub(r"[^a-zA-Z0-9]", "", text).lower()
                if not clean:
                    continue

                # Emoji trigger (debounced to one every 1.2s)
                if rel_start - last_emoji_time > 1.2:
                    for emoji, pattern in EMOJI_TRIGGERS:
                        if re.search(pattern, clean, re.IGNORECASE):
                            effects.append({
                                "type": "emoji",
                                "value": emoji,
                                "start": round(rel_start, 3),
                                "end": round(rel_start + 1.4, 3),
                                # Random position, biased toward top-third and sides
                                "x": round(rng.choice([0.18, 0.25, 0.72, 0.8]) + rng.uniform(-0.05, 0.05), 3),
                                "y": round(rng.uniform(0.15, 0.45), 3),
                                "rotate": rng.randint(-15, 15),
                            })
                            last_emoji_time = rel_start
                            break

                # Punch trigger (zoom + shake)
                if _is_punch_word(text):
                    effects.append({
                        "type": "punch",
                        "start": round(rel_start, 3),
                        "end": round(min(rel_end + 0.15, rel_start + 0.5), 3),
                        "intensity": 1.06,
                    })

        effects.sort(key=lambda e: e["start"])

        return {
            "clip_id": clip_id,
            "duration": round(clip_end - clip_start, 3),
            "effects": effects,
        }
    finally:
        db.close()


@router.get("/clips/{clip_id}/motion")
def get_clip_motion(clip_id: str, refresh: bool = False):
    """
    AI-directed motion graphics shot list for a clip.

    Calls Gemma to plan lower thirds, stat cards, and pull quotes based on the
    transcript. Caches the result — pass ?refresh=true to regenerate.
    """
    from database import SessionLocal, Clip
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(404, detail="Clip not found")

        transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{clip.job_id}.json")
        if not os.path.exists(transcript_path):
            raise HTTPException(404, detail="Transcript not found")

        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = json.load(f)

        clip_start = parse_timestamp(clip.start_time)
        clip_end = parse_timestamp(clip.end_time)
        duration = clip_end - clip_start

        words = []
        for segment in transcript.get("segments", []):
            for w in segment.get("words", []):
                w_start = float(w["start"])
                w_end = float(w["end"])
                if w_end >= clip_start and w_start <= clip_end:
                    words.append({
                        "word": w["word"].strip(),
                        "start": max(0.0, w_start - clip_start),
                        "end": max(0.0, w_end - clip_start),
                    })

        cues = generate_motion(clip_id, words, duration, force=refresh)

        return {
            "clip_id": clip_id,
            "duration": round(duration, 3),
            "cues": cues,
        }
    finally:
        db.close()
