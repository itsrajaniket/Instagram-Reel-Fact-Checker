"""Audio transcription module using OpenAI Whisper API with hallucination and silence filtering."""

import asyncio
import logging
import random
import re
import string
import time
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from app.config import settings
from app.errors import InvalidInputError, NoSpeechError
from app.models import Transcript, TranscriptSegment
from app.pipeline.download import extract_audio_from_media

logger = logging.getLogger(__name__)

# Constants
MAX_WHISPER_BYTES = 24 * 1024 * 1024  # 24 MB safety margin for 25 MB API limit
MIN_SPEECH_WORDS = 5
MAX_RETRIES = 3


def is_hallucination(text: str, hallucination_phrases: list[str]) -> bool:
    """Check if the transcribed segment text matches known Whisper silence hallucinations."""
    # Normalize text: lowercase and strip punctuation/whitespace
    normalized = text.lower().translate(str.maketrans("", "", string.punctuation)).strip()
    if not normalized:
        return True

    for phrase in hallucination_phrases:
        clean_phrase = phrase.lower().translate(str.maketrans("", "", string.punctuation)).strip()
        if clean_phrase and (clean_phrase in normalized or normalized == clean_phrase):
            return True

    return False


def filter_segments(
    raw_segments: list[Any],
    no_speech_threshold: float,
    logprob_threshold: float,
    hallucination_phrases: list[str],
) -> list[TranscriptSegment]:
    """Filter out silence, low-confidence noise, and hallucinated phrases from segments."""
    cleaned_segments: list[TranscriptSegment] = []

    for seg in raw_segments:
        # Extract attributes whether dict or Pydantic object
        text = (getattr(seg, "text", None) or seg.get("text", "")).strip()
        start = float(getattr(seg, "start", None) or seg.get("start", 0.0))
        end = float(getattr(seg, "end", None) or seg.get("end", 0.0))
        no_speech_prob = getattr(seg, "no_speech_prob", None)
        if no_speech_prob is None and isinstance(seg, dict):
            no_speech_prob = seg.get("no_speech_prob")

        avg_logprob = getattr(seg, "avg_logprob", None)
        if avg_logprob is None and isinstance(seg, dict):
            avg_logprob = seg.get("avg_logprob")

        # 1. Skip if text is empty
        if not text:
            continue

        # 2. Check no_speech_prob threshold
        if no_speech_prob is not None and float(no_speech_prob) > no_speech_threshold:
            logger.debug(
                "Filtered segment due to no_speech_prob (%.2f > %.2f): '%s'",
                float(no_speech_prob),
                no_speech_threshold,
                text,
            )
            continue

        # 3. Check combined low logprob + elevated no_speech_prob
        if (
            avg_logprob is not None
            and float(avg_logprob) < logprob_threshold
            and no_speech_prob is not None
            and float(no_speech_prob) > 0.4
        ):
            logger.debug(
                "Filtered segment due to low logprob (%.2f < %.2f): '%s'",
                float(avg_logprob),
                logprob_threshold,
                text,
            )
            continue

        # 4. Filter known silence hallucinations
        if is_hallucination(text, hallucination_phrases):
            logger.debug("Filtered hallucinated phrase segment: '%s'", text)
            continue

        cleaned_segments.append(
            TranscriptSegment(
                start=start,
                end=end,
                text=text,
                no_speech_prob=float(no_speech_prob) if no_speech_prob is not None else None,
                avg_logprob=float(avg_logprob) if avg_logprob is not None else None,
            )
        )

    return cleaned_segments


def ensure_size_limit(audio_path: Path) -> Path:
    """Check if the audio file exceeds 24MB, and compress if necessary."""
    file_size = audio_path.stat().st_size
    if file_size <= MAX_WHISPER_BYTES:
        return audio_path

    logger.warning("Audio file size (%d bytes) exceeds 24MB limit. Compressing...", file_size)
    compressed_path = audio_path.with_name(f"compressed_{audio_path.name}")
    extract_audio_from_media(audio_path, compressed_path)

    if compressed_path.stat().st_size > MAX_WHISPER_BYTES:
        compressed_path.unlink(missing_ok=True)
        raise InvalidInputError("Audio file exceeds the 25MB Whisper API limit even after compression.")

    return compressed_path


def transcribe(audio_path: Path | str) -> Transcript:
    """Transcribe an audio file using OpenAI Whisper API with retry and filtering.

    Args:
        audio_path: Path to the local MP3/audio file.

    Returns:
        Transcript: Cleaned transcript model with detected language and segments.

    Raises:
        NoSpeechError: If speech is missing, filtered out, or under 5 words.
        ValueError: If OPENAI_API_KEY is missing.
    """
    settings.validate_openai_key()
    path = Path(audio_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    # Ensure size is within limits
    usable_path = ensure_size_limit(path)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(usable_path, "rb") as audio_file:
                logger.info("Calling OpenAI Whisper API (attempt %d/%d)...", attempt, MAX_RETRIES)
                response = client.audio.transcriptions.create(
                    model=settings.WHISPER_MODEL,
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
            break
        except (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError) as e:
            last_error = e
            logger.warning("OpenAI API error on attempt %d: %s", attempt, str(e))
            if attempt < MAX_RETRIES:
                sleep_sec = (2**attempt) + random.uniform(0.1, 1.0)
                time.sleep(sleep_sec)
            else:
                raise
        except Exception as e:
            logger.error("OpenAI Whisper fatal error: %s", str(e))
            raise

    # Cleanup temporary compressed file if one was created
    if usable_path != path and usable_path.exists():
        usable_path.unlink(missing_ok=True)

    # Process segments from response
    raw_segments = getattr(response, "segments", None) or []
    cleaned_segments = filter_segments(
        raw_segments=raw_segments,
        no_speech_threshold=settings.NO_SPEECH_THRESHOLD,
        logprob_threshold=settings.LOGPROB_THRESHOLD,
        hallucination_phrases=settings.hallucination_phrases_list,
    )

    combined_text = " ".join(seg.text for seg in cleaned_segments).strip()
    words = combined_text.split()

    if len(words) < MIN_SPEECH_WORDS:
        raise NoSpeechError(
            f"No sufficient speech detected in audio ({len(words)} words found; minimum {MIN_SPEECH_WORDS} required). "
            "The reel may contain only background music, silence, or non-verbal sound."
        )

    detected_language = getattr(response, "language", None) or "unknown"

    return Transcript(
        text=combined_text,
        language=detected_language,
        segments=cleaned_segments,
    )


async def async_transcribe(audio_path: Path | str) -> Transcript:
    """Asynchronously transcribe audio in a background thread."""
    return await asyncio.to_thread(transcribe, audio_path)
