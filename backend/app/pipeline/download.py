"""Download and audio extraction pipeline module."""

import asyncio
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from app.config import settings
from app.errors import (
    DownloadBlockedError,
    DurationLimitError,
    InvalidInputError,
)
from app.models import ReelMetadata

logger = logging.getLogger(__name__)

SUPPORTED_FILE_EXTENSIONS = {".mp4", ".mov", ".mp3", ".m4a", ".wav"}


def get_ffmpeg_paths() -> tuple[str, str]:
    """Resolve ffmpeg and ffprobe executable paths, searching PATH and local WinGet packages."""
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")

    if not ffmpeg_bin or not ffprobe_bin:
        # Search common WinGet install directory on Windows
        pattern = os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\**\bin\ffmpeg.exe"
        )
        matches = glob.glob(pattern, recursive=True)
        if matches:
            found_dir = os.path.dirname(matches[0])
            if found_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = found_dir + os.pathsep + os.environ.get("PATH", "")
            ffmpeg_bin = ffmpeg_bin or os.path.join(found_dir, "ffmpeg.exe")
            ffprobe_bin = ffprobe_bin or os.path.join(found_dir, "ffprobe.exe")

    if not ffmpeg_bin or not os.path.exists(ffmpeg_bin):
        raise FileNotFoundError(
            "ffmpeg was not found on your system. Please install ffmpeg and ensure it is on PATH."
        )
    if not ffprobe_bin or not os.path.exists(ffprobe_bin):
        raise FileNotFoundError(
            "ffprobe was not found on your system. Please install ffprobe and ensure it is on PATH."
        )

    return ffmpeg_bin, ffprobe_bin


def validate_instagram_url(url: str) -> str:
    """Validate that the URL belongs to Instagram and targets a reel/post/share.

    Allowed paths: /reel/, /reels/, /p/, /share/
    """
    if not url or not isinstance(url, str):
        raise InvalidInputError("URL must be a non-empty string.")

    cleaned_url = url.strip()
    parsed = urlparse(cleaned_url)
    hostname = (parsed.hostname or "").lower()

    if hostname not in ("instagram.com", "www.instagram.com"):
        raise InvalidInputError(
            f"Invalid URL domain '{hostname}'. Only instagram.com links are supported."
        )

    path = parsed.path
    if not re.match(r"^/(reel|reels|p|share)/", path, re.IGNORECASE):
        raise InvalidInputError(
            f"Invalid Instagram URL path '{path}'. Expected path starting with /reel/, /reels/, /p/, or /share/."
        )

    return cleaned_url


