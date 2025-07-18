"""Tests for the music organizer module."""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

from src.organizer import MusicOrganizer


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    mock = Mock()
    mock.return_value = {
        "choices": [
            {
                "text": json.dumps(
                    {
                        "artist": "Test Artist",
                        "album": "Test Album",
                        "year": "2023",
                        "release_type": "Album",
                        "confidence": "high",
                        "reasoning": "Based on metadata",
                    }
                )
            }
        ]
    }
    return mock


@pytest.fixture
def mock_ui():
    """Create a mock UI."""
    mock = Mock()
    mock.get_user_feedback.return_value = {
        "action": "accept",
        "proposal": {
            "artist": "Test Artist",
            "album": "Test Album",
            "year": "2023",
            "release_type": "Album",
        },
    }
    return mock


@pytest.fixture
def mock_metadata_extractor():
    """Create a mock metadata extractor."""
    mock = Mock()
    mock.extract_folder_metadata.return_value = {
        "folder_name": "test_folder",
        "total_files": 10,
        "files": [
            {"filename": "track1.mp3", "artist": "Test Artist", "title": "Song 1"},
            {"filename": "track2.mp3", "artist": "Test Artist", "title": "Song 2"},
        ],
        "analysis": {
            "common_artist": "Test Artist",
            "common_album": "Test Album",
            "common_year": "2023",
            "likely_compilation": False,
            "track_number_pattern": "sequential",
        },
        "subdirectories": [],
    }
    return mock


