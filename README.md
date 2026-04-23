# ClipForge

AI-powered video clipping tool that automatically generates viral short-form clips from long videos. Upload a long video, and ClipForge finds 4–7 self-contained, meaningful moments and exports them as vertical (9:16) clips with optional word-by-word captions.

## Stack

- **Backend**: FastAPI + Celery + Redis + SQLite
- **AI**: OpenAI Whisper (word-level timestamps, GPU-accelerated) + Ollama Cloud (Gemma 4)
- **Video**: FFmpeg (silence-aware cuts, 9:16 reframe)
- **Frontend**: React + Vite + Tailwind, with native HTML5 video + React caption overlay
- **Captions**: System font picker (via fontTools), position/size/words-per-line controls, persisted in localStorage

## Features

- Upload videos up to 60 minutes / 500MB
- Whisper transcription with word-level timestamps (CUDA if available)
- Gemma 4 picks clips with complete thoughts, strong hooks, and satisfying payoffs
- Silence-snapped cuts so clips never start/end mid-word
- Auto-reframe landscape → 9:16 vertical
- Word-by-word caption overlay synced to native `<video>` for perfect audio sync
- Configurable caption font (any installed system font), position, size, and words-per-line
- Real-time job progress tracking; per-clip download

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- FFmpeg
- Redis
- (Optional) NVIDIA GPU + CUDA 12.4 toolkit for fast Whisper transcription

### 1. Clone
```bash
git clone https://github.com/<your-username>/clipforge.git
cd clipforge
```

### 2. Backend
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Unix
source venv/bin/activate

pip install -r requirements.txt

# For GPU (optional but strongly recommended):
pip install torch --index-url https://download.pytorch.org/whl/cu124

cp .env.example .env
# Edit .env and add your OLLAMA_CLOUD_API_KEY
```

Get an Ollama Cloud API key at <https://ollama.com/settings/keys>.

### 3. Frontend
```bash
cd ../frontend
npm install
```

### 4. Run
Start Redis, then in separate terminals:

```bash
# terminal 1 — FastAPI
cd backend && source venv/Scripts/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# terminal 2 — Celery worker
cd backend && source venv/Scripts/activate
celery -A celery_app worker --pool=solo --loglevel=info

# terminal 3 — frontend dev server
cd frontend
npm run dev
```

Open <http://localhost:5173>.

## Project layout

```
backend/
  main.py              # FastAPI entry
  celery_app.py        # Celery config
  config.py            # env + constants
  routers/             # upload, jobs, clips, fonts
  services/
    pipeline.py        # orchestrates transcribe → analyze → cut
    transcription.py   # Whisper (GPU-aware)
    analysis.py        # Gemma prompt + clip selection
    ...
  models/              # SQLAlchemy models
frontend/
  src/
    components/
      CaptionedPlayer.jsx  # native <video> + React caption overlay
      ClipCard.jsx
    remotion/
      CaptionedClip.jsx    # Remotion composition (for server-side renders)
```

## License

MIT
