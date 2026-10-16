"""Command Line Interface for Reel Fact Checker."""

import argparse
import json
import logging
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.errors import ReelCheckerError
from app.pipeline.run import get_transcript, run_full_pipeline

# Configure root logging for CLI: warnings/errors by default unless verbose/debug
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def format_timestamp(seconds: float | None) -> str:
    """Format seconds into [mm:ss] timestamp format."""
    if seconds is None:
        return "[--:--]"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{mins:02d}:{secs:02d}]"


def get_verdict_style(verdict: str) -> str:
    """Return Rich style/color for a given verdict."""
    v = verdict.lower()
    if v in ("mostly_true", "true"):
        return "bold green"
    elif v in ("mostly_false", "false"):
        return "bold red"
    elif v in ("mixed", "misleading"):
        return "bold yellow"
    elif v in ("mostly_unverified", "unverified", "not_enough_evidence"):
        return "bold cyan"
    return "bold magenta"


def main() -> None:
    """CLI entry point for Reel Fact Checker."""
    parser = argparse.ArgumentParser(
        description="Fact-check an Instagram Reel URL or local media file using Gemini AI & Search Grounding."
    )
    parser.add_argument(
        "source",
        help="Instagram reel URL (e.g. https://www.instagram.com/reel/...) or path to local media file (mp4, mov, mp3, m4a, wav)",
    )
    parser.add_argument(
        "--transcript-only",
        action="store_true",
        help="Only extract audio and transcribe without running Gemini fact-checking",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable detailed informational logging",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show detailed debug info including filtered-out speech segments",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    console = Console()

    try:
        if args.transcript_only:
            # Phase 1 Transcript-only mode
            transcript, metadata = get_transcript(args.source)
            if args.json:
                result = {
                    "metadata": metadata.model_dump(),
                    "transcript": transcript.model_dump(),
                }
                print(json.dumps(result, indent=2, ensure_ascii=False))
                sys.exit(0)

            console.print()
            console.print(Panel.fit("[bold cyan]Reel Fact Checker - Transcript Only[/bold cyan]", border_style="cyan"))

            meta_table = Table(title="[bold]Media Metadata[/bold]", show_header=True, header_style="bold magenta")
            meta_table.add_column("Property", style="cyan", width=18)
            meta_table.add_column("Value", style="white")
            meta_table.add_row("Source", metadata.source_url or args.source)
            meta_table.add_row("Duration", f"{metadata.duration_seconds:.1f} seconds")
            meta_table.add_row("Detected Language", transcript.language.upper())
            console.print(meta_table)
            console.print()

            console.print(f"[bold green]Transcript ({len(transcript.segments)} segments):[/bold green]")
            for seg in transcript.segments:
                console.print(f"[yellow]{format_timestamp(seg.start)}[/yellow] {seg.text}")
            console.print()
            console.print(Panel(transcript.text, title="[bold]Full Text[/bold]", border_style="green"))
            sys.exit(0)

        # Full Phase 2 Analysis Pipeline
        console.print("[dim cyan]Running end-to-end fact check pipeline...[/dim cyan]")
        analysis = run_full_pipeline(args.source)

        if args.json:
            print(json.dumps(analysis.model_dump(), indent=2, ensure_ascii=False))
            sys.exit(0)

        console.print()
        console.print(Panel.fit("[bold cyan]Reel Fact Checker - Analysis Report[/bold cyan]", border_style="cyan"))

        # Overall Verdict Banner
        style = get_verdict_style(analysis.overall_verdict)
        verdict_display = analysis.overall_verdict.replace("_", " ").upper()
        console.print(
            Panel(
                f"[{style}]Overall Verdict: {verdict_display}[/{style}]  |  [bold]Confidence: {analysis.overall_confidence}%[/bold]\n"
                f"[dim white]Tone: {analysis.tone.capitalize()} | Duration: {analysis.metadata.duration_seconds:.1f}s | Language: {analysis.transcript.language.upper()}[/dim white]",
                title="[bold]Summary Assessment[/bold]",
                border_style=style.split()[-1],
            )
        )

        # Summary & Background Story
        console.print(Panel(analysis.summary, title="[bold]Summary[/bold]", border_style="blue"))
        console.print(Panel(analysis.background_story, title="[bold]Background Context & Origin[/bold]", border_style="purple"))

        # Red Flags
        if analysis.red_flags:
            flags_text = " • " + "\n • ".join(analysis.red_flags)
            console.print(Panel(flags_text, title="[bold red]Red Flags Detected[/bold red]", border_style="red"))
        else:
            console.print("[dim green]✓ No major manipulative red flags detected.[/dim green]")

        console.print()

        # Claims & Fact-Check Details
        console.print(f"[bold]Extracted Claims ({len(analysis.claims)}):[/bold]")
        if not analysis.claims:
            console.print("[dim yellow]No checkable factual claims were identified in this video.[/dim yellow]")
        else:
            for claim in analysis.claims:
                verdict = next((v for v in analysis.verdicts if v.claim_id == claim.id), None)
                v_style = get_verdict_style(verdict.verdict) if verdict else "white"
                v_name = verdict.verdict.replace("_", " ").upper() if verdict else "UNVERIFIED"
                v_conf = f"{verdict.confidence}%" if verdict else "N/A"

                claim_body = [
                    f"[bold white]Claim {claim.id}:[/bold white] \"{claim.text}\"  [yellow]{format_timestamp(claim.timestamp)}[/yellow]",
                    f"[{v_style}]Verdict: {v_name}[/{v_style}] (Confidence: {v_conf})",
                ]

                if verdict:
                    claim_body.append(f"[italic]{verdict.explanation}[/italic]")
                    if verdict.sources:
                        claim_body.append("\n[bold]Sources Verified:[/bold]")
                        for s in verdict.sources:
                            claim_body.append(f" • [link={s.url}]{s.title}[/link] ([blue]{s.url}[/blue])")
                    else:
                        claim_body.append("\n[dim]No independent sources confirmed this claim.[/dim]")

                console.print(Panel("\n".join(claim_body), border_style=v_style.split()[-1]))

        # Debug View: Filtered segments
        if args.debug and analysis.transcript.filtered_segments:
            debug_table = Table(
                title=f"[bold red]Filtered Speech Segments ({len(analysis.transcript.filtered_segments)} discarded)[/bold red]",
                show_header=True,
                header_style="bold red",
            )
            debug_table.add_column("Time", style="yellow", width=14)
            debug_table.add_column("Text", style="white", width=25)
            debug_table.add_column("Reason", style="red")
            debug_table.add_column("no_speech_prob", style="cyan", width=15)
            debug_table.add_column("avg_logprob", style="magenta", width=12)

            for fseg in analysis.transcript.filtered_segments:
                t_str = f"{format_timestamp(fseg.start)}-{format_timestamp(fseg.end)}"
                debug_table.add_row(
                    t_str,
                    fseg.text or "<empty>",
                    fseg.reason,
                    f"{fseg.no_speech_prob:.3f}" if fseg.no_speech_prob is not None else "N/A",
                    f"{fseg.avg_logprob:.3f}" if fseg.avg_logprob is not None else "N/A",
                )
            console.print(debug_table)

        # Usage & Cost Stats
        cost_str = f"${analysis.cost_estimate_usd:.6f}" if analysis.cost_estimate_usd is not None else "N/A"
        console.print(
            f"[dim]Runtime: {analysis.runtime_seconds}s | Est. Cost: {cost_str}[/dim]"
        )

        # Mandatory Disclaimer
        console.print()
        console.print(Panel(f"[dim]{analysis.disclaimer}[/dim]", border_style="dim"))

    except ReelCheckerError as e:
        if args.json:
            print(json.dumps({"error": {"code": e.api_code, "message": str(e)}}, indent=2))
        else:
            console.print()
            console.print(f"[bold red]Error ({e.api_code}):[/bold red] {str(e)}")
        sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({"error": {"code": "INTERNAL_ERROR", "message": str(e)}}, indent=2))
        else:
            console.print()
            console.print(f"[bold red]Unexpected Error:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
