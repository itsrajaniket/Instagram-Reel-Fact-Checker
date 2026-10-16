"""Data models for Reel Fact Checker using Pydantic v2."""

from typing import Literal
from pydantic import BaseModel, Field


class ReelMetadata(BaseModel):
    """Metadata extracted from the video/reel source."""

    source_url: str | None = None
    caption: str | None = None
    creator: str | None = None
    upload_date: str | None = None
    duration_seconds: float = 0.0


class TranscriptSegment(BaseModel):
    """A segment of the transcript with timing and speech probability metrics."""

    start: float
    end: float
    text: str
    no_speech_prob: float | None = None
    avg_logprob: float | None = None


class FilteredSegment(BaseModel):
    """A discarded segment filtered out during silence, noise, or hallucination checks."""

    start: float
    end: float
    text: str
    reason: str
    no_speech_prob: float | None = None
    avg_logprob: float | None = None


class Transcript(BaseModel):
    """Complete transcript with detected language and segments."""

    text: str
    language: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
    filtered_segments: list[FilteredSegment] = Field(default_factory=list)


class Claim(BaseModel):
    """A factual claim extracted from transcript/caption."""

    id: int
    text: str
    timestamp: float | None = None  # seconds into the reel
    type: str = "other"  # e.g. statistic, health, political, event, scientific, other


class Source(BaseModel):
    """A grounding source reference URL and title."""

    title: str
    url: str


class ClaimVerdict(BaseModel):
    """Fact-check verification result for a single claim."""

    claim_id: int
    verdict: Literal["true", "false", "misleading", "unverified", "not_enough_evidence"]
    confidence: int = Field(ge=0, le=100)
    explanation: str
    sources: list[Source] = Field(default_factory=list)


class ClaimExtraction(BaseModel):
    """Step A extraction output from LLM."""

    summary: str
    tone: Literal["news", "educational", "opinion", "promotional", "clickbait", "satire", "rumor", "other"]
    red_flags: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Final orchestrated analysis result."""

    metadata: ReelMetadata
    transcript: Transcript
    summary: str
    tone: str
    red_flags: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    verdicts: list[ClaimVerdict] = Field(default_factory=list)
    background_story: str
    overall_verdict: Literal["mostly_true", "mixed", "mostly_false", "mostly_unverified", "no_checkable_claims"]
    overall_confidence: int = Field(ge=0, le=100)
    disclaimer: str
    cost_estimate_usd: float | None = None
    runtime_seconds: float = 0.0
