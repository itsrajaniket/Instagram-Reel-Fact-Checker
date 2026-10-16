# PROGRESS.md: Reel Checker

_Last updated: 2026-10-17 01:14_

## 🎯 Current Status
- **Current phase:** Phase 2: Analysis Engine (Gemini)
- **Current task:** Phase 2 implemented and verified; waiting for user verification & approval
- **Overall completion:** 2 of 6 phases done
- **Waiting on me?** Yes: Please review Phase 2 findings, add your `GEMINI_API_KEY` to `.env` to test live Gemini fact-checking, and approve to proceed to Phase 3.

## 📊 Phase Overview
| Phase | Name | Status | Started | Finished |
|---|---|---|---|---|
| 1 | Pipeline CLI (link/file → transcript) | DONE | 2026-10-17 | 2026-10-17 |
| 2 | Analysis engine (Gemini) | DONE | 2026-10-17 | 2026-10-17 |
| 3 | Test harness & prompt tuning | NOT STARTED | | |
| 4 | Async API (FastAPI) | NOT STARTED | | |
| 5 | Frontend (Next.js) | NOT STARTED | | |
| 6 | Hardening & deployment | NOT STARTED | | |

Status values: NOT STARTED / IN PROGRESS / DONE / BLOCKED / WAITING FOR APPROVAL

## ✅ Task Checklist
### Phase 1
- [x] 1.1 Scaffolding (.gitignore, .env.example, .env, PROGRESS.md, target directories)
- [x] 1.2 Config (config.py with typed settings, Whisper filters: no-speech threshold, avg_logprob, hallucination list, provider selection)
- [x] 1.3 Models and errors (models.py with Pydantic v2 and errors.py with custom exception hierarchy)
- [x] 1.4 download.py: get_audio(url) using yt-dlp Python API, Instagram URL validation (/reel/, /reels/, /p/, /share/), metadata extraction, duration pre-check, clean error handling
- [x] 1.5 download.py: get_audio_from_file(path) using ffprobe/ffmpeg with audio stream verification, duration check
- [x] 1.6 transcribe.py: dual provider support (faster-whisper local with Silero VAD vs OpenAI Whisper API), segment timestamps, configurable hallucination & no-speech filtering, avg_logprob, retry backoff
- [x] 1.7 pipeline/run.py: get_transcript(source) orchestrator with guaranteed temp cleanup in finally block
- [x] 1.8 cli.py: CLI interface with formatted display, --json output, and --debug flag for discarded segment inspection
- [x] 1.9 Docs & tests: requirements.txt, synthetic fixtures in test_media/, pytest suite (10 tests), README.md with PowerShell instructions

### Phase 2
- [x] 2.1 Gemini API & Search Grounding checks (confirmed `google-genai` SDK, free tier 10-15 RPM limits, and two-call search+schema architecture)
- [x] 2.2 LLM wrapper (`GeminiClient`, `UsageTracker`, exponential backoff on 429/5xx, prompt/candidate token tracking, and search query counts)
- [x] 2.3 Step A: Claim extraction (Pydantic `ClaimExtraction` schema, prompt injection defense, max 4 claims by default)
- [x] 2.4 Step B: Verification (Google Search grounding with sources extracted directly from `grounding_chunks`; hard rules in code: zero sources -> `not_enough_evidence`, confidence clamped 0-100, explanation truncated to 2 sentences)
- [x] 2.5 Step C: Synthesis (background story only from findings, deterministic code-governed overall verdict and confidence)
- [x] 2.6 Prompt-injection protection (delimiters `<transcript-data>`, `<caption-data>`, explicit system prompts marking inputs as untrusted)
- [x] 2.7 Validation & error handling (`AnalysisError`, schema retries)
- [x] 2.8 Orchestrator (`run_full_pipeline` and `async_run_full_pipeline` with cost and runtime tracking)
- [x] 2.9 CLI (`app.cli` with overall verdict badges, summary, background story, claims cards, clickable source links, disclaimer, and usage stats)

## 🧠 Decisions & Deviations
| Date | Decision | Why |
|---|---|---|
| 2026-10-17 | Gemini Two-Call Step B Architecture | Gemini API returns 400 when combining dynamic tools (Google Search grounding) directly with strict JSON `response_schema`. Call 1 uses Google Search for research and sources; Call 2 parses the research into strict JSON. |
| 2026-10-17 | Free Tier Quota Safeguards (`MAX_CLAIMS=4`) | Free tier has 10–15 RPM and 250–500 RPD. Lowering `MAX_CLAIMS` to 4 keeps total API calls per reel under 10 and prevents exceeding the RPM limit. |
| 2026-10-17 | Code-Level Hard Rules in Step B | If zero sources are found in grounding metadata, code automatically overrides LLM to `not_enough_evidence` with confidence <= 40 to eliminate ungrounded hallucinations. |
| 2026-10-17 | Deterministic Code Logic for Overall Verdict | Overall verdict is calculated with mathematical thresholds (false/misleading >= 50% -> `mostly_false`, etc.) rather than letting LLM guess the final verdict. |
| 2026-10-17 | Free local transcription via `faster-whisper` | Allowed testing without paying for OpenAI API; enabled Silero VAD (`vad_filter=True`) to trim non-speech silence before Whisper inference. Configurable via `TRANSCRIBE_PROVIDER=local` (default). |
| 2026-10-17 | Added `--debug` flag to CLI | Displays a detailed table of every discarded segment showing timestamps, text, reason, `no_speech_prob`, and `avg_logprob`. |

