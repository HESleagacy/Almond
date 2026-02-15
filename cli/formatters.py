"""
cli/formatters.py — Output formatters for different display modes.

Supports three output formats:
- pretty: Rich-formatted with colors and panels (default)
- json: Machine-readable JSON output
- minimal: Plain text with just the fix/solution
"""

import json
from typing import Any, Dict, Optional

from rich.console import Console, Group

from cli.display import DebugDisplayManager, StatusDisplay


def format_output(
    report: Dict[str, Any],
    format: str,
    verbose: bool,
    console: Console,
) -> None:
    """Route to appropriate formatter based on output format.

    Args:
        report: Engine report dict
        format: Output format (pretty, json, minimal)
        verbose: Show verbose output (trace trees, etc.)
        console: Rich Console for output
    """
    if format == "json":
        _format_json(report, console)
    elif format == "minimal":
        _format_minimal(report, console)
    else:  # default: pretty
        _format_pretty(report, verbose, console)


def _format_json(report: Dict[str, Any], console: Console) -> None:
    """Output report as JSON (machine-readable).

    Removes internal fields (starting with underscore) for cleaner output.

    Args:
        report: Engine report dict
        console: Rich Console for output
    """
    # Remove internal fields
    clean_report = {
        k: v for k, v in report.items()
        if not k.startswith("_")
    }

    console.print_json(data=clean_report)


def _format_minimal(report: Dict[str, Any], console: Console) -> None:
    """Output just the fix/solution text (no formatting).

    Args:
        report: Engine report dict
        console: Rich Console for output
    """
    status = report.get("status", "UNKNOWN")

    # Extract the core fix/solution based on tier
    if status == "RESOLVED_BY_CACHE":
        fix = report.get("fix", {})
        output = fix.get("fix_code") or fix.get("fix_description") or fix.get("description", "")

    elif status == "RESOLVED_BY_VAULT":
        report_data = report.get("report", {})
        output = report_data.get("solution") or report_data.get("root_cause", "")

    elif status == "RESOLVED_BY_SYNTHESIS":
        report_data = report.get("report", {})
        output = report_data.get("solution") or report_data.get("root_cause", "")

    else:
        # Error status
        output = report.get("msg", "") or report.get("raw", "")

    # Print plain text (no Rich formatting)
    console.print(output, markup=False, highlight=False)


def _format_pretty(
    report: Dict[str, Any],
    verbose: bool,
    console: Console,
) -> None:
    """Output Rich-formatted display with colors and panels.

    Args:
        report: Engine report dict
        verbose: Show verbose output (trace trees)
        console: Rich Console for output
    """
    status = report.get("status", "UNKNOWN")
    display_manager = DebugDisplayManager(console)

    # Status panel (always shown)
    status_panel = StatusDisplay.render(status, console)
    console.print(status_panel)
    console.print()  # spacing

    # Tier-specific rendering
    if status == "RESOLVED_BY_CACHE":
        fix = report.get("fix", {})
        content = display_manager.render_cache_result(fix)
        console.print(content)

    elif status == "RESOLVED_BY_VAULT":
        report_data = report.get("report", {})
        content = display_manager.render_vault_result(report_data)
        console.print(content)

    elif status == "RESOLVED_BY_SYNTHESIS":
        report_data = report.get("report", {})
        trace = report.get("_trace", [])
        content = display_manager.render_synthesis_result(
            report_data,
            trace=trace,
            verbose=verbose,
        )
        console.print(content)

    else:
        # Error status
        message = report.get("msg", "") or report.get("raw", "Unknown error")
        error_panel = display_manager.render_error(status, message)
        console.print(error_panel)
