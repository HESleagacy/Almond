"""
Tests for the Almond Memory Vault.

Covers data hygiene, ingestion round-trips, index integrity, search &
retrieval, and edge cases — updated for the new project structure
(vault/ingest.py + core/tools.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vault.ingest import Librarian, clean_log, strip_ansi, strip_progress_bars
from core.tools import VaultReader


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def librarian(vault_dir: Path) -> Librarian:
    return Librarian(vault_dir)


@pytest.fixture
def reader(vault_dir: Path) -> VaultReader:
    return VaultReader(vault_dir)


# ======================================================================
# 1. Hygiene tests
# ======================================================================

class TestStripAnsi:
    def test_removes_color_codes(self):
        text = "\x1b[31mERROR\x1b[0m: something broke"
        assert strip_ansi(text) == "ERROR: something broke"

    def test_removes_cursor_movement(self):
        text = "\x1b[2J\x1b[HWelcome"
        assert strip_ansi(text) == "Welcome"

    def test_preserves_plain_text(self):
        text = "Nothing special here"
        assert strip_ansi(text) == text

    def test_preserves_indentation(self):
        text = "    \x1b[32mindented line\x1b[0m"
        assert strip_ansi(text) == "    indented line"


class TestStripProgressBars:
    def test_removes_tqdm_bar(self):
        text = "Starting download\n 50%|█████     | 5/10 [00:05]\nDone"
        result = strip_progress_bars(text)
        assert "50%|" not in result
        assert "Starting download" in result
        assert "Done" in result

    def test_removes_download_lines(self):
        text = "Pulling image\nDownloading: 75% complete\nComplete"
        result = strip_progress_bars(text)
        assert "Downloading:" not in result
        assert "Complete" in result

    def test_preserves_normal_percentages(self):
        text = "CPU usage is at 80% today"
        result = strip_progress_bars(text)
        assert "80%" in result


class TestCleanLog:
    def test_full_pipeline(self):
        raw = (
            "\x1b[36m2025-01-15T10:30:00Z\x1b[0m INFO Starting deploy\n"
            " 75%|███████   | 15/20 [00:10]\n"
            "  config:\n"
            "    replicas: 3\n"
            "    image: myapp:v2   \n"
        )
        result = clean_log(raw)
        assert "2025-01-15T10:30:00Z" in result
        assert "\x1b" not in result
        assert "75%|" not in result
        assert "    replicas: 3" in result
        assert "image: myapp:v2" in result

    def test_preserves_yaml_structure(self):
        yaml_text = (
            "apiVersion: v1\n"
            "kind: ConfigMap\n"
            "metadata:\n"
            "  name: my-config\n"
            "  namespace: default\n"
            "data:\n"
            "  key: value\n"
        )
        result = clean_log(yaml_text)
        assert result.strip() == yaml_text.strip()


# ======================================================================
# 2. Ingestion round-trip tests
# ======================================================================

class TestIngestion:
    def test_ingest_deployment_log_roundtrip(self, librarian: Librarian, reader: VaultReader):
        meta = librarian.ingest_deployment_log(
            project="myapp",
            raw_text="2025-01-15 Deploy started\nAll pods healthy",
            timestamp="2025-01-15T10:30:00Z",
            tags=["env:prod"],
        )
        reader.reload_index()

        content = reader.get_entry("myapp", meta.id)
        assert content is not None
        assert "Deploy started" in content
        assert "All pods healthy" in content

    def test_ingest_pull_request_roundtrip(self, librarian: Librarian, reader: VaultReader):
        meta = librarian.ingest_pull_request(
            project="myapp",
            raw_diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new",
            comments="LGTM! Ship it.",
            pr_number=42,
            timestamp="2025-01-16T08:00:00Z",
        )
        reader.reload_index()

        content = reader.get_entry("myapp", meta.id)
        assert content is not None
        assert "PR #42" in content
        assert "+new" in content
        assert "LGTM" in content

    def test_ingest_golden_code_roundtrip(self, librarian: Librarian, reader: VaultReader):
        code = 'server {\n  listen 80;\n  location / {\n    proxy_pass http://app:8080;\n  }\n}'
        meta = librarian.ingest_golden_code(
            project="infra",
            code=code,
            description="Nginx reverse proxy config",
            language="nginx",
            tags=["type:config"],
        )
        reader.reload_index()

        content = reader.get_entry("infra", meta.id)
        assert content is not None
        assert "proxy_pass" in content
        assert "Nginx reverse proxy" in content

    def test_ingest_writes_to_history_txt(self, librarian: Librarian, vault_dir: Path):
        """Deployment logs and PRs go into the single history.txt file."""
        librarian.ingest_deployment_log("svc", "log data", "2025-01-01T00:00:00Z")
        librarian.ingest_pull_request("svc", "diff data", pr_number=7)

        history = (vault_dir / "history.txt").read_text(encoding="utf-8")
        assert "--- START DEPLOYMENT_LOG" in history
        assert "--- START PULL_REQUEST" in history
        assert "log data" in history
        assert "diff data" in history

    def test_golden_code_goes_to_snippets_dir(self, librarian: Librarian, vault_dir: Path):
        """Golden code goes to golden_snippets/, not history.txt."""
        meta = librarian.ingest_golden_code("infra", "code here", language="yaml")
        snippet = vault_dir / "golden_snippets" / f"{meta.id}.txt"
        assert snippet.exists()
        assert "code here" in snippet.read_text(encoding="utf-8")

    def test_list_projects_after_ingest(self, librarian: Librarian, reader: VaultReader):
        librarian.ingest_deployment_log("alpha", "log A", "2025-01-01T00:00:00Z")
        librarian.ingest_deployment_log("beta", "log B", "2025-01-02T00:00:00Z")
        reader.reload_index()

        projects = reader.list_projects()
        assert "alpha" in projects
        assert "beta" in projects


# ======================================================================
# 3. Index integrity tests
# ======================================================================

class TestIndexIntegrity:
    def test_byte_offsets_are_accurate(self, librarian: Librarian, vault_dir: Path):
        meta = librarian.ingest_deployment_log(
            project="svc",
            raw_text="Line one\nLine two\nLine three",
            timestamp="2025-03-01T00:00:00Z",
        )
        with open(vault_dir / "history.txt", "rb") as f:
            f.seek(meta.byte_start)
            data = f.read(meta.byte_end - meta.byte_start)

        text = data.decode("utf-8")
        assert "Line one" in text
        assert "Line three" in text
        assert "--- START DEPLOYMENT_LOG" in text

    def test_rebuild_index_matches_original(self, librarian: Librarian, vault_dir: Path):
        librarian.ingest_deployment_log("proj1", "log 1", "2025-01-01T00:00:00Z")
        librarian.ingest_deployment_log("proj1", "log 2", "2025-01-02T00:00:00Z")
        librarian.ingest_pull_request("proj1", "diff", "comment", 10, "2025-01-03T00:00:00Z")

        with open(vault_dir / "index.json", "r") as f:
            original = json.load(f)

        original_count = len(original["projects"]["proj1"]["entries"])

        librarian.rebuild_index()
        with open(vault_dir / "index.json", "r") as f:
            rebuilt = json.load(f)

        rebuilt_count = len(rebuilt["projects"]["proj1"]["entries"])
        assert rebuilt_count == original_count
        assert set(rebuilt["projects"].keys()) == set(original["projects"].keys())


# ======================================================================
# 4. Search & retrieval tests
# ======================================================================

class TestSearch:
    def test_grep_by_keyword(self, librarian: Librarian, reader: VaultReader):
        librarian.ingest_deployment_log(
            "myapp", "2025-01-15 ERROR: OOM killed\nRestarting pod",
            "2025-01-15T10:00:00Z",
        )
        librarian.ingest_deployment_log(
            "myapp", "2025-01-16 INFO: Deploy successful",
            "2025-01-16T10:00:00Z",
        )
        reader.reload_index()

        hits = reader.grep("ERROR", project="myapp")
        assert len(hits) >= 1
        assert any("OOM killed" in h.line_content for h in hits)

    def test_grep_with_context(self, librarian: Librarian, reader: VaultReader):
        librarian.ingest_deployment_log(
            "myapp", "line A\nline B\nERROR: failure\nline D\nline E",
            "2025-01-15T10:00:00Z",
        )
        reader.reload_index()

        hits = reader.grep("ERROR: failure", project="myapp", context_lines=2)
        assert len(hits) >= 1
        hit = hits[0]
        assert "line B" in hit.context_before
        assert "line D" in hit.context_after

    def test_get_log_window(self, librarian: Librarian, reader: VaultReader):
        librarian.ingest_deployment_log("svc", "early log", "2025-06-01T10:00:00Z")
        librarian.ingest_deployment_log("svc", "target log", "2025-06-01T12:00:00Z")
        librarian.ingest_deployment_log("svc", "late log", "2025-06-02T10:00:00Z")
        reader.reload_index()

        result = reader.get_log_window("2025-06-01T12:00:00Z", window_size=7200, project="svc")
        assert "target log" in result
        assert "early log" in result
        assert "late log" not in result

    def test_read_bytes(self, librarian: Librarian, reader: VaultReader, vault_dir: Path):
        librarian.ingest_deployment_log("svc", "hello world", "2025-01-01T00:00:00Z")
        reader.reload_index()

        content = reader.read_bytes(str(vault_dir / "history.txt"), 0, 50)
        assert "START DEPLOYMENT_LOG" in content

    def test_sub_query(self, librarian: Librarian, reader: VaultReader):
        meta = librarian.ingest_deployment_log(
            "myapp", "line1\nERROR: bad\nline3\nERROR: worse\nline5",
            "2025-01-01T00:00:00Z",
        )
        reader.reload_index()

        matches = reader.sub_query("myapp", meta.id, "ERROR")
        assert len(matches) == 2
        assert any("bad" in m for m in matches)
        assert any("worse" in m for m in matches)


# ======================================================================
# 5. Edge cases
# ======================================================================

class TestEdgeCases:
    def test_empty_vault_list_projects(self, reader: VaultReader):
        assert reader.list_projects() == []

    def test_empty_vault_search(self, reader: VaultReader):
        assert reader.grep("anything") == []

    def test_nonexistent_project_entries(self, reader: VaultReader):
        assert reader.list_entries("nonexistent") == []

    def test_nonexistent_entry_id(self, reader: VaultReader):
        assert reader.get_entry("nonexistent", "badid") is None

    def test_multiple_entries_append_correctly(self, librarian: Librarian, reader: VaultReader):
        librarian.ingest_deployment_log("svc", "first entry", "2025-01-01T00:00:00Z")
        librarian.ingest_deployment_log("svc", "second entry", "2025-01-02T00:00:00Z")
        librarian.ingest_deployment_log("svc", "third entry", "2025-01-03T00:00:00Z")
        reader.reload_index()

        entries = reader.list_entries("svc", category="deployment_log")
        assert len(entries) == 3

        for entry in entries:
            content = reader.get_entry("svc", entry["id"])
            assert content is not None

    def test_unicode_content(self, librarian: Librarian, reader: VaultReader):
        librarian.ingest_deployment_log(
            "intl", "日本語ログ: デプロイ成功 ✅\nEmoji: 🚀🔥",
            "2025-01-01T00:00:00Z",
        )
        reader.reload_index()

        hits = reader.grep("デプロイ", project="intl")
        assert len(hits) >= 1


# ======================================================================
# 6. Scraping automation tests
# ======================================================================

class TestScrapeLogDirectory:
    """Tests for Librarian.scrape_log_directory()."""

    def test_auto_detect_deploy_logs(self, librarian: Librarian, reader: VaultReader, tmp_path: Path):
        """Auto-detects files with deployment-related names."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # These should be detected (deploy/build/error in name + .log/.txt).
        (log_dir / "deploy-2025-01-15.log").write_text("Pod myapp-abc restarted\nOOM killed")
        (log_dir / "ci-build-output.txt").write_text("Step 1/5: Building image\nStep 5/5: Done")
        (log_dir / "error-report.log").write_text("FATAL: connection refused\nRetrying...")

        # These should NOT be detected (don't match).
        (log_dir / "notes.txt").write_text("meeting notes")
        (log_dir / "readme.md").write_text("# README")

        results = librarian.scrape_log_directory(log_dir, project="myapp")
        reader.reload_index()

        assert len(results) == 3
        projects = reader.list_projects()
        assert "myapp" in projects

        # Verify the error log was tagged as failed.
        error_entry = [r for r in results if "status:failed" in r.tags]
        assert len(error_entry) >= 1

    def test_custom_glob_pattern(self, librarian: Librarian, tmp_path: Path):
        """User can override auto-detect with a custom glob pattern."""
        log_dir = tmp_path / "custom"
        log_dir.mkdir()
        (log_dir / "app.log").write_text("some log data")
        (log_dir / "app.csv").write_text("col1,col2")

        results = librarian.scrape_log_directory(log_dir, project="x", pattern="*.log")
        assert len(results) == 1

    def test_empty_directory_returns_nothing(self, librarian: Librarian, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        results = librarian.scrape_log_directory(empty_dir, project="x")
        assert results == []


class TestExtractGoldenSnippets:
    """Tests for Librarian.extract_golden_snippets()."""

    def test_detects_infra_configs(self, librarian: Librarian, reader: VaultReader, tmp_path: Path):
        """Finds Dockerfiles, YAML configs, shell scripts, etc."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / "Dockerfile").write_text("FROM python:3.12\nCOPY . .\nCMD ['python', 'app.py']")
        (repo / "deploy.yaml").write_text("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: myapp")
        (repo / "setup.sh").write_text("#!/bin/bash\nhelm upgrade --install myapp ./chart")

        # This should be skipped (hidden dir).
        hidden = repo / ".git"
        hidden.mkdir()
        (hidden / "config").write_text("should be ignored")

        results = librarian.extract_golden_snippets(repo, project="infra")
        reader.reload_index()

        assert len(results) == 3
        # Check that language was detected.
        languages = {r.extra.get("language") for r in results}
        assert "dockerfile" in languages
        assert "yaml" in languages
        assert "bash" in languages

    def test_auto_tags_docker_and_k8s(self, librarian: Librarian, tmp_path: Path):
        """Docker/Kubernetes files get auto-tagged."""
        repo = tmp_path / "infra"
        repo.mkdir()
        (repo / "Dockerfile").write_text("FROM node:18")

        results = librarian.extract_golden_snippets(repo, project="web")
        assert len(results) == 1
        assert "type:docker" in results[0].tags

    def test_empty_dir(self, librarian: Librarian, tmp_path: Path):
        empty = tmp_path / "nothing"
        empty.mkdir()
        assert librarian.extract_golden_snippets(empty, project="x") == []


class TestScrapeGitLog:
    """Tests for Librarian.scrape_git_log()."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a tiny git repo with 3 commits for testing."""
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, capture_output=True)

        # Commit 1: initial
        (repo / "app.py").write_text("print('v1')")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, capture_output=True)

        # Commit 2: fix
        (repo / "app.py").write_text("print('v2')  # fixed OOM bug")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Fix: OOM bug in worker pool"], cwd=repo, capture_output=True)

        # Commit 3: deploy
        (repo / "app.py").write_text("print('v3')  # deployed")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Deploy v3 to production"], cwd=repo, capture_output=True)

        return repo

    def test_scrape_all_commits(self, librarian: Librarian, reader: VaultReader, git_repo: Path):
        results = librarian.scrape_git_log(git_repo, project="app")
        reader.reload_index()

        assert len(results) == 3
        assert "app" in reader.list_projects()

        # The fix commit should be tagged as type:fix.
        fix_entries = [r for r in results if "type:fix" in r.tags]
        assert len(fix_entries) >= 1

        # The deploy commit should be tagged as type:deploy.
        deploy_entries = [r for r in results if "type:deploy" in r.tags]
        assert len(deploy_entries) >= 1

    def test_grep_filter(self, librarian: Librarian, git_repo: Path):
        """The grep_filter param should limit commits to matching messages."""
        results = librarian.scrape_git_log(git_repo, project="app", grep_filter="Fix")
        assert len(results) == 1
        assert "OOM" in results[0].extra.get("subject", "")

    def test_nonexistent_repo_returns_empty(self, librarian: Librarian, tmp_path: Path):
        results = librarian.scrape_git_log(tmp_path / "nonexistent", project="x")
        assert results == []


