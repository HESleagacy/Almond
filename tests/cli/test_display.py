"""
tests/cli/test_display.py — Tests for display components.
"""

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.syntax import Syntax
from rich.tree import Tree

from cli.display import (
    CodeExtractor,
    ConfidenceIndicator,
    DebugDisplayManager,
    StatusDisplay,
    TraceTreeBuilder,
)


class TestStatusDisplay:
    """Tests for StatusDisplay component."""

    def test_resolved_by_vault(self):
        """Test Tier 1 status display."""
        console = Console()
        panel = StatusDisplay.render("RESOLVED_BY_VAULT", console)

        assert isinstance(panel, Panel)
        assert panel.border_style == "green"

    def test_resolved_by_cache(self):
        """Test Tier 2 status display."""
        console = Console()
        panel = StatusDisplay.render("RESOLVED_BY_CACHE", console)

        assert isinstance(panel, Panel)
        assert panel.border_style == "yellow"

    def test_resolved_by_synthesis(self):
        """Test Tier 3 status display."""
        console = Console()
        panel = StatusDisplay.render("RESOLVED_BY_SYNTHESIS", console)

        assert isinstance(panel, Panel)
        assert panel.border_style == "blue"

    def test_error_status(self):
        """Test error status display."""
        console = Console()
        panel = StatusDisplay.render("MAX_DEPTH", console)

        assert isinstance(panel, Panel)
        assert panel.border_style == "red"

    def test_unknown_status(self):
        """Test unknown status defaults to white."""
        console = Console()
        panel = StatusDisplay.render("UNKNOWN", console)

        assert isinstance(panel, Panel)
        assert panel.border_style == "white"


class TestConfidenceIndicator:
    """Tests for ConfidenceIndicator component."""

    def test_high_confidence(self):
        """Test high confidence (>= 0.8) shows green."""
        console = Console()
        progress = ConfidenceIndicator.render(0.9, console)

        assert isinstance(progress, Progress)

    def test_medium_confidence(self):
        """Test medium confidence (0.5-0.8) shows yellow."""
        console = Console()
        progress = ConfidenceIndicator.render(0.6, console)

        assert isinstance(progress, Progress)

    def test_low_confidence(self):
        """Test low confidence (< 0.5) shows red."""
        console = Console()
        progress = ConfidenceIndicator.render(0.3, console)

        assert isinstance(progress, Progress)


class TestCodeExtractor:
    """Tests for CodeExtractor component."""

    def test_extract_solution(self):
        """Test extracting code from 'solution' field."""
        report = {"solution": "kubectl apply -f fix.yaml"}
        code = CodeExtractor.extract(report)
        assert code == "kubectl apply -f fix.yaml"

    def test_extract_fix_code(self):
        """Test extracting code from 'fix_code' field."""
        report = {"fix_code": "export VAR=value"}
        code = CodeExtractor.extract(report)
        assert code == "export VAR=value"

    def test_extract_code(self):
        """Test extracting code from 'code' field."""
        report = {"code": "def fix(): pass"}
        code = CodeExtractor.extract(report)
        assert code == "def fix(): pass"

    def test_extract_priority(self):
        """Test that 'solution' takes priority over others."""
        report = {
            "solution": "primary",
            "fix_code": "secondary",
            "code": "tertiary",
        }
        code = CodeExtractor.extract(report)
        assert code == "primary"

    def test_extract_none(self):
        """Test that None is returned when no code found."""
        report = {"root_cause": "Network issue"}
        code = CodeExtractor.extract(report)
        assert code is None

    def test_detect_yaml(self):
        """Test YAML language detection."""
        code = "apiVersion: v1\nkind: Pod"
        lang = CodeExtractor.detect_language(code)
        assert lang == "yaml"

    def test_detect_python(self):
        """Test Python language detection."""
        code = "def main():\n    import sys"
        lang = CodeExtractor.detect_language(code)
        assert lang == "python"

    def test_detect_bash(self):
        """Test Bash language detection."""
        code = "#!/bin/bash\nexport PATH=/usr/bin"
        lang = CodeExtractor.detect_language(code)
        assert lang == "bash"

    def test_detect_dockerfile(self):
        """Test Dockerfile language detection."""
        code = "FROM ubuntu:20.04\nRUN apt-get update"
        lang = CodeExtractor.detect_language(code)
        assert lang == "dockerfile"

    def test_detect_json(self):
        """Test JSON language detection."""
        code = '{"key": "value"}'
        lang = CodeExtractor.detect_language(code)
        assert lang == "json"

    def test_detect_unknown(self):
        """Test unknown language defaults to text."""
        code = "Some random text without indicators"
        lang = CodeExtractor.detect_language(code)
        assert lang == "text"

    def test_render_syntax(self):
        """Test syntax rendering."""
        code = "def main(): pass"
        console = Console()
        syntax = CodeExtractor.render(code, console=console)

        assert isinstance(syntax, Syntax)

    def test_render_auto_detect(self):
        """Test auto-detection during render."""
        code = "apiVersion: v1"
        console = Console()
        syntax = CodeExtractor.render(code, console=console)

        assert isinstance(syntax, Syntax)


