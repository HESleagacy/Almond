"""
vault/ingest.py — The Librarian's ingestion engine.

Scrapes raw engineering data (deployment logs, GitHub PRs, golden code)
and writes it into the Memory Vault as grep-optimized flat files.

Data flows into:
  • vault/history.txt     — The massive "State" variable (logs + PRs)
  • vault/golden_snippets/ — Curated, verified configs & scripts
  • vault/index.json       — Lightweight byte-offset index
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────
# Data Hygiene  (strip noise, preserve structure)
# ──────────────────────────────────────────────────────────────────────

_ANSI_RE = re.compile(
    r"\x1b"
    r"(?:"
    r"\[[0-9;]*[a-zA-Z]"          # CSI  (colors, cursor)
    r"|\][^\x07]*\x07"            # OSC  (terminal titles)
    r"|\([\w]"                     # Character-set selection
    r"|[>=<78HMDEFN]"              # Single-char escapes
    r")"
)

_PROGRESS_RE = re.compile(
    r"^.*("
    r"█|▓|▒|░|━|╸|╺"
    r"|\d+%\|"
    r"|Downloading:\s+\d+%"
    r"|Uploading:\s+\d+%"
    r"|\d+(\.\d+)?\s*[kKmMgG][bB]/s"
    r"|ETA\s+\d+:\d+"
    r"|\r.*\d+%"
    r").*$",
    re.MULTILINE,
)

_CR_OVERWRITE_RE = re.compile(r"[^\n]\r(?!\n)")

# File extensions recognized as "golden snippet" candidates.
_GOLDEN_EXTENSIONS = {
    ".yaml", ".yml",    # Helm charts, Kubernetes manifests, CI configs
    ".toml",            # Python / Rust configs
    ".json",            # JSON configs
    ".conf", ".cfg",    # Nginx, systemd, etc.
    ".sh", ".bash",     # Shell scripts
    ".py",              # Python scripts
    ".tf",              # Terraform
    ".Dockerfile",      # Dockerfiles (explicit extension)
}

# Filenames (no extension check) recognized as golden snippets.
_GOLDEN_FILENAMES = {
    "Dockerfile", "Makefile", "Jenkinsfile", "Procfile",
    "docker-compose.yml", "docker-compose.yaml",
    "kustomization.yaml", "kustomization.yml",
    "skaffold.yaml", "helmfile.yaml",
    ".gitlab-ci.yml", ".travis.yml",
}

# Patterns in log filenames that indicate deployment/CI logs.
_LOG_FILE_PATTERNS = re.compile(
    r"(deploy|build|ci|cd|pipeline|release|rollout|kubectl|helm|"
    r"terraform|ansible|argocd|flux|jenkins|github.actions|"
    r"error|crash|incident|postmortem)"
    r".*\.(log|txt|out)$",
    re.IGNORECASE,
)


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape codes, preserving everything else."""
    return _ANSI_RE.sub("", text)


def strip_progress_bars(text: str) -> str:
    """Remove progress-bar lines and carriage-return overwrites."""
    text = _CR_OVERWRITE_RE.sub("", text)
    text = _PROGRESS_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def clean_log(text: str) -> str:
    """Full cleaning pipeline.

    1. ANSI escape removal
    2. Progress-bar line removal
    3. Trailing-whitespace trim per line (leading whitespace preserved)

    Indentation, timestamps, YAML/Python structure are **strictly preserved**.
    """
    text = strip_ansi(text)
    text = strip_progress_bars(text)
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Constants & Delimiters
# ──────────────────────────────────────────────────────────────────────

_DELIMITER_START = "--- START {category} [{timestamp}] [project:{project}] [id:{entry_id}] ---"
_DELIMITER_END   = "--- END {category} [{timestamp}] [id:{entry_id}] ---"

DELIMITER_START_RE = re.compile(
    r"^--- START (?P<category>\S+) "
    r"\[(?P<timestamp>[^\]]+)\] "
    r"\[project:(?P<project>[^\]]+)\] "
    r"\[id:(?P<entry_id>[^\]]+)\] ---$",
    re.MULTILINE,
)

DELIMITER_END_RE = re.compile(
    r"^--- END (?P<category>\S+) "
    r"\[(?P<timestamp>[^\]]+)\] "
    r"\[id:(?P<entry_id>[^\]]+)\] ---$",
    re.MULTILINE,
)


