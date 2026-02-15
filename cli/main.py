"""
cli/main.py — ALMOND CLI entry point using Typer.

Commands:
- debug: Diagnose deployment errors from log files
- version: Show version information
"""

import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.status import Status

from cli.formatters import format_output
from cli.utils import handle_errors, read_log_file, validate_env_vars
from core.engine import RLMEngine

# Load environment variables from .env file
load_dotenv()

# Create Typer app
app = typer.Typer(
    name="almond",
    help="ALMOND: Memory-Driven Deployment Assistant using Recursive Language Models",
    add_completion=False,
)

# Rich console for output
console = Console()


@app.command()
def debug(
    logs: Path = typer.Option(
        ...,
        "--logs",
        "-l",
        help="Path to log file containing deployment errors",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    format: str = typer.Option(
        "pretty",
        "--format",
        "-f",
        help="Output format: pretty (default), json, minimal",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show verbose output (reasoning traces for Tier 3)",
    ),
    context: int = typer.Option(
        500,
        "--context",
        "-c",
        help="Number of characters around error signature to include",
        min=100,
        max=5000,
    ),
):
    """Diagnose deployment errors using the RLM engine.

    Searches through three tiers:
    1. Human History (vault) - High-fidelity human-solved matches
    2. Synthetic Cache (ai_fixes) - Previously synthesized AI fixes
    3. First-Principles Synthesis - LLM generates and validates from scratch

    Examples:
        almond debug --logs error.log
        almond debug -l error.log --format json
        almond debug -l error.log --verbose
        almond debug -l error.log -f minimal > fix.txt
    """
    with handle_errors(console):
        # Validate format
        valid_formats = ["pretty", "json", "minimal"]
        format_lower = format.lower()
        if format_lower not in valid_formats:
            raise RuntimeError(
                f"Invalid format '{format}'. Choose from: {', '.join(valid_formats)}"
            )

        # Validate environment variables
        api_key, vault_path, cache_path = validate_env_vars(console)

        # Read log file
        if verbose or format_lower == "pretty":
            console.print(f"[dim]Reading log file: {logs}[/dim]")

        log_content = read_log_file(logs)

        # Initialize RLM engine
        if verbose or format_lower == "pretty":
            console.print(f"[dim]Initializing RLM engine...[/dim]")

        engine = RLMEngine(
            api_key=api_key,
            vault_path=vault_path,
            cache_path=cache_path,
        )

        # Run diagnosis with status spinner (only for pretty format)
        if format_lower == "pretty":
            with Status("[bold blue]Analyzing error...[/bold blue]", console=console):
                report = engine.debug(log_content)
        else:
            report = engine.debug(log_content)

        # Display results
        if verbose or format_lower == "pretty":
            console.print()  # spacing

        format_output(
            report=report,
            format=format_lower,
            verbose=verbose,
            console=console,
        )


@app.command()
def version():
    """Show ALMOND version information."""
    console.print("[bold]ALMOND RLM[/bold] v0.1.0")
    console.print("[dim]Memory-Driven Deployment Assistant[/dim]")
    console.print()
    console.print("Core Components:")
    console.print("  • Recursive Language Model (RLM) Engine")
    console.print("  • Three-tier search: Vault → Cache → Synthesis")
    console.print("  • Programmable memory with subsumption logic")


@app.callback()
def main():
    """ALMOND: Memory-Driven Deployment Assistant.

    Use 'almond --help' to see available commands.
    """
    pass


if __name__ == "__main__":
    app()
