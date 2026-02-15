"""
cli/__init__.py — ALMOND CLI entry point.

Exports the main Typer app for use as a console script.
"""

from cli.main import app

__all__ = ["app"]
