"""Custom domain exceptions for the Reel Fact Checker pipeline."""


class ReelCheckerError(Exception):
    """Base exception for all reel checker errors."""

    api_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, api_code: str | None = None):
        super().__init__(message)
        if api_code:
            self.api_code = api_code


class InvalidInputError(ReelCheckerError):
    """Raised when input URL or file type/size is invalid."""

    api_code: str = "INVALID_INPUT"


class DownloadBlockedError(ReelCheckerError):
    """Raised when yt-dlp fails or Instagram blocks audio extraction."""

    api_code: str = "DOWNLOAD_BLOCKED"


class DurationLimitError(ReelCheckerError):
    """Raised when media exceeds the maximum duration limit."""

    api_code: str = "TOO_LONG"


class NoSpeechError(ReelCheckerError):
    """Raised when audio contains no speech or only background music/silence."""

    api_code: str = "NO_SPEECH"


class AnalysisError(ReelCheckerError):
    """Raised when LLM analysis fails after retries."""

    api_code: str = "ANALYSIS_FAILED"


class JobTimeoutError(ReelCheckerError):
    """Raised when background job exceeds the maximum timeout."""

    api_code: str = "TIMEOUT"