def probe_file(file_path: Path) -> dict:
    """Probe media file using ffprobe and return parsed JSON metadata."""
    _, ffprobe_bin = get_ffmpeg_paths()

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(file_path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("ffprobe failed on file %s: %s", file_path, e.stderr)
        raise InvalidInputError(f"Unable to read media file metadata: {e.stderr.strip()}")
    except Exception as e:
        logger.error("ffprobe execution error on %s: %s", file_path, str(e))
        raise InvalidInputError(f"Failed to inspect media file: {str(e)}")


def extract_audio_from_media(input_path: Path, output_mp3_path: Path) -> None:
    """Convert any supported media file to mono 16kHz MP3 using ffmpeg."""
    ffmpeg_bin, _ = get_ffmpeg_paths()

    cmd = [
        ffmpeg_bin,
        "-i",
        str(input_path),
        "-vn",  # disable video
        "-acodec",
        "libmp3lame",
        "-ac",
        "1",  # mono
        "-ar",
        "16000",  # 16kHz sample rate for speech
        "-y",  # overwrite output
        str(output_mp3_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg audio extraction failed: %s", e.stderr)
        raise InvalidInputError(f"Failed to extract audio from media: {e.stderr.strip()}")


def get_audio(url: str) -> tuple[Path, ReelMetadata]:
    """Download audio from an Instagram URL using the yt-dlp Python API.

    Returns:
        tuple[Path, ReelMetadata]: Path to the extracted mp3 file and metadata.
    """
    valid_url = validate_instagram_url(url)
    ffmpeg_bin, _ = get_ffmpeg_paths()
    ffmpeg_dir = os.path.dirname(ffmpeg_bin)

    unique_id = uuid.uuid4().hex
    temp_target_base = settings.TEMP_DIR / unique_id
    expected_mp3_path = settings.TEMP_DIR / f"{unique_id}.mp3"

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": f"{temp_target_base}.%(ext)s",
        "ffmpeg_location": ffmpeg_dir,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 1. Pre-check duration without downloading
            try:
                info = ydl.extract_info(valid_url, download=False)
            except Exception as e:
                logger.warning("yt-dlp extract_info failed: %s", str(e))
                raise DownloadBlockedError(
                    f"Instagram blocked the audio download ({str(e)}). "
                    "Please upload the video or screen recording directly instead."
                ) from e

            if not info:
                raise DownloadBlockedError(
                    "Instagram blocked the audio download (no media information returned). "
                    "Please upload the video file directly."
                )

            duration = info.get("duration") or 0.0
            if duration and duration > settings.MAX_DURATION_SECONDS:
                raise DurationLimitError(
                    f"Reel duration ({duration:.1f}s) exceeds maximum allowed limit ({settings.MAX_DURATION_SECONDS}s)."
                )

            # Check if this Instagram post has no audio/video streams (e.g. photos/carousel)
            formats = info.get("formats") or []
            has_audio = any(f.get("acodec") != "none" or f.get("audio_channels") for f in formats)
            # If formats are listed but none have audio, report clearly
            if formats and not has_audio and not info.get("url"):
                raise DownloadBlockedError(
                    "This Instagram post does not contain any audio stream (it may be a photo or image carousel). "
                    "Please select a video reel or upload an audio/video file."
                )

            # 2. Download audio
            ydl.download([valid_url])

            if not expected_mp3_path.exists() or expected_mp3_path.stat().st_size == 0:
                raise DownloadBlockedError(
                    "Audio extraction failed to produce an MP3 file. "
                    "Instagram may have restricted this content. Please upload the file directly."
                )

            metadata = ReelMetadata(
                source_url=valid_url,
                caption=info.get("description") or info.get("title"),
                creator=info.get("uploader") or info.get("channel") or info.get("uploader_id"),
                upload_date=info.get("upload_date"),
                duration_seconds=float(duration),
            )

            return expected_mp3_path, metadata

    except (InvalidInputError, DurationLimitError, DownloadBlockedError):
        # Re-raise domain errors untouched
        raise
    except Exception as e:
        logger.error("Unexpected error downloading reel %s: %s", valid_url, str(e))
        raise DownloadBlockedError(
            f"Instagram blocked the audio download ({str(e)}). "
            "Please upload the video or screen recording directly instead."
        ) from e


def get_audio_from_file(path: Path | str) -> tuple[Path, ReelMetadata]:
    """Verify local video/audio file and extract mono MP3 audio into TEMP_DIR.

    Returns:
        tuple[Path, ReelMetadata]: Path to the extracted mp3 file and metadata.
    """
    file_path = Path(path).resolve()
    if not file_path.exists() or not file_path.is_file():
        raise InvalidInputError(f"Input file not found: {file_path}")

    # Check extension
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_FILE_EXTENSIONS:
        raise InvalidInputError(
            f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(SUPPORTED_FILE_EXTENSIONS))}."
        )

    # Check file size limit
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise InvalidInputError(
            f"File size ({size_mb:.1f} MB) exceeds maximum allowed limit of {settings.MAX_UPLOAD_MB} MB."
        )

    # Probe file with ffprobe
    probe_data = probe_file(file_path)

    # Verify audio stream exists
    streams = probe_data.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not has_audio:
        raise InvalidInputError("The uploaded file does not contain an audio stream.")

    # Check duration
    duration = None
    if "format" in probe_data and "duration" in probe_data["format"]:
        try:
            duration = float(probe_data["format"]["duration"])
        except (ValueError, TypeError):
            pass

    if duration is None:
        for s in streams:
            if s.get("codec_type") == "audio" and "duration" in s:
                try:
                    duration = float(s["duration"])
                    break
                except (ValueError, TypeError):
                    pass

    duration = duration or 0.0
    if duration > settings.MAX_DURATION_SECONDS:
        raise DurationLimitError(
            f"File duration ({duration:.1f}s) exceeds maximum allowed limit ({settings.MAX_DURATION_SECONDS}s)."
        )

    # Extract audio to unique MP3 in TEMP_DIR
    unique_id = uuid.uuid4().hex
    output_mp3_path = settings.TEMP_DIR / f"{unique_id}.mp3"
    extract_audio_from_media(file_path, output_mp3_path)

    metadata = ReelMetadata(
        source_url=None,
        caption=None,
        creator=None,
        upload_date=None,
        duration_seconds=duration,
    )

    return output_mp3_path, metadata


# Async wrappers for non-blocking execution in FastAPI / async contexts
async def async_get_audio(url: str) -> tuple[Path, ReelMetadata]:
    """Asynchronously download audio from an Instagram URL in a separate thread."""
    return await asyncio.to_thread(get_audio, url)


async def async_get_audio_from_file(path: Path | str) -> tuple[Path, ReelMetadata]:
    """Asynchronously extract audio from a local media file in a separate thread."""
    return await asyncio.to_thread(get_audio_from_file, path)
