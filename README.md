# Reel Checker

Reel Checker is an AI-powered fact-checking application that extracts audio from Instagram Reels (or uploaded video/audio files), transcribes the speech, extracts factual claims, verifies them using Google Search grounding, and provides a clear fact-check report with cited sources.

---

## 🚀 Quickstart (Windows PowerShell)

### 1. Prerequisites
- **Python 3.11+** installed
- **FFmpeg & ffprobe** installed and accessible on PATH

#### Installing FFmpeg:
- **Windows (PowerShell):**
  ```powershell
  winget install Gyan.FFmpeg
  ```
  *(Restart your PowerShell terminal after installation to refresh PATH)*
- **macOS:**
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu/Debian:**
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```

---

### 2. Environment Setup

From the project root:

```powershell
# 1. Create a Python virtual environment
python -m venv .venv

# 2. Activate the virtual environment in PowerShell
.\.venv\Scripts\Activate.ps1

# 3. Install backend dependencies (includes faster-whisper)
pip install -r backend\requirements.txt

# 4. Configure environment variables
Copy-Item .env.example .env
```

#### Choose Your Transcription Provider in `.env`:
- **Free Local Transcription (Default):**
  Uses `faster-whisper` running directly on your CPU without any API keys or costs.
  ```env
  TRANSCRIBE_PROVIDER=local
  LOCAL_WHISPER_MODEL=small
  LOCAL_WHISPER_DEVICE=cpu
  ```
  *Local Model Download Sizes (downloaded once on first run from HuggingFace Hub):*
  - `tiny`: ~75 MB (fastest, lowest accuracy)
  - `base`: ~145 MB
  - `small`: ~480 MB (**Default & Recommended**: good balance of accuracy for English and Hindi)
  - `medium`: ~1.5 GB (higher accuracy for accented speech and complex Hindi/Hinglish)
  - `large-v3`: ~3.1 GB (highest accuracy)

- **OpenAI Cloud API Transcription:**
  If you prefer to use the OpenAI Whisper API instead:
  ```env
  TRANSCRIBE_PROVIDER=openai
  OPENAI_API_KEY=sk-your-openai-api-key
  ```

---

### 3. Running the Pipeline via CLI

Execute the CLI from the project root using PowerShell:

```powershell
# Activate venv (if not already active)
.\.venv\Scripts\Activate.ps1

# Set PYTHONPATH to the backend folder
$env:PYTHONPATH="backend"

# 1. Fact-check typed text directly (no media file needed):
python -m app.cli --text "Drinking raw onion juice cures cancer in 48 hours."

# 2. Fact-check a transcript from a text file:
python -m app.cli --text-file "path\to\transcript.txt"

# 3. Analyze a local video or audio file:
python -m app.cli test_media\silent_3s.mp4

# 4. Run with --debug to see all filtered-out segments (silence, hallucinations, noise) and probability values:
python -m app.cli "path\to\your_audio.mp3" --debug

# 5. Output raw JSON:
python -m app.cli --text "Your text statement" --json

# 6. Analyze an Instagram Reel link:
python -m app.cli "https://www.instagram.com/reel/YOUR_REEL_ID/"

# 7. Extract transcript only without calling Gemini:
python -m app.cli "path\to\clip.mp4" --transcript-only
```

---

### 4. What Voice Activity Detection (`vad_filter=True`) Does

When running locally with `faster-whisper`, `vad_filter=True` activates Silero VAD (Voice Activity Detection).
- **What it does:** Scans the audio waveform to identify segments of real human vocal speech and automatically cuts out background music, ambient silence, and noise *before* passing the audio to the Whisper model.
- **Why it matters:** It stops Whisper from hallucinating text during silent or instrumental parts of a reel (e.g. producing random repetitive sentences) and speeds up processing time on clips with musical pauses.

---

### 5. Instagram URL Formats & Behavior

The pipeline supports public Instagram URLs with paths starting with:
- `/reel/` (standard Instagram reel)
- `/reels/` (reels gallery link)
- `/p/` (standard Instagram post; note: posts containing only images without an audio track will return a clean message indicating no audio stream was found)
- `/share/` (share links; yt-dlp automatically resolves the redirect target)

*Note on Instagram blocks:* Instagram frequently restricts automated media scraping without cookies. If yt-dlp cannot extract the audio from a link, the CLI cleanly raises `DOWNLOAD_BLOCKED` and instructs the user to upload the video or screen recording file directly.

---

### 6. Running Automated Tests

Run the test suite using `pytest`:

```powershell
$env:PYTHONPATH="backend"
pytest -v backend\tests\test_phase1.py
```