# ======================================================================
# 7. Tier 2: Synthetic Cache tests
# ======================================================================

class TestSyntheticCache:
    """Tests for the ai_fixes.json Synthetic Cache (Tier 2)."""

    def test_commit_fix_roundtrip(self, librarian: Librarian):
        """A committed fix should be searchable by error text."""
        librarian.commit_fix(
            error_signature=r"OOM.*worker.*pool",
            fix_description="Increase memory limits from 512Mi to 2Gi",
            fix_code="resources:\n  limits:\n    memory: 2Gi",
            project="myapp",
            confidence=0.85,
            tags=["type:oom"],
        )

        hits = librarian.search_synthetic_cache("ERROR: OOM killed in worker pool process")
        assert len(hits) == 1
        assert hits[0]["fix_description"] == "Increase memory limits from 512Mi to 2Gi"
        assert hits[0]["confidence"] == 0.85

    def test_no_match_returns_empty(self, librarian: Librarian):
        librarian.commit_fix(
            error_signature=r"OOM.*worker",
            fix_description="OOM fix",
            confidence=0.9,
        )
        hits = librarian.search_synthetic_cache("connection refused on port 5432")
        assert hits == []

    def test_confidence_filtering(self, librarian: Librarian):
        librarian.commit_fix(error_signature="timeout", fix_description="low conf", confidence=0.3)
        librarian.commit_fix(error_signature="timeout", fix_description="high conf", confidence=0.9)

        all_hits = librarian.search_synthetic_cache("request timeout exceeded")
        assert len(all_hits) == 2

        high_only = librarian.search_synthetic_cache("request timeout exceeded", min_confidence=0.5)
        assert len(high_only) == 1
        assert high_only[0]["fix_description"] == "high conf"

    def test_project_specific_ranking(self, librarian: Librarian):
        """Fixes from the queried project should rank higher."""
        librarian.commit_fix(error_signature="crash", fix_description="generic fix", project="other", confidence=0.9)
        librarian.commit_fix(error_signature="crash", fix_description="project fix", project="myapp", confidence=0.8)

        hits = librarian.search_synthetic_cache("application crash loop", project="myapp")
        assert len(hits) == 2
        # Project-specific fix should be ranked first despite lower confidence.
        assert hits[0]["fix_description"] == "project fix"

    def test_bump_cache_hit(self, librarian: Librarian):
        record = librarian.commit_fix(error_signature="x", fix_description="y", confidence=0.5)
        assert record["times_matched"] == 0

        librarian.bump_cache_hit(record["id"])
        librarian.bump_cache_hit(record["id"])

        hits = librarian.search_synthetic_cache("x")
        assert hits[0]["times_matched"] == 2

    def test_reader_search_cache(self, librarian: Librarian, reader: VaultReader):
        """VaultReader.search_cache() should find fixes committed by Librarian."""
        librarian.commit_fix(
            error_signature=r"connection refused.*5432",
            fix_description="PostgreSQL not running, restart the pod",
            confidence=0.95,
        )

        hits = reader.search_cache("FATAL: connection refused to port 5432")
        assert len(hits) == 1
        assert "PostgreSQL" in hits[0]["fix_description"]

    def test_empty_cache_returns_nothing(self, reader: VaultReader):
        assert reader.search_cache("any error") == []