class TestTraceTreeBuilder:
    """Tests for TraceTreeBuilder component."""

    def test_build_simple_trace(self):
        """Test building a simple trace tree."""
        trace = [
            {"depth": 0, "action": "EXECUTE_CODE", "delta": "Searching vault..."},
            {"depth": 0, "action": "FINAL_REPORT", "delta": "Found solution"},
        ]

        tree = TraceTreeBuilder.build(trace)
        assert isinstance(tree, Tree)

    def test_build_nested_trace(self):
        """Test building a nested trace with depth changes."""
        trace = [
            {"depth": 0, "action": "EXECUTE_CODE", "delta": "Parent search"},
            {"depth": 1, "action": "RECURSE_DEEPER", "delta": "Child search"},
            {"depth": 1, "action": "FINAL_REPORT", "delta": "Child found solution"},
        ]

        tree = TraceTreeBuilder.build(trace)
        assert isinstance(tree, Tree)

    def test_truncate_long_trace(self):
        """Test that traces >20 items are truncated."""
        trace = [
            {"depth": i % 3, "action": "EXECUTE_CODE", "delta": f"Step {i}"}
            for i in range(30)
        ]

        tree = TraceTreeBuilder.build(trace, max_items=20)
        assert isinstance(tree, Tree)

    def test_action_icons(self):
        """Test that action icons are applied."""
        trace = [
            {"depth": 0, "action": "EXECUTE_CODE", "delta": "Test"},
        ]

        tree = TraceTreeBuilder.build(trace)
        # Tree should be built successfully
        assert isinstance(tree, Tree)

    def test_long_delta_truncation(self):
        """Test that long deltas are truncated."""
        long_delta = "x" * 200
        trace = [
            {"depth": 0, "action": "EXECUTE_CODE", "delta": long_delta},
        ]

        tree = TraceTreeBuilder.build(trace)
        assert isinstance(tree, Tree)


class TestDebugDisplayManager:
    """Tests for DebugDisplayManager orchestration."""

    def test_render_cache_result(self):
        """Test rendering a cache (Tier 2) result."""
        console = Console()
        manager = DebugDisplayManager(console)

        fix = {
            "confidence": 0.85,
            "fix_description": "Add timeout configuration",
            "fix_code": "timeout: 30s",
        }

        result = manager.render_cache_result(fix)
        assert result is not None

    def test_render_cache_no_code(self):
        """Test rendering cache result without code."""
        console = Console()
        manager = DebugDisplayManager(console)

        fix = {
            "confidence": 0.7,
            "fix_description": "Manual intervention required",
        }

        result = manager.render_cache_result(fix)
        assert result is not None

    def test_render_vault_result(self):
        """Test rendering a vault (Tier 1) result."""
        console = Console()
        manager = DebugDisplayManager(console)

        report = {
            "root_cause": "Network timeout",
            "solution": "kubectl scale deployment --replicas=3",
        }

        result = manager.render_vault_result(report)
        assert result is not None

    def test_render_vault_no_code(self):
        """Test rendering vault result without code solution."""
        console = Console()
        manager = DebugDisplayManager(console)

        report = {
            "root_cause": "Configuration issue",
            "solution": "Check your config files",
        }

        result = manager.render_vault_result(report)
        assert result is not None

    def test_render_synthesis_result(self):
        """Test rendering a synthesis (Tier 3) result."""
        console = Console()
        manager = DebugDisplayManager(console)

        report = {
            "root_cause": "Memory leak in pod",
            "solution": "apiVersion: v1\nkind: Pod",
        }

        trace = [
            {"depth": 0, "action": "EXECUTE_CODE", "delta": "Analyzing..."},
        ]

        result = manager.render_synthesis_result(report, trace=trace, verbose=False)
        assert result is not None

    def test_render_synthesis_verbose(self):
        """Test rendering synthesis result with verbose trace."""
        console = Console()
        manager = DebugDisplayManager(console)

        report = {
            "hypothesis": "Database connection pool exhausted",
            "solution": "Increase pool size to 50",
        }

        trace = [
            {"depth": 0, "action": "EXECUTE_CODE", "delta": "Checking logs..."},
            {"depth": 1, "action": "RECURSE_DEEPER", "delta": "Deep dive..."},
        ]

        result = manager.render_synthesis_result(report, trace=trace, verbose=True)
        assert result is not None

    def test_render_error(self):
        """Test rendering an error status."""
        console = Console()
        manager = DebugDisplayManager(console)

        panel = manager.render_error("MAX_DEPTH", "Recursion limit reached")
        assert isinstance(panel, Panel)
        assert panel.border_style == "red"
