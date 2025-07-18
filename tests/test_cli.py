"""Tests for the CLI module."""

import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from src.cli import cli, organize, models


class TestCLI:
    """Test cases for CLI commands."""

    def test_cli_help(self):
        """Test CLI help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Organize music collections using local LLMs" in result.output

    def test_organize_help(self):
        """Test organize command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["organize", "--help"])
        assert result.exit_code == 0
        assert "SOURCE_DIR" in result.output
        assert "TARGET_DIR" in result.output
        assert "--model" in result.output

    def test_models_help(self):
        """Test models command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "--help"])
        assert result.exit_code == 0
        assert "--download" in result.output

    @patch("src.cli.ModelManager")
    def test_models_list_empty(self, mock_model_manager_class):
        """Test listing models when none are downloaded."""
        mock_manager = Mock()
        mock_manager.list_models.return_value = []
        mock_model_manager_class.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["models"])

        assert result.exit_code == 0
        assert "No models downloaded yet" in result.output

    @patch("src.cli.ModelManager")
    def test_models_list_with_models(self, mock_model_manager_class):
        """Test listing models when some are downloaded."""
        mock_manager = Mock()
        mock_manager.list_models.return_value = ["model1.gguf", "model2.gguf"]
        mock_model_manager_class.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["models"])

        assert result.exit_code == 0
        assert "Downloaded models:" in result.output
        assert "model1.gguf" in result.output
        assert "model2.gguf" in result.output

    @patch("src.cli.ModelManager")
    def test_models_download_success(self, mock_model_manager_class):
        """Test downloading a model successfully."""
        mock_manager = Mock()
        mock_manager.download_model.return_value = Path("/path/to/model.gguf")
        mock_model_manager_class.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["models", "--download", "test-model"])

        assert result.exit_code == 0
        assert "Downloading model: test-model" in result.output
        assert "Model downloaded to:" in result.output

    @patch("src.cli.ModelManager")
    def test_models_download_error(self, mock_model_manager_class):
        """Test model download error."""
        mock_manager = Mock()
        mock_manager.download_model.side_effect = Exception("Download failed")
        mock_model_manager_class.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(cli, ["models", "--download", "test-model"])

        assert result.exit_code != 0
        assert "Error downloading model" in result.output

    def test_organize_missing_arguments(self):
        """Test organize command with missing arguments."""
        runner = CliRunner()
        result = runner.invoke(cli, ["organize"])
        assert result.exit_code != 0

    @patch("src.cli.MusicOrganizer")
    @patch("src.cli.ModelManager")
    def test_organize_success(
        self, mock_model_manager_class, mock_organizer_class, tmp_path
    ):
        """Test successful music organization."""
        # Setup mocks
        mock_manager = Mock()
        mock_manager.ensure_model.return_value = Path("/path/to/model.gguf")
        mock_model_manager_class.return_value = mock_manager

        mock_organizer = Mock()
        mock_organizer_class.return_value = mock_organizer

        # Create test directories
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        runner = CliRunner()
        result = runner.invoke(
            cli, ["organize", str(source_dir), str(target_dir), "--model", "test-model"]
        )

        assert result.exit_code == 0
        assert target_dir.exists()
        mock_manager.ensure_model.assert_called_once_with("test-model")
        mock_organizer.organize.assert_called_once()

    @patch("src.cli.ModelManager")
    def test_organize_model_error(self, mock_model_manager_class, tmp_path):
        """Test organize command when model loading fails."""
        mock_manager = Mock()
        mock_manager.ensure_model.side_effect = Exception("Model not found")
        mock_model_manager_class.return_value = mock_manager

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        runner = CliRunner()
        result = runner.invoke(
            cli, ["organize", str(source_dir), str(target_dir), "--model", "test-model"]
        )

        assert result.exit_code != 0
        assert "Error:" in result.output

    def test_organize_source_not_exists(self, tmp_path):
        """Test organize command with non-existent source directory."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "organize",
                str(tmp_path / "nonexistent"),
                str(tmp_path / "target"),
                "--model",
                "test-model",
            ],
        )

        assert result.exit_code != 0
