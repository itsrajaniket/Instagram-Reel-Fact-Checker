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

# 3. Install backend dependencies
pip install -r backend\requirements.txt

# 4. Configure environment variables
# Copy .env.example to .env if not already created
Copy-Item .env.example .env
```

Open `.env` and enter your OpenAI API key:
```env
OPENAI_API_KEY=your_actual_openai_api_key_here
```

---

### 3. Running the Pipeline via CLI

Execute the CLI from the project root using PowerShell:

```powershell
# Activate venv (if not already active)
.\.venv\Scripts\Activate.ps1

# Set PYTHONPATH to the backend folder
$env:PYTHONPATH="backend"

# Analyze a local video or audio file:
python -m app.cli test_media\silent_3s.mp4

# Output raw JSON:
python -m app.cli test_media\silent_3s.mp4 --json

# Analyze an Instagram Reel link:
python -m app.cli "https://www.instagram.com/reel/YOUR_REEL_ID/"
```

---

### 4. Instagram URL Formats & Behavior

The pipeline supports public Instagram URLs with paths starting with:
- `/reel/` (standard Instagram reel)
- `/reels/` (reels gallery link)
- `/p/` (standard Instagram post; note: posts containing only images without an audio track will return a clean message indicating no audio stream was found)
- `/share/` (share links; yt-dlp automatically resolves the redirect target)

*Note on Instagram blocks:* Instagram frequently restricts automated media scraping without cookies. If yt-dlp cannot extract the audio from a link, the CLI cleanly raises `DOWNLOAD_BLOCKED` and instructs the user to upload the video or screen recording file directly.

---

### 5. Running Automated Tests

Run the test suite using `pytest`:

```powershell
$env:PYTHONPATH="backend"
pytest -v backend\tests\test_phase1.py
```
