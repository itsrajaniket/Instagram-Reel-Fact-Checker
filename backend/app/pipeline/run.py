"""Pipeline orchestration for audio extraction and transcription."""

import asyncio
import logging
from pathlib import Path

from app.models import ReelMetadata, Transcript
from app.pipeline.download import get_audio, get_audio_from_file
from app.pipeline.transcribe import transcribe

logger = logging.getLogger(__name__)


def is_url(source: str) -> bool:
    """Check if the source string looks like a web URL."""
    s = source.strip().lower()
    return s.startswith("http://") or s.startswith("https://") or s.startswith("instagram.com") or s.startswith("www.instagram.com")


def get_transcript(source: str) -> tuple[Transcript, ReelMetadata]:
    """Execute the pipeline: source -> audio extraction -> transcription.

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
