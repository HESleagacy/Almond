"""
core/tools.py — Tools the RLM agent calls: grep, slice, sub_query.

This module provides the VaultReader class, which is the API surface
the agent's Python REPL uses to search, slice, and read from the
Memory Vault.  Designed for programmatic access — no vector DB,
no embeddings — just text processing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from vault.ingest import DELIMITER_START_RE, DELIMITER_END_RE


# ──────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """A single search hit from :meth:`VaultReader.grep`."""
    file: str
    line_number: int
    line_content: str
    byte_offset: int
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
# VaultReader
# ──────────────────────────────────────────────────────────────────────

class VaultReader:
    """Read-only query interface to the Memory Vault.

    Supports the three-tiered search hierarchy::

        Tier 1 → grep()         search history.txt for human-solved matches
        Tier 2 → search_cache() search ai_fixes.json for AI-synthesized fixes
        Tier 3 → (Person 2)     de novo synthesis by the RLM engine

    Parameters
    ----------
    vault_dir : str | Path
        Root directory of the vault (e.g. ``"./vault"``).
    """

    def __init__(self, vault_dir: str | Path) -> None:
        self.vault_dir = Path(vault_dir)
        self.history_file = self.vault_dir / "history.txt"
        self.golden_dir = self.vault_dir / "golden_snippets"
        self._index_path = self.vault_dir / "index.json"
        self._cache_path = self.vault_dir / "ai_fixes.json"
        self._index: Dict[str, Any] = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"projects": {}, "golden_snippets": []}

    def reload_index(self) -> None:
        """Re-read ``index.json`` from disk (e.g. after new ingestion)."""
        self._index = self._load_index()

    # ── Project & Entry enumeration ──────────────────────────────────

    def list_projects(self) -> List[str]:
        """Return a sorted list of all project names in the vault."""
        return sorted(self._index.get("projects", {}).keys())

    def list_entries(
        self,
        project: str,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List entry metadata for a project, sorted by timestamp.

        Parameters
        ----------
        project : str
            Project name.
        category : str, optional
            Filter to ``deployment_log``, ``pull_request``, or ``golden_code``.
        """
        proj = self._index.get("projects", {}).get(project)
        if not proj:
            return []

        entries = proj.get("entries", [])
        if category:
            entries = [e for e in entries if e.get("category") == category]

        # Also include golden snippets for this project if requested.
        if category is None or category == "golden_code":
            for gs in self._index.get("golden_snippets", []):
                if gs.get("extra", {}).get("project") == project:
                    entries.append(gs)

        entries.sort(key=lambda e: e.get("timestamp", ""))
        return entries

    # ── Single-entry fetch ───────────────────────────────────────────

    def get_entry(self, project: str, entry_id: str) -> Optional[str]:
        """Fetch the full text of a vault entry by its ID.

        Uses the byte-offset index for efficient seek + read.
        """
        # Check history.txt entries.
        proj = self._index.get("projects", {}).get(project)
        if proj:
            for entry in proj.get("entries", []):
                if entry["id"] == entry_id:
                    return self.read_bytes(
                        str(self.history_file),
                        entry["byte_start"],
                        entry["byte_end"],
                    )

        # Check golden snippets.
        for gs in self._index.get("golden_snippets", []):
            if gs["id"] == entry_id:
                snippet_path = self.golden_dir / f"{entry_id}.txt"
                if snippet_path.exists():
                    return snippet_path.read_text(encoding="utf-8")

        return None

    # ── Byte-range read (the "slice" primitive) ──────────────────────

    def read_bytes(self, filepath: str, start: int, end: int) -> str:
        """Read a raw byte range from a vault file.

        The primitive the RLM uses to "slice" into large files without
        loading them entirely (e.g. ``read_bytes("vault/history.txt", 1000, 5000)``).
        """
        path = Path(filepath)
        if not path.is_absolute():
            path = self.vault_dir / path

        with open(path, "rb") as f:
            f.seek(start)
            raw = f.read(end - start)

        return raw.decode("utf-8", errors="replace")

    # ── grep: regex keyword search ───────────────────────────────────

    def grep(
        self,
        pattern: str,
        project: Optional[str] = None,
        context_lines: int = 3,
        max_results: int = 100,
    ) -> List[SearchResult]:
        """Search vault files for lines matching *pattern* (regex).

        This is the primary search tool. Works like ``grep -n -C3``.

        Parameters
        ----------
        pattern : str
            Python regex pattern.
        project : str, optional
            Restrict search to entries from one project.
        context_lines : int
            Lines of context before/after each match.
        max_results : int
            Maximum number of results.
        """
        regex = re.compile(pattern)
        results: List[SearchResult] = []
        files_to_search = self._get_searchable_files()

        for filepath in files_to_search:
            if not filepath.exists():
                continue

            text = filepath.read_text(encoding="utf-8")

            # If filtering by project, only search within that project's
            # delimited blocks in history.txt.
            if project and filepath == self.history_file:
                # Still do a full-text search but results will naturally
                # fall within delimited blocks.
                pass

            lines = text.split("\n")
            byte_offsets = []
            offset = 0
            for line in lines:
                byte_offsets.append(offset)
                offset += len(line.encode("utf-8")) + 1

            for i, line in enumerate(lines):
                if regex.search(line):
                    # If project filter is on, check that this line is
                    # within a block belonging to that project.
                    if project and filepath == self.history_file:
                        if not self._line_belongs_to_project(lines, i, project):
                            continue

                    ctx_before = lines[max(0, i - context_lines): i]
                    ctx_after = lines[i + 1: i + 1 + context_lines]
                    results.append(SearchResult(
                        file=str(filepath),
                        line_number=i + 1,
                        line_content=line,
                        byte_offset=byte_offsets[i],
                        context_before=ctx_before,
                        context_after=ctx_after,
                    ))
                    if len(results) >= max_results:
                        return results

        return results

    # Alias for backward compatibility.
    search_by_keyword = grep

    # ── Time-window slice ────────────────────────────────────────────

    def get_log_window(
        self,
        timestamp: str,
        window_size: int = 3600,
        project: Optional[str] = None,
    ) -> str:
        """Return all log entries within ±*window_size* seconds of *timestamp*.

        Parameters
        ----------
        timestamp : str
            ISO-8601 timestamp to center the window on.
        window_size : int
            Half-width in seconds (default: 1 hour).
        project : str, optional
            Restrict to a single project.
        """
        center = self._parse_ts(timestamp)
        delta = timedelta(seconds=window_size)
        t_start = center - delta
        t_end = center + delta

        projects = [project] if project else self.list_projects()
        matched: List[str] = []

        for proj_name in projects:
            entries = self.list_entries(proj_name, category="deployment_log")
            for entry in entries:
                entry_ts = self._parse_ts(entry["timestamp"])
                if t_start <= entry_ts <= t_end:
                    content = self.get_entry(proj_name, entry["id"])
                    if content:
                        matched.append(content)

        return "\n".join(matched)

    # ── sub_query: search within a specific entry ────────────────────

    def sub_query(
        self,
        project: str,
        entry_id: str,
        pattern: str,
    ) -> List[str]:
        """Search within a single entry for lines matching *pattern*.

        Useful for drilling down after a broad ``grep`` narrows the
        target to a specific entry.
        """
        content = self.get_entry(project, entry_id)
        if not content:
            return []

        regex = re.compile(pattern)
        return [line for line in content.split("\n") if regex.search(line)]

    # ── Tier 2: Synthetic Cache Search ────────────────────────────────

    def search_cache(
        self,
        error_text: str,
        project: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search the Synthetic Cache (Tier 2) for matching AI fixes.

        Regex-matches *error_text* against stored error signatures in
        ``ai_fixes.json``.  Returns matches sorted by confidence.

        Parameters
        ----------
        error_text : str
            Current error message / log snippet.
        project : str, optional
            Prefer fixes from this project.
        min_confidence : float
            Minimum confidence threshold.
        """
        cache = self._load_cache()
        matches: List[Dict[str, Any]] = []

        for fix in cache:
            if fix.get("confidence", 0) < min_confidence:
                continue
            try:
                if re.search(fix["error_signature"], error_text, re.IGNORECASE):
                    matches.append(fix)
            except re.error:
                continue

        def sort_key(f: Dict[str, Any]) -> tuple:
            project_match = 1 if (project and f.get("project") == project) else 0
            return (project_match, f.get("confidence", 0))

        matches.sort(key=sort_key, reverse=True)
        return matches

    def reload_cache(self) -> None:
        """Re-read ``ai_fixes.json`` from disk."""
        # Cache is loaded fresh on each search_cache() call,
        # but this provides an explicit reload hook.
        pass

    def _load_cache(self) -> List[Dict[str, Any]]:
        if self._cache_path.exists():
            with open(self._cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    # ── Helpers ──────────────────────────────────────────────────────

    def _get_searchable_files(self) -> List[Path]:
        """List all files the grep tool should search."""
        files: List[Path] = []
        if self.history_file.exists():
            files.append(self.history_file)
        if self.golden_dir.exists():
            files.extend(sorted(self.golden_dir.glob("*.txt")))
        return files

    def _line_belongs_to_project(
        self, lines: List[str], line_idx: int, project: str
    ) -> bool:
        """Check if a line falls within a delimited block for *project*."""
        # Walk backward to find the nearest START delimiter.
        for j in range(line_idx, -1, -1):
            m = DELIMITER_START_RE.match(lines[j])
            if m:
                return m.group("project") == project
        return False

    @staticmethod
    def _parse_ts(ts: str) -> datetime:
        ts = ts.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