class TestMusicOrganizer:
    """Test cases for MusicOrganizer class."""

    @patch("src.organizer.Llama")
    @patch("src.organizer.InteractiveUI")
    @patch("src.organizer.MetadataExtractor")
    def test_init_success(
        self, mock_metadata_class, mock_ui_class, mock_llama_class, tmp_path
    ):
        """Test successful initialization."""
        mock_llama_class.return_value = Mock()
        mock_ui_class.return_value = Mock()
        mock_metadata_class.return_value = Mock()

        model_path = tmp_path / "model.gguf"
        model_path.touch()
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target"

        organizer = MusicOrganizer(model_path, source_dir, target_dir)

        assert organizer.model_path == model_path
        assert organizer.source_dir == source_dir
        assert organizer.target_dir == target_dir
        mock_llama_class.assert_called_once()

    @patch("src.organizer.Llama")
    def test_init_llm_error(self, mock_llama_class, tmp_path):
        """Test initialization when LLM loading fails."""
        mock_llama_class.side_effect = Exception("Failed to load model")

        model_path = tmp_path / "model.gguf"
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"

        with pytest.raises(Exception, match="Failed to load model"):
            MusicOrganizer(model_path, source_dir, target_dir)

    def test_build_prompt(self, tmp_path, mock_llm, mock_ui, mock_metadata_extractor):
        """Test prompt building."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", tmp_path, tmp_path
                    )

                    metadata = (
                        mock_metadata_extractor.extract_folder_metadata.return_value
                    )
                    prompt = organizer._build_prompt(metadata)

                    assert "test_folder" in prompt
                    assert "Test Artist" in prompt
                    assert "Test Album" in prompt
                    assert "2023" in prompt
                    assert "sequential" in prompt

    def test_build_prompt_with_feedback(
        self, tmp_path, mock_llm, mock_ui, mock_metadata_extractor
    ):
        """Test prompt building with user feedback."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", tmp_path, tmp_path
                    )

                    metadata = (
                        mock_metadata_extractor.extract_folder_metadata.return_value
                    )
                    prompt = organizer._build_prompt(
                        metadata, "This is actually a live album"
                    )

                    assert "User Feedback: This is actually a live album" in prompt

    def test_parse_llm_response_valid_json(
        self, tmp_path, mock_llm, mock_ui, mock_metadata_extractor
    ):
        """Test parsing valid JSON response from LLM."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", tmp_path, tmp_path
                    )

                    response = """Here is my analysis:
                    ```json
                    {
                        "artist": "The Beatles",
                        "album": "Abbey Road",
                        "year": "1969",
                        "release_type": "Album",
                        "confidence": "high",
                        "reasoning": "Classic album"
                    }
                    ```"""

                    proposal = organizer._parse_llm_response(response)

                    assert proposal["artist"] == "The Beatles"
                    assert proposal["album"] == "Abbey Road"
                    assert proposal["year"] == "1969"
                    assert proposal["release_type"] == "Album"

    def test_parse_llm_response_invalid_json(
        self, tmp_path, mock_llm, mock_ui, mock_metadata_extractor
    ):
        """Test parsing invalid response from LLM."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", tmp_path, tmp_path
                    )

                    response = (
                        "I think the artist is The Beatles and the album is Abbey Road"
                    )

                    proposal = organizer._parse_llm_response(response)

                    # Should return default values
                    assert proposal["artist"] == "Unknown Artist"
                    assert proposal["album"] == "Unknown Album"
                    assert proposal["confidence"] == "low"

    def test_sanitize_filename(
        self, tmp_path, mock_llm, mock_ui, mock_metadata_extractor
    ):
        """Test filename sanitization."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", tmp_path, tmp_path
                    )

                    # Test invalid characters
                    assert organizer._sanitize_filename("Test/Album") == "Test_Album"
                    assert organizer._sanitize_filename("Test:Album") == "Test_Album"
                    assert organizer._sanitize_filename("Test<Album>") == "Test_Album_"

                    # Test length limit
                    long_name = "A" * 150
                    assert len(organizer._sanitize_filename(long_name)) == 120

    @patch("src.organizer.shutil.copy2")
    @patch("src.organizer.MetadataExtractor")
    def test_organize_folder(
        self, mock_metadata_class, mock_copy, tmp_path, mock_llm, mock_ui
    ):
        """Test organizing a folder."""
        # Set up MetadataExtractor mock with SUPPORTED_FORMATS
        mock_metadata_class.SUPPORTED_FORMATS = {
            ".mp3",
            ".flac",
            ".m4a",
            ".mp4",
            ".ogg",
            ".opus",
            ".wav",
        }

        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                source_dir = tmp_path / "source"
                source_dir.mkdir()
                target_dir = tmp_path / "target"
                target_dir.mkdir()

                # Create test music files
                test_folder = source_dir / "test_album"
                test_folder.mkdir()
                (test_folder / "track1.mp3").touch()
                (test_folder / "track2.mp3").touch()

                organizer = MusicOrganizer(
                    tmp_path / "model.gguf", source_dir, target_dir
                )

                proposal = {
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "year": "2023",
                    "release_type": "Album",
                }

                organizer._organize_folder(test_folder, proposal)

                # Check target directory was created
                expected_dir = target_dir / "Test Artist" / "Test Album (2023)"
                assert expected_dir.exists()

                # Check copy was called
                assert mock_copy.call_count == 2

    def test_organize_no_folders(
        self, tmp_path, mock_llm, mock_ui, mock_metadata_extractor
    ):
        """Test organize when no folders exist."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    source_dir = tmp_path / "source"
                    source_dir.mkdir()
                    target_dir = tmp_path / "target"

                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", source_dir, target_dir
                    )
                    organizer.organize()

                    # Should handle gracefully
                    mock_ui.display_completion_summary.assert_not_called()

    def test_organize_skip_folder(self, tmp_path, mock_llm, mock_metadata_extractor):
        """Test skipping a folder during organization."""
        mock_ui = Mock()
        mock_ui.get_user_feedback.return_value = {"action": "skip"}

        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    source_dir = tmp_path / "source"
                    source_dir.mkdir()
                    test_folder = source_dir / "test_album"
                    test_folder.mkdir()
                    target_dir = tmp_path / "target"

                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", source_dir, target_dir
                    )
                    organizer.organize()

                    # Check summary shows skipped
                    summary_call = mock_ui.display_completion_summary.call_args[0][0]
                    assert summary_call["skipped"] == 1
                    assert summary_call["successful"] == 0
