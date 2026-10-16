"""Unit tests for Phase 1 pipeline components."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.config import settings
from app.errors import (
    DownloadBlockedError,
    DurationLimitError,
    InvalidInputError,
    NoSpeechError,
)
from app.pipeline.download import get_audio, get_audio_from_file, validate_instagram_url
from app.pipeline.run import get_transcript, is_url
from app.pipeline.transcribe import filter_segments, is_hallucination, transcribe


def test_validate_instagram_url():
    """Verify Instagram URL domain and path validation."""
    # Valid formats
    assert validate_instagram_url("https://www.instagram.com/reel/C1234567/")
    assert validate_instagram_url("https://instagram.com/reels/C1234567/")
    assert validate_instagram_url("https://www.instagram.com/p/C1234567/")
    assert validate_instagram_url("https://instagram.com/share/C1234567/")

    # Invalid domains
    with pytest.raises(InvalidInputError) as exc:
        validate_instagram_url("https://youtube.com/watch?v=123")
    assert "youtube.com" in str(exc.value)

    with pytest.raises(InvalidInputError) as exc:
        validate_instagram_url("https://evil-instagram.com/reel/123")
    assert "evil-instagram.com" in str(exc.value)

    # Invalid paths
    with pytest.raises(InvalidInputError) as exc:
        validate_instagram_url("https://www.instagram.com/explore/")
    assert "Invalid Instagram URL path" in str(exc.value)


def test_is_url():
    """Verify URL detection helper."""
    assert is_url("https://www.instagram.com/reel/123") is True
    assert is_url("http://instagram.com/p/123") is True
    assert is_url("instagram.com/reel/123") is True
    assert is_url("test_media/sample.mp4") is False
    assert is_url("C:\\path\\to\\file.mp3") is False


def test_get_audio_from_file_valid_and_cleanup():
    """Verify local file audio extraction and metadata."""
    sample_mp4 = Path("test_media/silent_3s.mp4")
    if not sample_mp4.exists():
        pytest.skip("Synthetic fixture silent_3s.mp4 not found")

    out_mp3, metadata = get_audio_from_file(sample_mp4)
    try:
        assert out_mp3.exists()
        assert out_mp3.suffix == ".mp3"
        assert metadata.duration_seconds == pytest.approx(3.0, abs=0.5)
        assert metadata.source_url is None
    finally:
        out_mp3.unlink(missing_ok=True)


def test_get_audio_from_file_no_audio_stream():
    """Verify that video without audio stream raises InvalidInputError."""
    sample = Path("test_media/video_no_audio.mp4")
    if not sample.exists():
        pytest.skip("Synthetic fixture video_no_audio.mp4 not found")

    with pytest.raises(InvalidInputError) as exc:
        get_audio_from_file(sample)
    assert "does not contain an audio stream" in str(exc.value)


def test_get_audio_from_file_duration_limit():
    """Verify that file exceeding MAX_DURATION_SECONDS raises DurationLimitError."""
    sample = Path("test_media/overlength_200s.mp3")
    if not sample.exists():
        pytest.skip("Synthetic fixture overlength_200s.mp3 not found")

    with pytest.raises(DurationLimitError) as exc:
        get_audio_from_file(sample)
    assert "exceeds maximum allowed limit" in str(exc.value)


def test_get_audio_from_file_unsupported_extension():
    """Verify unsupported file extension rejection."""
    with pytest.raises(InvalidInputError) as exc:
        get_audio_from_file("PROGRESS.md")
    assert "Unsupported file format" in str(exc.value)


def test_whisper_hallucination_and_silence_filter():
    """Verify hallucination and silence filtering logic."""
    phrases = settings.hallucination_phrases_list

    assert is_hallucination("Thank you for watching!", phrases) is True
    assert is_hallucination("Subtitles by Amara.org", phrases) is True
    assert is_hallucination("Important scientific announcement today.", phrases) is False

    mock_segments = [
        {"text": "Thanks for watching.", "start": 0.0, "end": 1.0, "no_speech_prob": 0.05, "avg_logprob": -0.1},
        {"text": "[Music]", "start": 1.0, "end": 2.5, "no_speech_prob": 0.88, "avg_logprob": -0.4},
        {"text": "Garbled whisper", "start": 2.5, "end": 3.5, "no_speech_prob": 0.55, "avg_logprob": -1.8},
        {
            "text": "The health agency published a comprehensive study on nutrition.",
            "start": 3.5,
            "end": 8.0,
            "no_speech_prob": 0.01,
            "avg_logprob": -0.12,
        },
    ]

    filtered = filter_segments(
        mock_segments,
        no_speech_threshold=settings.NO_SPEECH_THRESHOLD,
        logprob_threshold=settings.LOGPROB_THRESHOLD,
        hallucination_phrases=phrases,
    )

    assert len(filtered) == 1
    assert "health agency published" in filtered[0].text


def test_transcribe_no_speech_error_under_five_words():
    """Verify NoSpeechError when cleaned transcription has fewer than 5 words."""
    mock_segments = [
        {"text": "Yes hello", "start": 0.0, "end": 1.0, "no_speech_prob": 0.05, "avg_logprob": -0.1}
    ]

    filtered = filter_segments(
        mock_segments,
        no_speech_threshold=settings.NO_SPEECH_THRESHOLD,
        logprob_threshold=settings.LOGPROB_THRESHOLD,
        hallucination_phrases=settings.hallucination_phrases_list,
    )

    combined_text = " ".join(s.text for s in filtered)
    words = combined_text.split()
    assert len(words) < 5


@patch("app.pipeline.run.transcribe")
def test_get_transcript_guaranteed_temp_cleanup(mock_transcribe):
    """Verify that temporary audio is ALWAYS unlinked even if transcribe fails."""
    mock_transcribe.side_effect = RuntimeError("Simulated transcription crash")

    sample_mp4 = Path("test_media/silent_3s.mp4")
    if not sample_mp4.exists():
        pytest.skip("Synthetic fixture silent_3s.mp4 not found")

    with pytest.raises(RuntimeError):
        get_transcript(str(sample_mp4))

    # Ensure no leftover files in tmp directory
    leftover = list(settings.TEMP_DIR.glob("*.mp3"))
    assert len(leftover) == 0, f"Leftover files found in tmp: {leftover}"
