"""Audio transcription module supporting local faster-whisper and OpenAI Whisper API."""

import asyncio
import logging
import random
import string
import time
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from app.config import settings
from app.errors import InvalidInputError, NoSpeechError
from app.models import FilteredSegment, Transcript, TranscriptSegment
from app.pipeline.download import extract_audio_from_media

logger = logging.getLogger(__name__)

# Constants
MAX_WHISPER_BYTES = 24 * 1024 * 1024  # 24 MB safety margin for 25 MB OpenAI API limit
MIN_SPEECH_WORDS = 5
MAX_RETRIES = 3

# Cache for local faster-whisper model instance to avoid reloading between calls
_cached_whisper_model: Any = None
_cached_model_key: tuple[str, str] | None = None


def is_hallucination(text: str, hallucination_phrases: list[str]) -> tuple[bool, str | None]:
    """Check if segment text matches known Whisper silence hallucinations.

    Returns:
        tuple[bool, str | None]: (is_match, matched_phrase)
    """
    normalized = text.lower().translate(str.maketrans("", "", string.punctuation)).strip()
    if not normalized:
        return True, "empty after normalization"

    for phrase in hallucination_phrases:
        clean_phrase = phrase.lower().translate(str.maketrans("", "", string.punctuation)).strip()
        if clean_phrase and (clean_phrase in normalized or normalized == clean_phrase):
            return True, phrase

    return False, None


def filter_segments(
    raw_segments: list[Any],
    no_speech_threshold: float,
    logprob_threshold: float,
    hallucination_phrases: list[str],
) -> tuple[list[TranscriptSegment], list[FilteredSegment]]:
    """Filter out silence, low-confidence noise, and hallucinated phrases.

    Returns:
        tuple: (list of accepted TranscriptSegment, list of rejected FilteredSegment)
    """
    accepted: list[TranscriptSegment] = []
    rejected: list[FilteredSegment] = []

    for seg in raw_segments:
        text = (getattr(seg, "text", None) or (seg.get("text") if isinstance(seg, dict) else "") or "").strip()
        start = float(getattr(seg, "start", None) or (seg.get("start") if isinstance(seg, dict) else 0.0) or 0.0)
        end = float(getattr(seg, "end", None) or (seg.get("end") if isinstance(seg, dict) else 0.0) or 0.0)

        no_speech_prob = getattr(seg, "no_speech_prob", None)
        if no_speech_prob is None and isinstance(seg, dict):
            no_speech_prob = seg.get("no_speech_prob")

        avg_logprob = getattr(seg, "avg_logprob", None)
        if avg_logprob is None and isinstance(seg, dict):
            avg_logprob = seg.get("avg_logprob")

        nsp_float = float(no_speech_prob) if no_speech_prob is not None else None
        logp_float = float(avg_logprob) if avg_logprob is not None else None

        # 1. Skip if text is empty
        if not text:
            rejected.append(
                FilteredSegment(
                    start=start,
                    end=end,
                    text="",
                    reason="empty text",
                    no_speech_prob=nsp_float,
                    avg_logprob=logp_float,
                )
            )
            continue

        # 2. Check no_speech_prob threshold
        if nsp_float is not None and nsp_float > no_speech_threshold:
            reason = f"no_speech_prob ({nsp_float:.2f} > {no_speech_threshold:.2f})"
            logger.debug("Filtered segment: '%s' [%s]", text, reason)
            rejected.append(
                FilteredSegment(
                    start=start,
                    end=end,
                    text=text,
                    reason=reason,
                    no_speech_prob=nsp_float,
                    avg_logprob=logp_float,
                )
            )
            continue

        # 3. Check combined low logprob + elevated no_speech_prob
        if (
            logp_float is not None
            and logp_float < logprob_threshold
            and nsp_float is not None
            and nsp_float > 0.4
        ):
            reason = f"low logprob ({logp_float:.2f} < {logprob_threshold:.2f}) and elevated no_speech_prob ({nsp_float:.2f} > 0.40)"
            logger.debug("Filtered segment: '%s' [%s]", text, reason)
            rejected.append(
                FilteredSegment(
                    start=start,
                    end=end,
                    text=text,
                    reason=reason,
                    no_speech_prob=nsp_float,
                    avg_logprob=logp_float,
                )
            )
            continue

        # 4. Filter known silence hallucinations
        matched, matched_phrase = is_hallucination(text, hallucination_phrases)
        if matched:
            reason = f"matched hallucination phrase '{matched_phrase}'"
            logger.debug("Filtered segment: '%s' [%s]", text, reason)
            rejected.append(
                FilteredSegment(
                    start=start,
                    end=end,
                    text=text,
                    reason=reason,
                    no_speech_prob=nsp_float,
                    avg_logprob=logp_float,
                )
            )
            continue

        accepted.append(
            TranscriptSegment(
                start=start,
                end=end,
                text=text,
                no_speech_prob=nsp_float,
                avg_logprob=logp_float,
            )
        )

    return accepted, rejected


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


