"""
tests/cli/test_main.py — Integration tests for CLI commands.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


class TestDebugCommand:
    """Tests for the debug command."""

    @patch("cli.main.RLMEngine")
    @patch("cli.main.validate_env_vars")
    def test_debug_basic(self, mock_validate, mock_engine, tmp_path):
        """Test basic debug command execution."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Connection timeout")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.debug.return_value = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {
                "confidence": 0.8,
                "fix_description": "Test fix",
                "fix_code": "test code",
            },
        }

        # Execute
        result = runner.invoke(app, ["debug", "--logs", str(log_file)])

        # Verify
        assert result.exit_code == 0

    @patch("cli.main.RLMEngine")
    @patch("cli.main.validate_env_vars")
    def test_debug_json_format(self, mock_validate, mock_engine, tmp_path):
        """Test debug with JSON output format."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Test")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.debug.return_value = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {"description": "Test"},
        }

        # Execute
        result = runner.invoke(app, ["debug", "--logs", str(log_file), "--format", "json"])

        # Verify
        assert result.exit_code == 0

    @patch("cli.main.RLMEngine")
    @patch("cli.main.validate_env_vars")
    def test_debug_minimal_format(self, mock_validate, mock_engine, tmp_path):
        """Test debug with minimal output format."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Test")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.debug.return_value = {
            "status": "RESOLVED_BY_CACHE",
            "fix": {"fix_description": "Test fix"},
        }

        # Execute
        result = runner.invoke(
            app, ["debug", "--logs", str(log_file), "--format", "minimal"]
        )

        # Verify
        assert result.exit_code == 0

    @patch("cli.main.RLMEngine")
    @patch("cli.main.validate_env_vars")
    def test_debug_verbose(self, mock_validate, mock_engine, tmp_path):
        """Test debug with verbose flag."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Test")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.debug.return_value = {
            "status": "RESOLVED_BY_SYNTHESIS",
            "report": {"solution": "Test"},
            "_trace": [{"depth": 0, "action": "EXECUTE_CODE", "delta": "Test"}],
        }

        # Execute
        result = runner.invoke(app, ["debug", "--logs", str(log_file), "--verbose"])

        # Verify
        assert result.exit_code == 0

    def test_debug_file_not_found(self):
        """Test debug with non-existent log file."""
        result = runner.invoke(app, ["debug", "--logs", "/nonexistent/file.log"])

        # Typer should catch this before our code
        assert result.exit_code != 0

    @patch("cli.main.validate_env_vars")
    def test_debug_invalid_format(self, mock_validate, tmp_path):
        """Test debug with invalid format option."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Test")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        # Execute
        result = runner.invoke(
            app, ["debug", "--logs", str(log_file), "--format", "invalid"]
        )

        # Verify - should exit with error
        assert result.exit_code == 1

    @patch("cli.main.RLMEngine")
    @patch("cli.main.validate_env_vars")
    def test_debug_vault_result(self, mock_validate, mock_engine, tmp_path):
        """Test debug with Tier 1 (vault) result."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Network timeout")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.debug.return_value = {
            "status": "RESOLVED_BY_VAULT",
            "report": {
                "root_cause": "Network issue",
                "solution": "kubectl restart",
            },
        }

        # Execute
        result = runner.invoke(app, ["debug", "--logs", str(log_file)])

        # Verify
        assert result.exit_code == 0

    @patch("cli.main.RLMEngine")
    @patch("cli.main.validate_env_vars")
    def test_debug_synthesis_result(self, mock_validate, mock_engine, tmp_path):
        """Test debug with Tier 3 (synthesis) result."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Memory leak")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.debug.return_value = {
            "status": "RESOLVED_BY_SYNTHESIS",
            "report": {
                "root_cause": "Memory leak detected",
                "solution": "Increase memory limit",
            },
            "_trace": [
                {"depth": 0, "action": "EXECUTE_CODE", "delta": "Analyzing..."},
            ],
        }

        # Execute
        result = runner.invoke(app, ["debug", "--logs", str(log_file)])

        # Verify
        assert result.exit_code == 0

    @patch("cli.main.RLMEngine")
    @patch("cli.main.validate_env_vars")
    def test_debug_error_status(self, mock_validate, mock_engine, tmp_path):
        """Test debug with error status from engine."""
        # Setup
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Complex issue")

        mock_validate.return_value = ("api-key", "vault-path", "cache-path")

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.debug.return_value = {
            "status": "MAX_DEPTH",
            "msg": "Recursion limit reached",
        }

        # Execute
        result = runner.invoke(app, ["debug", "--logs", str(log_file)])

        # Verify - should still exit cleanly (engine handled the error)
        assert result.exit_code == 0


class TestVersionCommand:
    """Tests for the version command."""

    def test_version(self):
        """Test version command output."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "ALMOND RLM" in result.output
        assert "v0.1.0" in result.output

    def test_version_shows_components(self):
        """Test that version shows core components."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Recursive Language Model" in result.output
        assert "Three-tier" in result.output


class TestMainCallback:
    """Tests for the main callback."""

    def test_help(self):
        """Test that help command works."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "ALMOND" in result.output
        assert "debug" in result.output
        assert "version" in result.output

    def test_no_command(self):
        """Test running with no command shows help."""
        result = runner.invoke(app, [])

        # Typer returns exit code 2 when no command is provided (standard behavior)
        assert result.exit_code in [0, 2]


class TestEnvironmentValidation:
    """Tests for environment variable validation."""

    @patch("cli.main.validate_env_vars")
    def test_missing_api_key(self, mock_validate, tmp_path):
        """Test that missing API key is caught."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Test")

        mock_validate.side_effect = RuntimeError("ANTHROPIC_API_KEY not set")

        result = runner.invoke(app, ["debug", "--logs", str(log_file)])

        # Should exit with error
        assert result.exit_code == 1

    @patch("cli.main.validate_env_vars")
    def test_missing_vault(self, mock_validate, tmp_path):
        """Test that missing vault is caught."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Error: Test")

        mock_validate.side_effect = RuntimeError("Vault not found")

        result = runner.invoke(app, ["debug", "--logs", str(log_file)])

        # Should exit with error
        assert result.exit_code == 1
