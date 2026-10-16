"""Pipeline orchestration for audio extraction, transcription, and Gemini analysis."""

import asyncio
import logging
from pathlib import Path

from app.models import AnalysisResult, ReelMetadata, Transcript, TranscriptSegment
from app.pipeline.analyze import GeminiClient, analyze_reel, analyze_reel_async
from app.pipeline.download import get_audio, get_audio_from_file
from app.pipeline.transcribe import transcribe

logger = logging.getLogger(__name__)


def is_url(source: str) -> bool:
    """Check if the source string looks like a web URL."""
    s = source.strip().lower()
    return s.startswith("http://") or s.startswith("https://") or s.startswith("instagram.com") or s.startswith("www.instagram.com")


def get_transcript(source: str) -> tuple[Transcript, ReelMetadata]:
    """Execute the data pipeline: source -> audio extraction -> transcription.

    Always cleans up temporary audio files in a finally block.

    Args:
        source: Instagram URL or local media file path.

    Returns:
        tuple[Transcript, ReelMetadata]: Extracted transcript and metadata.
    """
    temp_audio_path: Path | None = None

    try:
        if is_url(source):
            logger.info("Processing Instagram URL: %s", source)
            temp_audio_path, metadata = get_audio(source)
        else:
            logger.info("Processing local media file: %s", source)
            temp_audio_path, metadata = get_audio_from_file(source)

        logger.info("Audio extracted to %s. Beginning transcription...", temp_audio_path)
        transcript = transcribe(temp_audio_path)
        return transcript, metadata

    finally:
        # Mandatory cleanup: delete temp audio file in all circumstances
        if temp_audio_path is not None and temp_audio_path.exists():
            try:
                temp_audio_path.unlink()
                logger.debug("Successfully cleaned up temporary audio: %s", temp_audio_path)
            except Exception as e:
                logger.warning("Failed to delete temporary audio %s: %s", temp_audio_path, str(e))


async def async_get_transcript(source: str) -> tuple[Transcript, ReelMetadata]:
    """Asynchronously execute audio extraction and transcription in a separate thread."""
    return await asyncio.to_thread(get_transcript, source)


def run_full_pipeline(source: str, client: GeminiClient | None = None) -> AnalysisResult:
    """Execute complete end-to-end pipeline: media extraction -> transcription -> 3-step fact check.

    Args:
        source: Instagram URL or local media file path.
        client: Optional pre-configured GeminiClient.

    Returns:
        AnalysisResult: Full orchestrated fact-check report.
    """
    transcript, metadata = get_transcript(source)
    return analyze_reel(transcript=transcript, metadata=metadata, client=client)


async def async_run_full_pipeline(source: str, client: GeminiClient | None = None) -> AnalysisResult:
    """Asynchronously execute full pipeline for FastAPI endpoints."""
    transcript, metadata = await async_get_transcript(source)
    return await analyze_reel_async(transcript=transcript, metadata=metadata, client=client)


def analyze_text(text: str, client: GeminiClient | None = None) -> AnalysisResult:
    """Directly analyze and fact-check a raw text string without requiring audio media.

    Args:
        text: Text statement or video transcript.
        client: Optional pre-configured GeminiClient.

    Returns:
        AnalysisResult: Full orchestrated fact-check report.
    """
    clean_text = text.strip()
    if not clean_text:
        from app.errors import InvalidInputError
        raise InvalidInputError("Text input cannot be empty.")

    words = clean_text.split()
    estimated_duration = max(3.0, round(len(words) / 2.5, 1))

    transcript = Transcript(
        text=clean_text,
        language="en",
        segments=[
            TranscriptSegment(
                start=0.0,
                end=estimated_duration,
                text=clean_text,
            )
        ],
    )
    metadata = ReelMetadata(
        source_url="text-input",
        caption=None,
        creator="Direct Text Input",
        upload_date=None,
        duration_seconds=estimated_duration,
    )
    return analyze_reel(transcript=transcript, metadata=metadata, client=client)