def get_local_whisper_model(model_name: str, device: str) -> Any:
    """Retrieve or load cached local faster-whisper WhisperModel instance."""
    global _cached_whisper_model, _cached_model_key
    from faster_whisper import WhisperModel

    current_key = (model_name, device)
    if _cached_whisper_model is None or _cached_model_key != current_key:
        compute_type = "int8" if device.lower() == "cpu" else "default"
        logger.info(
            "Loading local faster-whisper model '%s' on %s (compute_type=%s)...",
            model_name,
            device,
            compute_type,
        )
        _cached_whisper_model = WhisperModel(
            model_size_or_path=model_name,
            device=device,
            compute_type=compute_type,
        )
        _cached_model_key = current_key

    return _cached_whisper_model


def transcribe_local(audio_path: Path) -> tuple[str, list[Any]]:
    """Run local transcription using faster-whisper with Silero VAD filter.

    vad_filter=True uses Silero VAD to detect and remove non-speech silence before Whisper inference,
    preventing hallucinated text on silent sections and speeding up processing.
    """
    model = get_local_whisper_model(
        model_name=settings.LOCAL_WHISPER_MODEL,
        device=settings.LOCAL_WHISPER_DEVICE,
    )

    logger.info(
        "Transcribing locally with faster-whisper ('%s' on %s, vad_filter=True)...",
        settings.LOCAL_WHISPER_MODEL,
        settings.LOCAL_WHISPER_DEVICE,
    )

    # vad_filter=True filters out silent/non-speech chunks before transcription
    # language=None enables automatic language detection (e.g. Hindi, English, Hinglish)
    segments_gen, info = model.transcribe(
        str(audio_path),
        vad_filter=True,
        language=None,
    )

    raw_segments = list(segments_gen)
    detected_language = info.language or "unknown"
    logger.info(
        "Local transcription complete. Detected language: '%s' (probability: %.2f), Segments: %d",
        detected_language,
        getattr(info, "language_probability", 0.0),
        len(raw_segments),
    )

    return detected_language, raw_segments


def transcribe_openai(audio_path: Path) -> tuple[str, list[Any]]:
    """Run transcription via OpenAI Whisper API."""
    settings.validate_openai_key()
    usable_path = ensure_size_limit(audio_path)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    last_error: Exception | None = None
    response = None

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
    if usable_path != audio_path and usable_path.exists():
        usable_path.unlink(missing_ok=True)

    raw_segments = getattr(response, "segments", None) or []
    detected_language = getattr(response, "language", None) or "unknown"

    return detected_language, raw_segments


def transcribe(audio_path: Path | str) -> Transcript:
    """Transcribe an audio file using either local faster-whisper or OpenAI API.

    Provider is controlled by TRANSCRIBE_PROVIDER ("local" or "openai").
    Applies silence, logprob, and hallucination filtering, and validates word count.

    Returns:
        Transcript: Standardized transcript model with detected language, accepted segments, and filtered segments.
    """
    path = Path(audio_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    provider = settings.TRANSCRIBE_PROVIDER.lower()
    if provider == "openai":
        detected_language, raw_segments = transcribe_openai(path)
    else:
        detected_language, raw_segments = transcribe_local(path)

    # Filter segments using shared criteria
    accepted_segments, rejected_segments = filter_segments(
        raw_segments=raw_segments,
        no_speech_threshold=settings.NO_SPEECH_THRESHOLD,
        logprob_threshold=settings.LOGPROB_THRESHOLD,
        hallucination_phrases=settings.hallucination_phrases_list,
    )

    combined_text = " ".join(seg.text for seg in accepted_segments).strip()
    words = combined_text.split()

    if len(words) < MIN_SPEECH_WORDS:
        raise NoSpeechError(
            f"No sufficient speech detected in audio ({len(words)} words found; minimum {MIN_SPEECH_WORDS} required). "
            "The reel may contain only background music, silence, or non-verbal sound."
        )

    return Transcript(
        text=combined_text,
        language=detected_language,
        segments=accepted_segments,
        filtered_segments=rejected_segments,
    )


async def async_transcribe(audio_path: Path | str) -> Transcript:
    """Asynchronously transcribe audio in a background thread."""
    return await asyncio.to_thread(transcribe, audio_path)
