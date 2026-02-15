"""
core/tools.py — VaultReader: the read-side API for the Memory Vault.

Provides grep, entry retrieval, time-window slicing, sub-queries,
and Tier 2 synthetic-cache lookups.  Mirrors the Librarian's write-side
API in vault/ingest.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_iso(ts: str) -> datetime:
    """Parse ISO-8601 timestamps, handling the 'Z' suffix that
    Python 3.10's fromisoformat() doesn't support."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ──────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class GrepHit:
    """A single search result from a vault grep."""
    entry_id: str
    line_number: int
    line_content: str
    context_before: str = ""
    context_after: str = ""


# ──────────────────────────────────────────────────────────────────────
# VaultReader
# ──────────────────────────────────────────────────────────────────────

class VaultReader:
    """Read-side companion to ``vault.ingest.Librarian``.

    Loads ``index.json`` and provides search / retrieval methods over
    ``history.txt``, ``golden_snippets/``, and ``ai_fixes.json``.

    Parameters
    ----------
    vault_dir : str | Path
        Root directory of the vault (same path given to Librarian).
    """

    def __init__(self, vault_dir: str | Path) -> None:
        self.vault_dir = Path(vault_dir)
        self.history_file = self.vault_dir / "history.txt"
        self.golden_dir = self.vault_dir / "golden_snippets"
        self._index_path = self.vault_dir / "index.json"
        self._cache_path = self.vault_dir / "ai_fixes.json"
        self._index: Dict[str, Any] = self._load_index()

    # ── Index I/O ────────────────────────────────────────────────────

    def _load_index(self) -> Dict[str, Any]:
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"projects": {}, "golden_snippets": []}

    def reload_index(self) -> None:
        """Re-read ``index.json`` from disk (call after Librarian writes)."""
        self._index = self._load_index()

    # ── Project / Entry listing ──────────────────────────────────────

    def list_projects(self) -> List[str]:
        """Return all project names in the index."""
        return list(self._index.get("projects", {}).keys())

    def list_entries(
        self,
        project: str,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List index entries for a project, optionally filtered by category."""
        proj = self._index.get("projects", {}).get(project)
        if not proj:
            return []
        entries = proj.get("entries", [])
        if category:
            entries = [e for e in entries if e.get("category") == category]
        return entries

    # ── Entry retrieval ──────────────────────────────────────────────

    def get_entry(self, project: str, entry_id: str) -> Optional[str]:
        """Read a single vault entry by project + ID.

        For history entries, slices ``history.txt`` by byte offset.
        For golden snippets, reads the snippet file directly.
        """
        # Check history entries.
        proj = self._index.get("projects", {}).get(project)
        if proj:
            for entry in proj.get("entries", []):
                if entry["id"] == entry_id:
                    return self._read_history_entry(entry)

        # Check golden snippets.
        for snippet in self._index.get("golden_snippets", []):
            if snippet["id"] == entry_id:
                snippet_path = self.golden_dir / f"{entry_id}.txt"
                if snippet_path.exists():
                    return snippet_path.read_text(encoding="utf-8")
        return None

    def _read_history_entry(self, entry: Dict[str, Any]) -> Optional[str]:
        """Read a history.txt entry using byte offsets from the index."""
        if not self.history_file.exists():
            return None
        byte_start = entry.get("byte_start", 0)
        byte_end = entry.get("byte_end", 0)
        with open(self.history_file, "rb") as f:
            f.seek(byte_start)
            data = f.read(byte_end - byte_start)
        return data.decode("utf-8", errors="replace")

    # ── Raw byte read ────────────────────────────────────────────────

    def read_bytes(self, filepath: str, start: int, length: int) -> str:
        """Read raw bytes from any vault file.  Used by the sandbox."""
        p = Path(filepath)
        if not p.exists():
            return ""
        with open(p, "rb") as f:
            f.seek(start)
            data = f.read(length)
        return data.decode("utf-8", errors="replace")

    # ── Grep search ──────────────────────────────────────────────────

    def grep(
        self,
        query: str,
        project: Optional[str] = None,
        context_lines: int = 0,
    ) -> List[GrepHit]:
        """Search ``history.txt`` for lines matching *query*.

        Parameters
        ----------
        query : str
            Plain-text or regex pattern to search for.
        project : str, optional
            If given, only search within entries for this project.
        context_lines : int
            Number of surrounding lines to include.

        Returns
        -------
        list[GrepHit]
        """
        if not self.history_file.exists():
            return []

        # If project-scoped, only search within that project's byte ranges.
        if project:
            return self._grep_project(query, project, context_lines)

        # Full-file search.
        content = self.history_file.read_text(encoding="utf-8")
        return self._grep_text(content, query, context_lines)

    def _grep_project(
        self, query: str, project: str, context_lines: int
    ) -> List[GrepHit]:
        """Grep only within byte ranges belonging to *project*."""
        entries = self.list_entries(project)
        hits: List[GrepHit] = []
        for entry in entries:
            text = self._read_history_entry(entry)
            if text is None:
                continue
            for hit in self._grep_text(text, query, context_lines, entry_id=entry["id"]):
                hits.append(hit)
        return hits

    def _grep_text(
        self,
        text: str,
        query: str,
        context_lines: int = 0,
        entry_id: str = "",
    ) -> List[GrepHit]:
        """Line-by-line grep over a text block."""
        lines = text.split("\n")
        hits: List[GrepHit] = []
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        for i, line in enumerate(lines):
            if pattern.search(line):
                before = "\n".join(lines[max(0, i - context_lines):i]) if context_lines else ""
                after = "\n".join(lines[i + 1:i + 1 + context_lines]) if context_lines else ""
                hits.append(GrepHit(
                    entry_id=entry_id,
                    line_number=i + 1,
                    line_content=line,
                    context_before=before,
                    context_after=after,
                ))
        return hits

    # ── Time-window retrieval ────────────────────────────────────────

    def get_log_window(
        self,
        timestamp: str,
        window_size: int = 3600,
        project: Optional[str] = None,
    ) -> str:
        """Return vault entries within *window_size* seconds of *timestamp*.

        Parameters
        ----------
        timestamp : str
            ISO-8601 center timestamp.
        window_size : int
            Window radius in seconds (default 1 hour).
        project : str, optional
            Limit to entries from this project.
        """
        try:
            center = _parse_iso(timestamp)
        except ValueError:
            return ""

        results: List[str] = []

        projects_to_check = [project] if project else self.list_projects()
        for proj in projects_to_check:
            for entry in self.list_entries(proj):
                try:
                    entry_time = _parse_iso(entry["timestamp"])
                except (ValueError, KeyError):
                    continue

                delta = abs((entry_time - center).total_seconds())
                if delta <= window_size:
                    text = self._read_history_entry(entry)
                    if text:
                        results.append(text)

        return "\n".join(results)

    # ── Sub-query (search within a single entry) ─────────────────────

    def sub_query(
        self, project: str, entry_id: str, pattern: str
    ) -> List[str]:
        """Search within a single entry for lines matching *pattern*.

        Returns the matching lines as a list of strings.
        """
        text = self.get_entry(project, entry_id)
        if text is None:
            return []

        matches: List[str] = []
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            compiled = re.compile(re.escape(pattern), re.IGNORECASE)

        for line in text.split("\n"):
            if compiled.search(line):
                matches.append(line)
        return matches

    # ── Tier 2: Synthetic Cache search ───────────────────────────────

    def search_cache(
        self,
        error_text: str,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search ``ai_fixes.json`` for cached fixes matching an error.

        Uses the same schema as ``Librarian.commit_fix()`` / 
        ``Librarian.search_synthetic_cache()``.
        """
        if not self._cache_path.exists():
            return []

        with open(self._cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)

        matches: List[Dict[str, Any]] = []
        for fix in cache:
            if fix.get("confidence", 0) < min_confidence:
                continue
            try:
                if re.search(fix["error_signature"], error_text, re.IGNORECASE):
                    matches.append(fix)
            except (re.error, KeyError):
                continue

        matches.sort(key=lambda f: f.get("confidence", 0), reverse=True)
        return matches
