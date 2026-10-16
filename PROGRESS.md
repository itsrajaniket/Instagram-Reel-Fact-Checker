# PROGRESS.md: Reel Checker

_Last updated: 2026-10-17 00:46_

## 🎯 Current Status
- **Current phase:** Phase 1: Pipeline CLI (link/file → transcript)
- **Current task:** Phase 1 complete; waiting for user verification & approval
- **Overall completion:** 1 of 6 phases done
- **Waiting on me?** Yes: Please review Phase 1, insert your `OPENAI_API_KEY` into `.env`, test with your sample files/URLs, and approve to proceed to Phase 2.

## 📊 Phase Overview
| Phase | Name | Status | Started | Finished |
|---|---|---|---|---|
| 1 | Pipeline CLI (link/file → transcript) | DONE | 2026-10-17 | 2026-10-17 |
| 2 | Analysis engine (Gemini) | NOT STARTED | | |
| 3 | Test harness & prompt tuning | NOT STARTED | | |
| 4 | Async API (FastAPI) | NOT STARTED | | |
| 5 | Frontend (Next.js) | NOT STARTED | | |
| 6 | Hardening & deployment | NOT STARTED | | |

Status values: NOT STARTED / IN PROGRESS / DONE / BLOCKED / WAITING FOR APPROVAL

## ✅ Task Checklist
### Phase 1
- [x] 1.1 Scaffolding (.gitignore, .env.example, .env, PROGRESS.md, target directories)
- [x] 1.2 Config (config.py with typed settings, Whisper filters: no-speech threshold, avg_logprob, hallucination list)
- [x] 1.3 Models and errors (models.py with Pydantic v2 and errors.py with custom exception hierarchy)
- [x] 1.4 download.py: get_audio(url) using yt-dlp Python API, Instagram URL validation (/reel/, /reels/, /p/, /share/), metadata extraction, duration pre-check, clean error handling
- [x] 1.5 download.py: get_audio_from_file(path) using ffprobe/ffmpeg with audio stream verification, duration check
- [x] 1.6 transcribe.py: transcribe(audio_path) using OpenAI Whisper API, segment timestamps, configurable hallucination & no-speech filtering, avg_logprob, retry backoff
- [x] 1.7 pipeline/run.py: get_transcript(source) orchestrator with guaranteed temp cleanup in finally block
- [x] 1.8 cli.py: CLI interface with formatted display and --json output
- [x] 1.9 Docs & tests: requirements.txt, synthetic fixtures in test_media/, pytest suite, README.md with PowerShell instructions

## 🧠 Decisions & Deviations
| Date | Decision | Why |
|---|---|---|
| 2026-10-17 | FFmpeg installation via WinGet | Installed Gyan.FFmpeg version 9.0.2 to local machine; added auto-discovery of WinGet FFmpeg binaries in `get_ffmpeg_paths()` so processes never fail even before terminal restart. |
| 2026-10-17 | Configurable Whisper filtering in .env | Exposed `NO_SPEECH_THRESHOLD=0.6`, `LOGPROB_THRESHOLD=-1.0`, and `HALLUCINATION_PHRASES` so user can tune thresholds in Phase 3 without code edits. |
| 2026-10-17 | Comma-separated or JSON list for `HALLUCINATION_PHRASES` | Supported both comma-separated phrases and JSON array formatting to avoid dotenv parsing crashes in pydantic-settings. |
| 2026-10-17 | Supported `/p/` and `/share/` Instagram paths | yt-dlp extracts audio from video posts and follows `/share/` redirects. If a `/p/` post is a photo without audio, code detects missing audio stream and warns cleanly. |
| 2026-10-17 | Synthetic test media in `test_media/` | Created 3s silence, 200s overlength audio, and video-without-audio fixtures using ffmpeg lavfi without downloading copyrighted web content. |

## ⚠️ Problems, Blockers & Questions for Me
| Date | Issue | Status | Resolution |
|---|---|---|---|
| 2026-10-17 | FFmpeg not on Windows PATH initially | RESOLVED | Installed via `winget install Gyan.FFmpeg`; confirmed v9.0.2 working and configured fallback detection in code. |
| 2026-10-17 | OPENAI_API_KEY required for real transcription | PENDING USER | Scaffolding complete; user will paste key in `.env` for real Whisper API runs. |

