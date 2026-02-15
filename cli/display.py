"""
cli/display.py — Display components for Rich visualization.

Provides modular display components for rendering RLM engine results:
- StatusDisplay: Tier-specific colored panels
- TraceTreeBuilder: Hierarchical trace visualization
- CodeExtractor: Syntax-highlighted code extraction
- ConfidenceIndicator: Colored progress bars for confidence scores
"""

from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.syntax import Syntax
from rich.tree import Tree


class StatusDisplay:
    """Maps resolution status to colored panels."""

    STATUS_COLORS = {
        "RESOLVED_BY_VAULT": "green",
        "RESOLVED_BY_CACHE": "yellow",
        "RESOLVED_BY_SYNTHESIS": "blue",
        "MAX_DEPTH": "red",
        "STEP_LIMIT": "red",
        "PARSE_ERROR": "red",
        "UNKNOWN_ACTION": "red",
    }

    STATUS_TITLES = {
        "RESOLVED_BY_VAULT": "Tier 1: Human History",
        "RESOLVED_BY_CACHE": "Tier 2: Synthetic Cache",
        "RESOLVED_BY_SYNTHESIS": "Tier 3: First-Principles Synthesis",
        "MAX_DEPTH": "Error: Maximum Recursion Depth",
        "STEP_LIMIT": "Error: Step Limit Exceeded",
        "PARSE_ERROR": "Error: Parse Error",
        "UNKNOWN_ACTION": "Error: Unknown Action",
    }

    @classmethod
    def render(cls, status: str, console: Console) -> Panel:
        """Render a status panel with tier-specific color.

        Args:
            status: Resolution status from engine
            console: Rich Console

        Returns:
            Colored Rich Panel
        """
        color = cls.STATUS_COLORS.get(status, "white")
        title = cls.STATUS_TITLES.get(status, status)

        return Panel(
            f"[bold]{title}[/bold]",
            border_style=color,
            title="Resolution Tier",
        )


class ConfidenceIndicator:
    """Renders confidence scores as colored progress bars."""

    @staticmethod
    def render(confidence: float, console: Console) -> Progress:
        """Render a confidence score as a colored progress bar.

        Args:
            confidence: Score from 0.0 to 1.0
            console: Rich Console

        Returns:
            Rich Progress bar

        Color mapping:
            >= 0.8: green
            0.5-0.8: yellow
            < 0.5: red
        """
        if confidence >= 0.8:
            color = "green"
        elif confidence >= 0.5:
            color = "yellow"
        else:
            color = "red"

        progress = Progress(
            TextColumn("[bold]Confidence:[/bold]"),
            BarColumn(bar_width=30, style=color, complete_style=color),
            TextColumn(f"[{color}]{confidence:.1%}[/{color}]"),
            console=console,
        )

        task = progress.add_task("confidence", total=100)
        progress.update(task, completed=confidence * 100)

        return progress


class CodeExtractor:
    """Extracts and syntax-highlights solution code from reports."""

    # Language detection patterns
    LANGUAGE_PATTERNS = {
        "yaml": ["apiVersion:", "kind:", "metadata:"],
        "python": ["def ", "import ", "class ", "if __name__"],
        "bash": ["#!/bin/bash", "#!/bin/sh", "export "],
        "dockerfile": ["FROM ", "RUN ", "COPY ", "CMD "],
        "json": ['"', "{", "["],
    }

    @classmethod
    def extract(cls, report: Dict[str, Any]) -> Optional[str]:
        """Extract solution code from report.

        Checks these fields in order:
        1. solution
        2. fix_code
        3. code

        Args:
            report: Engine report dict

        Returns:
            Code string or None if not found
        """
        for field in ["solution", "fix_code", "code"]:
            code = report.get(field)
            if code and isinstance(code, str) and len(code.strip()) > 0:
                return code.strip()
        return None

    @classmethod
    def detect_language(cls, code: str) -> str:
        """Auto-detect code language from content.

        Args:
            code: Code string

        Returns:
            Language name (default: "text")
        """
        code_lower = code.lower()

        for lang, patterns in cls.LANGUAGE_PATTERNS.items():
            if any(pattern.lower() in code_lower for pattern in patterns):
                return lang

        return "text"

    @classmethod
    def render(cls, code: str, language: Optional[str] = None, console: Console = None) -> Syntax:
        """Render code with syntax highlighting.

        Args:
            code: Code string to highlight
            language: Optional language (auto-detected if None)
            console: Rich Console (unused, for API consistency)

        Returns:
            Rich Syntax object
        """
        if language is None:
            language = cls.detect_language(code)

        return Syntax(
            code,
            language,
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )


