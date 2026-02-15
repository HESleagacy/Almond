"""
tests/cli/test_utils.py — Tests for CLI utilities.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from cli.utils import handle_errors, read_log_file, validate_env_vars


class TestReadLogFile:
    """Tests for read_log_file function."""

    def test_read_small_file(self, tmp_path):
        """Test reading a small file."""
        log_file = tmp_path / "test.log"
        content = "Error: Connection timeout\n"
        log_file.write_text(content)

        result = read_log_file(log_file)
        assert result == content

    def test_read_large_file_truncates(self, tmp_path):
        """Test that large files are truncated."""
        log_file = tmp_path / "large.log"
        # Create a 100k character file
        content = "x" * 100000
        log_file.write_text(content)

        result = read_log_file(log_file, max_chars=50000)
        # Should be truncated with separator
        assert len(result) > 50000  # Has separator text
        assert "File truncated" in result
        assert result.startswith("x" * 1000)  # First part preserved
        assert result.endswith("x" * 1000)  # Last part preserved

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        with pytest.raises(FileNotFoundError, match="Log file not found"):
            read_log_file(Path("/nonexistent/file.log"))

    def test_path_is_directory(self, tmp_path):
        """Test that RuntimeError is raised for directories."""
        with pytest.raises(RuntimeError, match="Path is not a file"):
            read_log_file(tmp_path)

    def test_utf8_with_errors(self, tmp_path):
        """Test that invalid UTF-8 is handled gracefully."""
        log_file = tmp_path / "invalid.log"
        # Write invalid UTF-8
        log_file.write_bytes(b"Valid text \xff\xfe Invalid UTF-8")

        result = read_log_file(log_file)
        # Should replace invalid chars
        assert "Valid text" in result


class TestValidateEnvVars:
    """Tests for validate_env_vars function."""

    def test_missing_api_key(self):
        """Test that RuntimeError is raised when API key is missing."""
        console = Console()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
                validate_env_vars(console)

    def test_missing_vault(self):
        """Test that RuntimeError is raised when vault doesn't exist."""
        console = Console()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            with pytest.raises(RuntimeError, match="Vault not found"):
                validate_env_vars(console)

    def test_valid_env_vars(self, tmp_path):
        """Test successful validation with all env vars set."""
        console = Console()
        vault_file = tmp_path / "history.txt"
        vault_file.write_text("Test vault")

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-key",
                "VAULT_PATH": str(vault_file),
                "CACHE_PATH": "./vault/ai_fixes.json",
            },
            clear=True,
        ):
            api_key, vault_path, cache_path = validate_env_vars(console)
            assert api_key == "test-key"
            assert vault_path == str(vault_file)
            assert cache_path == "./vault/ai_fixes.json"

    def test_defaults(self, tmp_path):
        """Test that default paths are used when not specified."""
        console = Console()
        vault_file = tmp_path / "history.txt"
        vault_file.write_text("Test vault")

        # Create default vault path
        default_vault = Path("./vault/history.txt")
        default_vault.parent.mkdir(exist_ok=True)
        default_vault.write_text("Default vault")

        try:
            with patch.dict(
                os.environ,
                {"ANTHROPIC_API_KEY": "test-key"},
                clear=True,
            ):
                api_key, vault_path, cache_path = validate_env_vars(console)
                assert api_key == "test-key"
                assert vault_path == "./vault/history.txt"
                assert cache_path == "./vault/ai_fixes.json"
        finally:
            # Cleanup
            if default_vault.exists():
                default_vault.unlink()


class TestHandleErrors:
    """Tests for handle_errors context manager."""

    def test_keyboard_interrupt(self):
        """Test that KeyboardInterrupt exits with code 130."""
        console = Console()
        with pytest.raises(SystemExit) as exc_info:
            with handle_errors(console):
                raise KeyboardInterrupt()
        assert exc_info.value.code == 130

    def test_file_not_found(self):
        """Test that FileNotFoundError exits with code 1."""
        console = Console()
        with pytest.raises(SystemExit) as exc_info:
            with handle_errors(console):
                raise FileNotFoundError("test.log")
        assert exc_info.value.code == 1

    def test_runtime_error(self):
        """Test that RuntimeError exits with code 1."""
        console = Console()
        with pytest.raises(SystemExit) as exc_info:
            with handle_errors(console):
                raise RuntimeError("Test error")
        assert exc_info.value.code == 1

    def test_generic_exception(self):
        """Test that generic exceptions exit with code 1."""
        console = Console()
        with pytest.raises(SystemExit) as exc_info:
            with handle_errors(console):
                raise ValueError("Test error")
        assert exc_info.value.code == 1

    def test_no_error(self):
        """Test that no error allows normal execution."""
        console = Console()
        executed = False
        with handle_errors(console):
            executed = True
        assert executed