# ──────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class EntryMeta:
    """Metadata for a single vault entry stored in ``index.json``."""
    id: str
    timestamp: str
    byte_start: int
    byte_end: int
    category: str
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# Librarian  (the ingestion engine)
# ──────────────────────────────────────────────────────────────────────

class Librarian:
    """Ingest and store engineering data in the Memory Vault.

    Vault layout (Three-Tiered Search)::

        vault/
        ├── history.txt         # Tier 1: Human-solved successes (logs + PRs)
        ├── golden_snippets/    # Tier 1: Curated verified configs
        ├── ai_fixes.json       # Tier 2: Synthetic Cache (AI-generated fixes)
        ├── index.json          # Byte-offset metadata index
        └── ingest.py           # (this file)

    Search Hierarchy::

        Tier 1 → history.txt    (high-fidelity human solutions)
        Tier 2 → ai_fixes.json  (previously synthesized AI fixes)
        Tier 3 → De Novo        (Person 2's engine generates from scratch)

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
        self._ensure_structure()
        self._index: Dict[str, Any] = self._load_index()
        self._cache: List[Dict[str, Any]] = self._load_cache()

    # ── Bootstrap ────────────────────────────────────────────────────

    def _ensure_structure(self) -> None:
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.golden_dir.mkdir(exist_ok=True)
        if not self.history_file.exists():
            self.history_file.touch()

    # ── Index I/O ────────────────────────────────────────────────────

    def _load_index(self) -> Dict[str, Any]:
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"projects": {}, "golden_snippets": []}

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _ensure_project(self, project: str) -> Dict[str, Any]:
        projects = self._index.setdefault("projects", {})
        if project not in projects:
            projects[project] = {"entries": []}
        return projects[project]

    # ── Synthetic Cache I/O (Tier 2) ─────────────────────────────────

    def _load_cache(self) -> List[Dict[str, Any]]:
        if self._cache_path.exists():
            with open(self._cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_cache(self) -> None:
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, ensure_ascii=False)

    # ── Core append (writes to history.txt) ──────────────────────────

    def _append_to_history(
        self,
        project: str,
        category: str,
        content: str,
        timestamp: str,
        tags: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> EntryMeta:
        """Append a delimited entry to ``history.txt`` and update the index."""
        proj = self._ensure_project(project)
        entry_id = uuid.uuid4().hex[:12]
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        header = _DELIMITER_START.format(
            category=category.upper(),
            timestamp=ts,
            project=project,
            entry_id=entry_id,
        )
        footer = _DELIMITER_END.format(
            category=category.upper(),
            timestamp=ts,
            entry_id=entry_id,
        )

        block = f"{header}\n{content}\n{footer}\n"

        # Record byte position before writing.
        byte_start = self.history_file.stat().st_size

        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(block)

        byte_end = self.history_file.stat().st_size

        meta = EntryMeta(
            id=entry_id,
            timestamp=ts,
            byte_start=byte_start,
            byte_end=byte_end,
            category=category,
            tags=tags or [],
            extra=extra or {},
        )
        proj["entries"].append(asdict(meta))
        self._save_index()
        return meta

    # ── Public Ingestion API ─────────────────────────────────────────

    def ingest_deployment_log(
        self,
        project: str,
        raw_text: str,
        timestamp: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> EntryMeta:
        """Clean and store a deployment log entry in ``history.txt``.

        Parameters
        ----------
        project : str
            Project name (used as the index key).
        raw_text : str
            Raw log output — ANSI stripped, progress bars removed,
            indentation preserved.
        timestamp : str, optional
            ISO-8601 timestamp.  Defaults to ``now(UTC)``.
        tags : list[str], optional
            Freeform tags (e.g. ``["error:OOM", "env:prod"]``).
        """
        cleaned = clean_log(raw_text)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        return self._append_to_history(project, "deployment_log", cleaned, ts, tags)

    def ingest_pull_request(
        self,
        project: str,
        raw_diff: str,
        comments: str = "",
        pr_number: Optional[int] = None,
        timestamp: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> EntryMeta:
        """Clean and store a GitHub PR (diff + review comments) in ``history.txt``."""
        cleaned_diff = clean_log(raw_diff)
        cleaned_comments = clean_log(comments) if comments else ""

        sections = [f"[PR #{pr_number}]" if pr_number else "[PR]"]
        sections.append("")
        sections.append("=== DIFF ===")
        sections.append(cleaned_diff)
        if cleaned_comments:
            sections.append("")
            sections.append("=== COMMENTS ===")
            sections.append(cleaned_comments)

        content = "\n".join(sections)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        extra = {"pr_number": pr_number} if pr_number else {}
        return self._append_to_history(project, "pull_request", content, ts, tags, extra)

    def ingest_golden_code(
        self,
        project: str,
        code: str,
        description: str = "",
        language: str = "",
        tags: Optional[List[str]] = None,
    ) -> EntryMeta:
        """Store a verified config/script as a golden snippet file.

        Golden code goes to ``vault/golden_snippets/<id>.txt`` (not
        ``history.txt``) since these are curated, stable references.
        """
        cleaned = strip_ansi(code)
        entry_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()

        # Build the golden snippet file content.
        lines = []
        lines.append(f"# Project: {project}")
        if description:
            lines.append(f"# Description: {description}")
        if language:
            lines.append(f"# Language: {language}")
        if tags:
            lines.append(f"# Tags: {', '.join(tags)}")
        lines.append(f"# Timestamp: {ts}")
        lines.append("")
        lines.append(cleaned)

        snippet_path = self.golden_dir / f"{entry_id}.txt"
        snippet_path.write_text("\n".join(lines), encoding="utf-8")

        byte_end = snippet_path.stat().st_size
        meta = EntryMeta(
            id=entry_id,
            timestamp=ts,
            byte_start=0,
            byte_end=byte_end,
            category="golden_code",
            tags=tags or [],
            extra={"project": project, "language": language, "description": description},
        )

        self._index.setdefault("golden_snippets", []).append(asdict(meta))
        self._ensure_project(project)
        self._save_index()
        return meta

    # ══════════════════════════════════════════════════════════════════
    # TIER 2: SYNTHETIC CACHE  (AI-generated fixes)
    # ══════════════════════════════════════════════════════════════════

    def commit_fix(
        self,
        error_signature: str,
        fix_description: str,
        fix_code: str = "",
        project: str = "",
        confidence: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Store an AI-synthesized fix in the Synthetic Cache (Tier 2).

        Called by Person 2's engine after Tier 3 (de novo synthesis)
        produces a validated fix.  The next time a similar error appears,
        Tier 2 can return this fix immediately — no re-derivation needed.

        Parameters
        ----------
        error_signature : str
            A regex-compatible pattern that describes the error
            (e.g. ``"OOM.*worker.*pool"`` or ``"connection refused.*5432"``).
            Future errors are matched against this signature.
        fix_description : str
            Human-readable description of the fix.
        fix_code : str, optional
            The actual code/config change that resolves the error.
        project : str, optional
            Which project this fix originated from (empty = cross-project).
        confidence : float, optional
            Confidence score (0.0–1.0) assigned by the engine.
        tags : list[str], optional
            Freeform tags.

        Returns
        -------
        dict
            The cached fix record (includes generated ID and timestamp).
        """
        fix_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()

        record = {
            "id": fix_id,
            "timestamp": ts,
            "error_signature": error_signature,
            "fix_description": fix_description,
            "fix_code": fix_code,
            "project": project,
            "confidence": confidence,
            "tags": tags or [],
            "times_matched": 0,
        }

        self._cache.append(record)
        self._save_cache()
        return record

    def search_synthetic_cache(
        self,
        error_text: str,
        project: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search the Synthetic Cache for fixes matching an error.

        Uses regex to compare *error_text* against stored error
        signatures.  Returns matches ranked by confidence score
        (highest first).

        This is the Tier 2 lookup — called when Tier 1 (history.txt)
        finds no human-solved match.

        Parameters
        ----------
        error_text : str
            The current error message / log snippet.
        project : str, optional
            If given, prefer fixes from this project (but still return
            cross-project matches).
        min_confidence : float
            Minimum confidence threshold (0.0–1.0).

        Returns
        -------
        list[dict]
            Matching fix records, sorted by confidence descending.
        """
        matches: List[Dict[str, Any]] = []

        for fix in self._cache:
            if fix.get("confidence", 0) < min_confidence:
                continue

            try:
                if re.search(fix["error_signature"], error_text, re.IGNORECASE):
                    matches.append(fix)
            except re.error:
                # Bad regex in stored signature — skip it.
                continue

        # Sort: project-specific matches first, then by confidence.
        def sort_key(f: Dict[str, Any]) -> tuple:
            project_match = 1 if (project and f.get("project") == project) else 0
            return (project_match, f.get("confidence", 0))

        matches.sort(key=sort_key, reverse=True)
        return matches

    def bump_cache_hit(self, fix_id: str) -> None:
        """Increment the ``times_matched`` counter for a cached fix.

        Called when a Tier 2 fix is successfully applied, so frequently
        useful fixes float to the top.
        """
        for fix in self._cache:
            if fix["id"] == fix_id:
                fix["times_matched"] = fix.get("times_matched", 0) + 1
                self._save_cache()
                return

    # ══════════════════════════════════════════════════════════════════
    # SCRAPING  (automated data gathering from real sources)
    # ══════════════════════════════════════════════════════════════════

    def scrape_log_directory(
        self,
        directory: str | Path,
        project: str,
        pattern: Optional[str] = None,
        recursive: bool = True,
    ) -> List[EntryMeta]:
        """Scan a directory for deployment/CI log files and ingest them.

        Automatically detects files that look like deployment logs
        (by filename pattern) and ingests each one as a separate entry
        in ``history.txt``.

        Parameters
        ----------
        directory : str | Path
            Path to scan for log files.
        project : str
            Project name for all ingested entries.
        pattern : str, optional
            Glob pattern override (e.g. ``"**/*.log"``).  If None, uses
            built-in heuristics to detect deployment log files.
        recursive : bool
            Whether to search subdirectories.

        Returns
        -------
        list[EntryMeta]
            Metadata for each ingested log file.
        """
        directory = Path(directory)
        results: List[EntryMeta] = []

        if pattern:
            # User-specified glob.
            files = sorted(directory.rglob(pattern) if recursive else directory.glob(pattern))
        else:
            # Auto-detect: all .log/.txt/.out files, then filter by name.
            glob_fn = directory.rglob if recursive else directory.glob
            candidates = []
            for ext in ("*.log", "*.txt", "*.out"):
                candidates.extend(glob_fn(ext))
            files = sorted(f for f in candidates if _LOG_FILE_PATTERNS.search(f.name))

        for filepath in files:
            if not filepath.is_file():
                continue

            try:
                raw_text = filepath.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue

            if not raw_text.strip():
                continue

            # Use file modification time as the timestamp.
            mtime = datetime.fromtimestamp(
                filepath.stat().st_mtime, tz=timezone.utc
            ).isoformat()

            # Auto-tag based on filename.
            tags = [f"source:{filepath.name}"]
            lower_name = filepath.name.lower()
            if "error" in lower_name or "crash" in lower_name or "incident" in lower_name:
                tags.append("status:failed")
            elif "success" in lower_name or "complete" in lower_name:
                tags.append("status:success")

            meta = self.ingest_deployment_log(
                project=project,
                raw_text=raw_text,
                timestamp=mtime,
                tags=tags,
            )
            results.append(meta)

        return results

    def scrape_git_log(
        self,
        repo_path: str | Path,
        project: str,
        max_commits: int = 200,
        since: Optional[str] = None,
        grep_filter: Optional[str] = None,
    ) -> List[EntryMeta]:
        """Extract git history from a local repo and ingest into the vault.

        Captures each commit as a deployment log entry with its full
        diff, so the RLM can trace "Error A led to Fix B" across the
        commit timeline.

        Parameters
        ----------
        repo_path : str | Path
            Path to the local git repository.
        project : str
            Project name for indexing.
        max_commits : int
            Maximum number of commits to extract.
        since : str, optional
            Only include commits after this date (e.g. ``"2024-01-01"``).
        grep_filter : str, optional
            Only include commits whose message matches this pattern
            (e.g. ``"deploy|hotfix|fix|revert"``).

        Returns
        -------
        list[EntryMeta]
            Metadata for each ingested commit.
        """
        repo_path = Path(repo_path)
        results: List[EntryMeta] = []

        # Build the git log command.
        cmd = [
            "git", "-C", str(repo_path), "log",
            f"-n{max_commits}",
            "--format=---COMMIT_SEP---%n%H%n%aI%n%an%n%s%n---COMMIT_MSG_START---%n%b%n---COMMIT_MSG_END---",
            "-p",  # include diffs
        ]
        if since:
            cmd.append(f"--since={since}")
        if grep_filter:
            cmd.extend(["--grep", grep_filter, "-i"])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return results

        if result.returncode != 0:
            return results

        # Parse the output into individual commits.
        raw_commits = result.stdout.split("---COMMIT_SEP---")

        for raw_commit in raw_commits:
            raw_commit = raw_commit.strip()
            if not raw_commit:
                continue

            lines = raw_commit.split("\n")
            if len(lines) < 4:
                continue

            commit_hash = lines[0].strip()
            timestamp = lines[1].strip()
            author = lines[2].strip()
            subject = lines[3].strip()

            # Extract the body (between MSG_START and MSG_END) and the diff.
            full_text = "\n".join(lines)
            body = ""
            msg_start = full_text.find("---COMMIT_MSG_START---")
            msg_end = full_text.find("---COMMIT_MSG_END---")
            if msg_start != -1 and msg_end != -1:
                body = full_text[msg_start + len("---COMMIT_MSG_START---"):msg_end].strip()

            diff_start = msg_end + len("---COMMIT_MSG_END---") if msg_end != -1 else 0
            diff = full_text[diff_start:].strip()

            # Build the content block.
            sections = [
                f"[COMMIT {commit_hash[:8]}] {subject}",
                f"Author: {author}",
                f"Date:   {timestamp}",
            ]
            if body:
                sections.append("")
                sections.append(body)
            if diff:
                sections.append("")
                sections.append("=== DIFF ===")
                sections.append(diff)

            content = "\n".join(sections)

            # Auto-tag.
            tags = [f"commit:{commit_hash[:8]}", f"author:{author}"]
            lower_subj = subject.lower()
            if any(kw in lower_subj for kw in ("fix", "bug", "hotfix", "patch")):
                tags.append("type:fix")
            if any(kw in lower_subj for kw in ("deploy", "release", "rollout")):
                tags.append("type:deploy")
            if any(kw in lower_subj for kw in ("revert", "rollback")):
                tags.append("type:revert")

            meta = self._append_to_history(
                project=project,
                category="git_commit",
                content=content,
                timestamp=timestamp,
                tags=tags,
                extra={"commit": commit_hash, "author": author, "subject": subject},
            )
            results.append(meta)

        return results

    def extract_golden_snippets(
        self,
        directory: str | Path,
        project: str,
        recursive: bool = True,
    ) -> List[EntryMeta]:
        """Scan a directory for "golden" configs and scripts, and ingest them.

        Automatically detects files that look like verified
        infrastructure configs: Helm charts, Dockerfiles, CI configs,
        Kubernetes manifests, Terraform files, deployment scripts, etc.

        Parameters
        ----------
        directory : str | Path
            Path to scan (e.g. a repo root, a ``deploy/`` folder).
        project : str
            Project name for indexing.
        recursive : bool
            Whether to search subdirectories.

        Returns
        -------
        list[EntryMeta]
            Metadata for each ingested golden snippet.
        """
        directory = Path(directory)
        results: List[EntryMeta] = []
        seen: set = set()

        glob_fn = directory.rglob if recursive else directory.glob

        for filepath in sorted(glob_fn("*")):
            if not filepath.is_file():
                continue

            # Skip hidden dirs, vendor, node_modules, __pycache__, etc.
            parts = filepath.relative_to(directory).parts
            if any(p.startswith(".") or p in ("vendor", "node_modules", "__pycache__", ".git") for p in parts):
                continue

            # Check if this file qualifies as a golden snippet.
            is_golden = (
                filepath.name in _GOLDEN_FILENAMES
                or filepath.suffix in _GOLDEN_EXTENSIONS
            )
            if not is_golden:
                continue

            # Avoid duplicates.
            real = filepath.resolve()
            if real in seen:
                continue
            seen.add(real)

            try:
                code = filepath.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue

            if not code.strip():
                continue

            # Detect language from extension.
            ext_to_lang = {
                ".yaml": "yaml", ".yml": "yaml",
                ".json": "json", ".toml": "toml",
                ".py": "python", ".sh": "bash", ".bash": "bash",
                ".tf": "terraform", ".conf": "config", ".cfg": "config",
            }
            language = ext_to_lang.get(filepath.suffix, filepath.suffix.lstrip("."))
            if filepath.name == "Dockerfile":
                language = "dockerfile"
            elif filepath.name == "Makefile":
                language = "makefile"

            # Build a description from the relative path.
            rel_path = filepath.relative_to(directory)
            description = str(rel_path)

            # Auto-tag.
            tags = [f"source:{rel_path}"]
            lower_name = filepath.name.lower()
            if "helm" in lower_name or "chart" in str(rel_path).lower():
                tags.append("type:helm")
            if "docker" in lower_name:
                tags.append("type:docker")
            if "kube" in lower_name or "k8s" in lower_name:
                tags.append("type:kubernetes")

            meta = self.ingest_golden_code(
                project=project,
                code=code,
                description=description,
                language=language,
                tags=tags,
            )
            results.append(meta)

        return results

    # ── Index Rebuild (disaster recovery) ────────────────────────────

    def rebuild_index(self) -> Dict[str, Any]:
        """Scan ``history.txt`` and ``golden_snippets/`` to rebuild ``index.json``.

        Useful for disaster recovery or after manual edits.
        """
        new_index: Dict[str, Any] = {"projects": {}, "golden_snippets": []}

        # ── Rebuild from history.txt ─────────────────────────────────
        if self.history_file.exists():
            raw = self.history_file.read_text(encoding="utf-8")

            for m_start in DELIMITER_START_RE.finditer(raw):
                entry_id = m_start.group("entry_id")
                timestamp = m_start.group("timestamp")
                category = m_start.group("category").lower()
                project = m_start.group("project")

                char_start = m_start.start()
                byte_start = len(raw[:char_start].encode("utf-8"))

                end_pattern = re.compile(
                    rf"^--- END {re.escape(category.upper())} "
                    rf"\[{re.escape(timestamp)}\] "
                    rf"\[id:{re.escape(entry_id)}\] ---$",
                    re.MULTILINE,
                )
                m_end = end_pattern.search(raw, m_start.end())
                if m_end:
                    char_end = m_end.end()
                    byte_end = len(raw[:char_end].encode("utf-8")) + 1
                else:
                    byte_end = len(raw.encode("utf-8"))

                if project not in new_index["projects"]:
                    new_index["projects"][project] = {"entries": []}

                new_index["projects"][project]["entries"].append({
                    "id": entry_id,
                    "timestamp": timestamp,
                    "byte_start": byte_start,
                    "byte_end": byte_end,
                    "category": category,
                    "tags": [],
                    "extra": {},
                })

        # ── Rebuild from golden_snippets/ ────────────────────────────
        if self.golden_dir.exists():
            for snippet_file in sorted(self.golden_dir.glob("*.txt")):
                entry_id = snippet_file.stem
                content = snippet_file.read_text(encoding="utf-8")
                byte_end = snippet_file.stat().st_size

                # Parse header comments for metadata.
                project = ""
                language = ""
                description = ""
                timestamp = ""
                tags: List[str] = []
                for line in content.split("\n"):
                    if line.startswith("# Project:"):
                        project = line.split(":", 1)[1].strip()
                    elif line.startswith("# Language:"):
                        language = line.split(":", 1)[1].strip()
                    elif line.startswith("# Description:"):
                        description = line.split(":", 1)[1].strip()
                    elif line.startswith("# Timestamp:"):
                        timestamp = line.split(":", 1)[1].strip()
                    elif line.startswith("# Tags:"):
                        tags = [t.strip() for t in line.split(":", 1)[1].split(",")]
                    elif not line.startswith("#"):
                        break

                new_index["golden_snippets"].append({
                    "id": entry_id,
                    "timestamp": timestamp,
                    "byte_start": 0,
                    "byte_end": byte_end,
                    "category": "golden_code",
                    "tags": tags,
                    "extra": {"project": project, "language": language, "description": description},
                })

                if project:
                    if project not in new_index["projects"]:
                        new_index["projects"][project] = {"entries": []}

        self._index = new_index
        self._save_index()
        return new_index
