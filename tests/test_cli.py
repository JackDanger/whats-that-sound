"""Tests for the CLI module."""

import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from src.cli import main_cli


class TestCLI:
    """Test cases for CLI commands."""

    def test_cli_help(self):
        """Test CLI help command."""
        runner = CliRunner()
        result = runner.invoke(main_cli, ["--help"])
        assert result.exit_code == 0
        assert "Organize music from SOURCE_DIR into TARGET_DIR" in result.output

    def test_cli_short_help(self):
        runner = CliRunner()
        result = runner.invoke(main_cli, ["-h"])
        assert result.exit_code == 0
        assert "Organize music from SOURCE_DIR into TARGET_DIR" in result.output

    def test_organize_help(self):
        """Test organize command help."""
        runner = CliRunner()
        result = runner.invoke(main_cli, ["--help"])
        assert result.exit_code == 0
        assert "--source-dir" in result.output
        assert "--target-dir" in result.output
        assert "--model" in result.output
        assert "--inference-url" in result.output

    def test_no_models_command_anymore(self):
        # there is no models command; help should be only for main_cli
        runner = CliRunner()
        result = runner.invoke(main_cli, ["--help"])
        assert result.exit_code == 0

    @patch("src.cli.InferenceProvider")
    @patch("src.cli.MusicOrganizer")
    def test_organize_success_with_model(self, mock_organizer_class, mock_inf_class, tmp_path):
        mock_inf = Mock()
        mock_inf_class.return_value = mock_inf
        mock_org = Mock()
        mock_organizer_class.return_value = mock_org

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        runner = CliRunner()
        with patch.dict("os.environ", {"OPENAI_API_TOKEN": "tok"}, clear=False):
            result = runner.invoke(
                main_cli,
                [
                    "--source-dir", str(source_dir),
                    "--target-dir", str(target_dir),
                    "--model", "gpt-5",
                ],
            )

        assert result.exit_code == 0
        mock_org.organize.assert_called_once()

    @patch("src.cli.InferenceProvider")
    @patch("src.cli.MusicOrganizer")
    def test_organize_success_with_inference_url(self, mock_organizer_class, mock_inf_class, tmp_path):
        mock_org = Mock()
        mock_organizer_class.return_value = mock_org
        mock_inf = Mock()
        mock_inf_class.return_value = mock_inf

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        runner = CliRunner()
        result = runner.invoke(
            main_cli,
            [
                "--source-dir", str(source_dir),
                "--target-dir", str(target_dir),
                "--inference-url", "http://localhost:11434/v1",
            ],
        )

        assert result.exit_code == 0
        mock_org.organize.assert_called_once()

    def test_mutually_exclusive_args(self, tmp_path):
        runner = CliRunner()
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"
        result = runner.invoke(
            main_cli,
            [
                "--source-dir", str(source_dir),
                "--target-dir", str(target_dir),
                "--model", "gpt-5",
                "--inference-url", "http://localhost:11434/v1",
            ],
        )
        assert result.exit_code != 0
        assert "Provide exactly one" in result.output

    def test_organize_missing_arguments(self):
        """Test organize command with missing arguments."""
        runner = CliRunner()
        result = runner.invoke(main_cli, [])
        assert result.exit_code != 0

    @patch("src.cli.MusicOrganizer")
    def test_organize_success(
        self, mock_organizer_class, tmp_path
    ):
        """Test successful music organization."""
        mock_organizer = Mock()
        mock_organizer_class.return_value = mock_organizer

        # Create test directories
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        runner = CliRunner()
        with patch.dict("os.environ", {"OPENAI_API_TOKEN": "tok"}, clear=False):
            result = runner.invoke(
                main_cli,
                [
                    "--source-dir", str(source_dir),
                    "--target-dir", str(target_dir),
                    "--model", "gpt-5",
                ],
            )

        assert result.exit_code == 0
        assert target_dir.exists()
        mock_organizer.organize.assert_called_once()

    def test_missing_token_for_openai(self, tmp_path):
        runner = CliRunner()
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"
        result = runner.invoke(
            main_cli,
            [
                "--source-dir", str(source_dir),
                "--target-dir", str(target_dir),
                "--model", "gpt-5",
            ],
        )
        assert result.exit_code != 0
        assert "OPENAI_API_TOKEN" in result.output

    def test_organize_source_not_exists(self, tmp_path):
        """Test organize command with non-existent source directory."""
        runner = CliRunner()
        result = runner.invoke(
            main_cli,
            [
                "--source-dir", str(tmp_path / "nonexistent"),
                "--target-dir", str(tmp_path / "target"),
                "--model", "test-model",
            ],
        )

        assert result.exit_code != 0