class TraceTreeBuilder:
    """Converts RLM trace arrays into hierarchical Rich Trees."""

    # Action icons for visual clarity
    ACTION_ICONS = {
        "EXECUTE_CODE": "🔍",
        "RECURSE_DEEPER": "🔄",
        "FINAL_REPORT": "✓",
    }

    @classmethod
    def build(cls, trace: List[Dict[str, Any]], max_items: int = 20) -> Tree:
        """Build a hierarchical tree from trace data.

        Args:
            trace: List of trace dicts with depth, action, delta
            max_items: Maximum items to show (truncate if exceeded)

        Returns:
            Rich Tree object
        """
        tree = Tree("[bold]Reasoning Trace[/bold]")

        # Truncate if too long
        if len(trace) > max_items:
            show_trace = trace[:10] + trace[-10:]
            truncated = len(trace) - 20
        else:
            show_trace = trace
            truncated = 0

        # Build tree by depth
        depth_nodes = {-1: tree}  # Root

        for item in show_trace:
            depth = item.get("depth", 0)
            action = item.get("action", "UNKNOWN")
            delta = item.get("delta", "")

            # Get or create parent node
            parent_depth = depth - 1
            if parent_depth not in depth_nodes:
                # Find closest ancestor
                for d in range(parent_depth, -2, -1):
                    if d in depth_nodes:
                        parent_depth = d
                        break

            parent = depth_nodes.get(parent_depth, tree)

            # Format node label
            icon = cls.ACTION_ICONS.get(action, "•")
            label = f"{icon} [dim]Depth {depth}:[/dim] {action}"
            if delta:
                # Truncate long deltas
                delta_display = delta[:100] + "..." if len(delta) > 100 else delta
                label += f"\n  [italic]{delta_display}[/italic]"

            # Add node
            node = parent.add(label)
            depth_nodes[depth] = node

        # Add truncation notice
        if truncated > 0:
            tree.add(f"[dim]... {truncated} steps omitted ...[/dim]")

        return tree


class DebugDisplayManager:
    """Orchestrates all display components."""

    def __init__(self, console: Console):
        self.console = console

    def render_cache_result(self, fix: Dict[str, Any]) -> Group:
        """Render a Tier 2 (cache) result.

        Args:
            fix: Cache hit dict with confidence, description, code

        Returns:
            Rich Group with all panels
        """
        panels = []

        # Confidence indicator
        confidence = fix.get("confidence", 0.5)
        panels.append(ConfidenceIndicator.render(confidence, self.console))

        # Description
        description = fix.get("fix_description", fix.get("description", "No description"))
        panels.append(
            Panel(
                description,
                title="Fix Description",
                border_style="yellow",
            )
        )

        # Code (if present)
        code = fix.get("fix_code", fix.get("code"))
        if code:
            syntax = CodeExtractor.render(code, console=self.console)
            panels.append(
                Panel(
                    syntax,
                    title="Fix Code",
                    border_style="yellow",
                )
            )

        return Group(*panels)

    def render_vault_result(self, report: Dict[str, Any]) -> Group:
        """Render a Tier 1 (vault) result.

        Args:
            report: Vault match report with root_cause, solution

        Returns:
            Rich Group with all panels
        """
        panels = []

        # Root cause
        root_cause = report.get("root_cause", report.get("hypothesis", "Unknown"))
        panels.append(
            Panel(
                root_cause,
                title="Root Cause",
                border_style="green",
            )
        )

        # Solution with syntax highlighting
        solution = CodeExtractor.extract(report)
        if solution:
            syntax = CodeExtractor.render(solution, console=self.console)
            panels.append(
                Panel(
                    syntax,
                    title="Solution",
                    border_style="green",
                )
            )
        else:
            # No code, show text solution
            solution_text = report.get("solution", "No solution provided")
            panels.append(
                Panel(
                    solution_text,
                    title="Solution",
                    border_style="green",
                )
            )

        return Group(*panels)

    def render_synthesis_result(self, report: Dict[str, Any], trace: Optional[List] = None, verbose: bool = False) -> Group:
        """Render a Tier 3 (synthesis) result.

        Args:
            report: Synthesis report dict
            trace: Optional trace data for verbose mode
            verbose: Show full trace tree

        Returns:
            Rich Group with all panels
        """
        panels = []

        # Root cause / hypothesis
        root_cause = report.get("root_cause", report.get("hypothesis", "Unknown"))
        panels.append(
            Panel(
                root_cause,
                title="Root Cause Analysis",
                border_style="blue",
            )
        )

        # Solution with syntax highlighting
        solution = CodeExtractor.extract(report)
        if solution:
            syntax = CodeExtractor.render(solution, console=self.console)
            panels.append(
                Panel(
                    syntax,
                    title="Solution",
                    border_style="blue",
                )
            )
        else:
            # No code, show text solution
            solution_text = report.get("solution", "No solution provided")
            panels.append(
                Panel(
                    solution_text,
                    title="Solution",
                    border_style="blue",
                )
            )

        # Trace tree (only in verbose mode)
        if verbose and trace:
            tree = TraceTreeBuilder.build(trace)
            panels.append(
                Panel(
                    tree,
                    title="Reasoning Trace",
                    border_style="blue",
                )
            )

        return Group(*panels)

    def render_error(self, status: str, message: str) -> Panel:
        """Render an error status.

        Args:
            status: Error status code
            message: Error message

        Returns:
            Red error panel
        """
        return Panel(
            message,
            title=f"Error: {status}",
            border_style="red",
        )