## 📁 Files Created / Changed
| File | Phase | What it does |
|---|---|---|
| PROGRESS.md | 1 | Master progress tracking document |
| .gitignore | 1 | Ignores `.env`, `tmp/`, `cache/`, `test_media/`, `.venv/`, `__pycache__/` |
| .env.example | 1 | Environment configuration template |
| .env | 1 | Environment file for user secrets |
| backend/requirements.txt | 1 | Pinned backend dependencies |
| backend/app/__init__.py | 1 | Application package initialization |
| backend/app/errors.py | 1 | Custom domain exceptions (InvalidInputError, DownloadBlockedError, DurationLimitError, NoSpeechError, AnalysisError, JobTimeoutError) |
| backend/app/models.py | 1 | Pydantic v2 schemas (ReelMetadata, TranscriptSegment, Transcript, Claim, ClaimVerdict, etc.) |
| backend/app/config.py | 1 | Typed settings loading with dynamic FFmpeg path resolution |
| backend/app/pipeline/__init__.py | 1 | Pipeline package initialization |
| backend/app/pipeline/download.py | 1 | yt-dlp and ffmpeg/ffprobe audio extraction with async wrappers |
| backend/app/pipeline/transcribe.py | 1 | OpenAI Whisper verbose_json transcription with silence/hallucination filtering |
| backend/app/pipeline/run.py | 1 | Orchestrates URL/file detection, download, transcribe, and guaranteed cleanup |
| backend/app/cli.py | 1 | Command-line interface with Rich formatting and `--json` support |
| backend/tests/test_phase1.py | 1 | Pytest suite with 9 unit tests covering all Phase 1 edge cases |
| README.md | 1 | Setup and usage documentation for Windows PowerShell |

## 🧪 Test Results
| Date | Phase | What was tested | Result | Notes |
|---|---|---|---|---|
| 2026-10-17 | 1 | WinGet FFmpeg installation & version | PASSED | ffmpeg version 9.0.2 and ffprobe version 9.0.2 verified |
| 2026-10-17 | 1 | Virtual environment & dependencies | PASSED | All dependencies installed cleanly into `.venv` |
| 2026-10-17 | 1 | Config loading and hallucination parser | PASSED | Loaded defaults and correctly parsed phrase list |
| 2026-10-17 | 1 | URL validation (valid / invalid domain & path) | PASSED | Allowed reel/reels/p/share; blocked youtube and evil domains |
| 2026-10-17 | 1 | Audio extraction from MP4 | PASSED | Extracted 3.0s MP3 to tmp/ and verified duration |
| 2026-10-17 | 1 | Video without audio stream detection | PASSED | Raised `InvalidInputError` as expected |
| 2026-10-17 | 1 | Media duration limit (>180s) enforcement | PASSED | Raised `DurationLimitError` on 200s audio fixture |
| 2026-10-17 | 1 | Blocked / non-existent Instagram URL | PASSED | Caught yt-dlp error and raised `DownloadBlockedError` |
| 2026-10-17 | 1 | Whisper hallucination & silence filtering | PASSED | Filtered high no-speech prob and hallucinated phrases |
| 2026-10-17 | 1 | Minimum 5 words speech threshold | PASSED | Rejects transcripts under 5 words with `NoSpeechError` |
| 2026-10-17 | 1 | Temp file cleanup in `finally` block | PASSED | `tmp/` has 0 leftover files across all success and error runs |
| 2026-10-17 | 1 | Pytest test suite (9 tests) | PASSED | 9 of 9 unit tests passed in 1.67s |

## 📝 Activity Log (newest first)
- 2026-10-17 00:46: Phase 1 complete. Implemented download, transcription, pipeline runner, CLI, synthetic fixtures, pytest test suite, and README.md. All tests passing.
- 2026-10-17 00:36: Installed Gyan.FFmpeg v9.0.2 via winget, created .venv, installed requirements.
- 2026-10-17 00:31: Started Phase 1. Initialized PROGRESS.md and started environment setup.

## ▶️ Next Steps
1. User tests Phase 1 with their own `OPENAI_API_KEY` and audio/video files.
2. User provides approval to start Phase 2 (Analysis Engine with Gemini).

## 🔧 How to Run (keep this up to date)
```powershell
# 1. Activate environment in PowerShell:
.\.venv\Scripts\Activate.ps1

# 2. Run automated unit test suite:
$env:PYTHONPATH="backend"
pytest -v backend\tests\test_phase1.py

# 3. Test CLI with local media:
python -m app.cli test_media\silent_3s.mp4

# 4. Test CLI with Instagram link:
python -m app.cli "https://www.instagram.com/reel/YOUR_REEL_ID/"
```
