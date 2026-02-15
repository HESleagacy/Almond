"""
cli/utils.py — Utility functions for CLI operations.

Handles file reading, error handling, and common operations.
"""

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel


def read_log_file(path: Path, max_chars: int = 50000) -> str:
    """Read a log file with UTF-8 encoding and optional truncation.

    Args:
        path: Path to the log file
        max_chars: Maximum characters to read (default 50k)

    Returns:
        Log file contents (possibly truncated)

    Raises:
        FileNotFoundError: If the file doesn't exist
        RuntimeError: If the file can't be read
    """
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    if not path.is_file():
        raise RuntimeError(f"Path is not a file: {path}")

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to read file {path}: {e}")

    # Truncate if too large
    if len(content) > max_chars:
        half = max_chars // 2
        separator = f"\n\n... [File truncated: {len(content)} chars, showing first {half} + last {half}] ...\n\n"
        content = content[:half] + separator + content[-half:]

    return content


@contextmanager
def handle_errors(console: Console):
    """Context manager for graceful error handling with Rich display.

    Catches common errors and displays them as Rich panels instead of
    raw tracebacks. Exits with appropriate exit codes.

    Args:
        console: Rich Console for error output

    Exit codes:
        0: Success
        1: General error
        130: Keyboard interrupt (Ctrl+C)
    """
    try:
        yield
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except FileNotFoundError as e:
        console.print(
            Panel(
                f"[red]File not found:[/red] {e}",
                title="Error",
                border_style="red",
            )
        )
        sys.exit(1)
    except RuntimeError as e:
        console.print(
            Panel(
                f"[red]Runtime error:[/red] {e}",
                title="Error",
                border_style="red",
            )
        )
        sys.exit(1)
    except Exception as e:
        console.print(
            Panel(
                f"[red]Unexpected error:[/red] {type(e).__name__}: {e}",
                title="Error",
                border_style="red",
            )
        )
        sys.exit(1)


def validate_env_vars(console: Console) -> tuple[str, str, str]:
    """Validate required environment variables.

    Args:
        console: Rich Console for error output

    Returns:
        Tuple of (api_key, vault_path, cache_path)

    Raises:
        RuntimeError: If required env vars are missing
    """
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. "
            "Please set it in your environment or .env file."
        )

    vault_path = os.getenv("VAULT_PATH", "./vault/history.txt")
    cache_path = os.getenv("CACHE_PATH", "./vault/ai_fixes.json")

    # Validate vault exists
    if not Path(vault_path).exists():
        raise RuntimeError(
            f"Vault not found at {vault_path}. "
            "Please initialize the vault first."
        )

    return api_key, vault_path, cache_path
