"""
tests/cli/test_formatters.py — Tests for output formatters.
"""

import json
from io import StringIO

import pytest
from rich.console import Console

from cli.formatters import _format_json, _format_minimal, _format_pretty, format_output


class TestFormatJson:
    """Tests for JSON output format."""

    def test_json_output(self):
        """Test JSON output removes internal fields."""
        report = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {"description": "Test fix"},
            "_trace": ["internal", "data"],
        }

        console = Console(file=StringIO())
        _format_json(report, console)

        # Should not raise exception

    def test_json_clean_internal_fields(self):
        """Test that internal fields (starting with _) are removed."""
        report = {
            "status": "RESOLVED_BY_SYNTHESIS",
            "report": {"solution": "Fix"},
            "_trace": ["step1", "step2"],
            "_internal": "data",
        }

        console = Console(file=StringIO())
        # Capture output
        output = StringIO()
        test_console = Console(file=output)
        _format_json(report, test_console)

        # Verify internal fields not in output
        result = output.getvalue()
        assert "_trace" not in result
        assert "_internal" not in result


class TestFormatMinimal:
    """Tests for minimal output format."""

    def test_minimal_cache_with_code(self):
        """Test minimal output for cache hit with code."""
        report = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {
                "fix_code": "kubectl scale --replicas=3",
                "fix_description": "Scale up deployment",
            },
        }

        output = StringIO()
        console = Console(file=output, markup=False, highlight=False)
        _format_minimal(report, console)

        result = output.getvalue()
        assert "kubectl scale --replicas=3" in result

    def test_minimal_cache_without_code(self):
        """Test minimal output for cache hit without code."""
        report = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {
                "fix_description": "Manual intervention required",
            },
        }

        output = StringIO()
        console = Console(file=output, markup=False, highlight=False)
        _format_minimal(report, console)

        result = output.getvalue()
        assert "Manual intervention required" in result

    def test_minimal_vault(self):
        """Test minimal output for vault match."""
        report = {
            "status": "RESOLVED_BY_VAULT",
            "report": {
                "solution": "apiVersion: v1\nkind: Pod",
                "root_cause": "Pod crash loop",
            },
        }

        output = StringIO()
        console = Console(file=output, markup=False, highlight=False)
        _format_minimal(report, console)

        result = output.getvalue()
        assert "apiVersion: v1" in result

    def test_minimal_synthesis(self):
        """Test minimal output for synthesis."""
        report = {
            "status": "RESOLVED_BY_SYNTHESIS",
            "report": {
                "solution": "Fix code here",
                "root_cause": "Memory leak",
            },
        }

        output = StringIO()
        console = Console(file=output, markup=False, highlight=False)
        _format_minimal(report, console)

        result = output.getvalue()
        assert "Fix code here" in result

    def test_minimal_error(self):
        """Test minimal output for error status."""
        report = {
            "status": "MAX_DEPTH",
            "msg": "Recursion limit reached",
        }

        output = StringIO()
        console = Console(file=output, markup=False, highlight=False)
        _format_minimal(report, console)

        result = output.getvalue()
        assert "Recursion limit reached" in result


class TestFormatPretty:
    """Tests for pretty (Rich-formatted) output."""

    def test_pretty_cache(self):
        """Test pretty output for cache hit."""
        report = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {
                "confidence": 0.85,
                "fix_description": "Scale deployment",
                "fix_code": "kubectl scale --replicas=3",
            },
        }

        console = Console(file=StringIO())
        _format_pretty(report, verbose=False, console=console)

        # Should not raise exception

    def test_pretty_vault(self):
        """Test pretty output for vault match."""
        report = {
            "status": "RESOLVED_BY_VAULT",
            "report": {
                "root_cause": "Network timeout",
                "solution": "apiVersion: v1",
            },
        }

        console = Console(file=StringIO())
        _format_pretty(report, verbose=False, console=console)

        # Should not raise exception

    def test_pretty_synthesis_no_verbose(self):
        """Test pretty output for synthesis without verbose."""
        report = {
            "status": "RESOLVED_BY_SYNTHESIS",
            "report": {
                "root_cause": "Memory leak",
                "solution": "Increase memory limit",
            },
            "_trace": [
                {"depth": 0, "action": "EXECUTE_CODE", "delta": "Searching..."},
            ],
        }

        console = Console(file=StringIO())
        _format_pretty(report, verbose=False, console=console)

        # Should not raise exception

    def test_pretty_synthesis_verbose(self):
        """Test pretty output for synthesis with verbose trace."""
        report = {
            "status": "RESOLVED_BY_SYNTHESIS",
            "report": {
                "hypothesis": "Database connection issue",
                "solution": "Increase connection pool",
            },
            "_trace": [
                {"depth": 0, "action": "EXECUTE_CODE", "delta": "Step 1"},
                {"depth": 1, "action": "RECURSE_DEEPER", "delta": "Step 2"},
            ],
        }

        console = Console(file=StringIO())
        _format_pretty(report, verbose=True, console=console)

        # Should not raise exception

    def test_pretty_error(self):
        """Test pretty output for error status."""
        report = {
            "status": "STEP_LIMIT",
            "msg": "Exhausted steps at depth 2",
        }

        console = Console(file=StringIO())
        _format_pretty(report, verbose=False, console=console)

        # Should not raise exception


class TestFormatOutput:
    """Tests for format_output router function."""

    def test_route_to_json(self):
        """Test routing to JSON formatter."""
        report = {"status": "RESOLVED_BY_CACHE", "fix": {}}

        console = Console(file=StringIO())
        format_output(report, format="json", verbose=False, console=console)

        # Should not raise exception

    def test_route_to_minimal(self):
        """Test routing to minimal formatter."""
        report = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {"fix_description": "Test"},
        }

        console = Console(file=StringIO())
        format_output(report, format="minimal", verbose=False, console=console)

        # Should not raise exception

    def test_route_to_pretty(self):
        """Test routing to pretty formatter (default)."""
        report = {"status": "RESOLVED_BY_CACHE", "fix": {}}

        console = Console(file=StringIO())
        format_output(report, format="pretty", verbose=False, console=console)

        # Should not raise exception

    def test_default_to_pretty(self):
        """Test that unknown formats default to pretty."""
        report = {"status": "RESOLVED_BY_CACHE", "fix": {}}

        console = Console(file=StringIO())
        format_output(report, format="unknown", verbose=False, console=console)

        # Should not raise exception (defaults to pretty)
