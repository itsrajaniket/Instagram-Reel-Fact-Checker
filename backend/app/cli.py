"""Command Line Interface for Reel Fact Checker."""

import argparse
import json
import logging
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.errors import ReelCheckerError
from app.pipeline.run import get_transcript

# Configure root logging for CLI: display warnings/errors by default unless verbose
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def format_timestamp(seconds: float) -> str:
    """Format seconds into [mm:ss] timestamp format."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{mins:02d}:{secs:02d}]"


def main() -> None:
    """CLI entry point for running Phase 1 transcript pipeline."""
    parser = argparse.ArgumentParser(
        description="Extract audio and transcribe speech from an Instagram Reel URL or local media file."
    )
    parser.add_argument(
        "source",
        help="Instagram reel URL (e.g. https://www.instagram.com/reel/...) or path to a local media file (mp4, mov, mp3, m4a, wav)",
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
        help="Enable detailed debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    console = Console()

    try:
        transcript, metadata = get_transcript(args.source)

        if args.json:
            result = {
                "metadata": metadata.model_dump(),
                "transcript": transcript.model_dump(),
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            sys.exit(0)

        # Rich formatted output
        console.print()
        console.print(Panel.fit("[bold cyan]Reel Fact Checker - Transcript Pipeline[/bold cyan]", border_style="cyan"))

        # Metadata table
        meta_table = Table(title="[bold]Media Metadata[/bold]", show_header=True, header_style="bold magenta")
        meta_table.add_column("Property", style="cyan", width=18)
        meta_table.add_column("Value", style="white")

        meta_table.add_row("Source", metadata.source_url or args.source)
        meta_table.add_row("Duration", f"{metadata.duration_seconds:.1f} seconds")
        if metadata.creator:
            meta_table.add_row("Creator", metadata.creator)
        if metadata.upload_date:
            meta_table.add_row("Upload Date", metadata.upload_date)
        if metadata.caption:
            caption_preview = metadata.caption if len(metadata.caption) <= 120 else metadata.caption[:117] + "..."
            meta_table.add_row("Caption", caption_preview)

        meta_table.add_row("Detected Language", transcript.language.upper())
        console.print(meta_table)
        console.print()

        # Transcript segments
        console.print(f"[bold green]Timestamped Transcript ({len(transcript.segments)} segments):[/bold green]")
        for seg in transcript.segments:
            ts = format_timestamp(seg.start)
            console.print(f"[yellow]{ts}[/yellow] {seg.text}")

        console.print()
        console.print(Panel(transcript.text, title="[bold]Full Text[/bold]", border_style="green"))

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