## ⚠️ Problems, Blockers & Questions for Me
| Date | Issue | Status | Resolution |
|---|---|---|---|
| 2026-10-17 | Gemini API Free Tier limits | DOCUMENTED | Gemini 2.5 Flash free tier has 10-15 RPM, 250k TPM, 250-500 RPD. Set MAX_CLAIMS=4 and capped concurrency to 3 to stay within limits. |
| 2026-10-17 | GEMINI_API_KEY required for live fact-checking | PENDING USER | Code and test suite ready; user will add `GEMINI_API_KEY` to `.env` to test live Gemini runs. |

## 📁 Files Created / Changed
| File | Phase | What it does |
|---|---|---|
| PROGRESS.md | 2 | Master progress tracking document |
| backend/app/config.py | 2 | Added MAX_CLAIMS=4, token cost constants, and GEMINI_API_KEY validation |
| backend/app/pipeline/analyze.py | 2 | 3-step Gemini analysis engine with Google Search grounding, token/cost tracking, and hard rules |
| backend/app/pipeline/run.py | 2 | Added `run_full_pipeline` and `async_run_full_pipeline` |
| backend/app/cli.py | 2 | Rich fact check analysis report with verdict banners, claims cards, sources, and stats |
| backend/tests/test_phase2.py | 2 | Unit tests covering usage tracking, sentence truncation, verdict logic, zero-source rule, and injection safety |
| .env.example | 2 | Updated with MAX_CLAIMS=4 |
| .env | 2 | Updated with MAX_CLAIMS=4 |

## 🧪 Test Results
| Date | Phase | What was tested | Result | Notes |
|---|---|---|---|---|
| 2026-10-17 | 2 | Usage tracker & cost calculation | PASSED | Token math matches Gemini 2.5 Flash pricing |
| 2026-10-17 | 2 | Sentence truncation helper | PASSED | Truncates to at most 2 sentences preserving punctuation |
| 2026-10-17 | 2 | Deterministic overall verdict logic | PASSED | Correctly computes mostly_true, mostly_false, unverified, and no_checkable_claims |
| 2026-10-17 | 2 | Step B zero-sources hard rule | PASSED | Forces `not_enough_evidence` and confidence <= 40 when no sources returned |
| 2026-10-17 | 2 | Step B confidence clamping & truncation | PASSED | Clamps confidence to 0-100 and truncates explanation to 2 sentences |
| 2026-10-17 | 2 | Step A prompt-injection safety | PASSED | Delimiters and untrusted system prompt prevent instruction override |
| 2026-10-17 | 2 | Step A JSON retry on invalid response | PASSED | Successfully retries with repair prompt on malformed JSON |
| 2026-10-17 | 2 | Pytest full test suite (17 tests) | PASSED | All 17 tests passed in 2.12s |

## 📝 Activity Log (newest first)
- 2026-10-17 01:14: Phase 2 complete. Implemented GeminiClient with usage/cost tracking, Step A extraction, Step B parallel search grounding, Step C synthesis, deterministic verdict logic, and full CLI reporting. All 17 unit tests passing.
- 2026-10-17 01:02: Added free local transcription via faster-whisper with Silero VAD, conditional key checks, and `--debug` flag.
- 2026-10-17 00:46: Phase 1 complete. Implemented download, transcription, pipeline runner, CLI, synthetic fixtures, pytest test suite, and README.md.

## ▶️ Next Steps
1. User adds `GEMINI_API_KEY` to `.env`.
2. User tests live fact-checking CLI on sample video/audio clips or Instagram links.
3. User approves to continue to Phase 3 (Test Harness & Prompt Tuning).

## 🔧 How to Run (keep this up to date)
```powershell
# 1. Activate environment in PowerShell:
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="backend"

# 2. Run automated test suite:
pytest -v backend\tests\

# 3. Run full fact-check analysis:
python -m app.cli "path\to\clip.mp4"

# 4. Run transcript only (skip Gemini):
python -m app.cli "path\to\clip.mp4" --transcript-only

# 5. Output raw JSON:
python -m app.cli "path\to\clip.mp4" --json
```
