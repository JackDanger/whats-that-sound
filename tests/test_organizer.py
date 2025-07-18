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
        "folder_name": "test_album",
        "total_files": 2,
        "files": [
            {
                "filename": "track1.mp3",
                "artist": "Test Artist",
                "title": "Track 1",
                "album": "Test Album",
                "year": "2023",
            },
            {
                "filename": "track2.mp3",
                "artist": "Test Artist",
                "title": "Track 2",
                "album": "Test Album",
                "year": "2023",
            },
        ],
        "analysis": {
            "common_artist": "Test Artist",
            "common_album": "Test Album",
            "common_year": "2023",
            "likely_compilation": False,
            "track_number_pattern": "consistent",
        },
    }
    return mock


class TestMusicOrganizer:
    """Test cases for MusicOrganizer class."""

    @patch("src.organizer.Llama")
    def test_init_success(self, mock_llama_class, tmp_path):
        """Test successful initialization."""
        mock_llama = Mock()
        mock_llama_class.return_value = mock_llama

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
        )

        assert organizer.model_path == tmp_path / "model.gguf"
        assert organizer.source_dir == tmp_path / "source"
        assert organizer.target_dir == tmp_path / "target"
        assert organizer.llm == mock_llama

    @patch("src.organizer.Llama")
    def test_init_llm_error(self, mock_llama_class, tmp_path):
        """Test initialization with LLM error."""
        mock_llama_class.side_effect = Exception("LLM error")

        with pytest.raises(Exception, match="LLM error"):
            MusicOrganizer(
                tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
            )

    def test_build_prompt(self, tmp_path, mock_llm):
        """Test prompt building."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            organizer = MusicOrganizer(
                tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
            )

            metadata = {
                "folder_name": "Test Album",
                "total_files": 2,
                "files": [
                    {"filename": "track1.mp3", "artist": "Artist", "title": "Track 1"}
                ],
                "analysis": {
                    "common_artist": "Test Artist",
                    "common_album": "Test Album",
                    "common_year": "2023",
                    "likely_compilation": False,
                    "track_number_pattern": "consistent",
                },
            }

            prompt = organizer._build_prompt(metadata)

            assert "Test Album" in prompt
            assert "Test Artist" in prompt
            assert "2023" in prompt
            assert "track1.mp3" in prompt

    def test_build_prompt_with_feedback(self, tmp_path, mock_llm):
        """Test prompt building with user feedback."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            organizer = MusicOrganizer(
                tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
            )

            metadata = {
                "folder_name": "Test Album",
                "total_files": 2,
                "files": [],
                "analysis": {},
            }

            prompt = organizer._build_prompt(metadata, "This is feedback")

            assert "This is feedback" in prompt
            assert "User Feedback:" in prompt

    def test_parse_llm_response_valid_json(self, tmp_path, mock_llm):
        """Test parsing valid JSON response."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            organizer = MusicOrganizer(
                tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
            )

            valid_response = json.dumps(
                {
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "year": "2023",
                    "release_type": "Album",
                }
            )

            proposal = organizer._parse_llm_response(valid_response)

            assert proposal["artist"] == "Test Artist"
            assert proposal["album"] == "Test Album"
            assert proposal["year"] == "2023"
            assert proposal["release_type"] == "Album"

    def test_parse_llm_response_invalid_json(self, tmp_path, mock_llm):
        """Test parsing invalid JSON response."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            organizer = MusicOrganizer(
                tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
            )

            invalid_response = "artist: Test Artist\nalbum: Test Album\nyear: 2023"

            proposal = organizer._parse_llm_response(invalid_response)

            assert proposal["artist"] == "Test Artist"
            assert proposal["album"] == "Test Album"
            assert proposal["year"] == "2023"

    def test_sanitize_filename(self, tmp_path, mock_llm):
        """Test filename sanitization."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            organizer = MusicOrganizer(
                tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
            )

            # Test invalid characters
            result = organizer._sanitize_filename('Test<>:"/\\|?*Name')
            assert result == "Test_________Name"

            # Test length limit
            long_name = "a" * 150
            result = organizer._sanitize_filename(long_name)
            assert len(result) <= 120

    def test_organize_folder(self, tmp_path, mock_llm):
        """Test folder organization."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.shutil.copy2") as mock_copy:
                with patch("src.organizer.MetadataExtractor") as MockExtractor:
                    MockExtractor.SUPPORTED_FORMATS = [".mp3", ".flac"]

                    source_dir = tmp_path / "source"
                    test_folder = source_dir / "test_album"
                    test_folder.mkdir(parents=True)

                    # Create test files
                    (test_folder / "track1.mp3").touch()
                    (test_folder / "track2.flac").touch()

                    target_dir = tmp_path / "target"
                    target_dir.mkdir()

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

    def test_organize_skip_already_organized(
        self, tmp_path, mock_llm, mock_metadata_extractor
    ):
        """Test skipping folders that already have .whats-that-sound files."""
        mock_ui = Mock()

        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    source_dir = tmp_path / "source"
                    source_dir.mkdir()

                    # Create two folders
                    test_folder1 = source_dir / "test_album1"
                    test_folder1.mkdir()
                    test_folder2 = source_dir / "test_album2"
                    test_folder2.mkdir()

                    # Add tracker file to first folder (already organized)
                    tracker_file = test_folder1 / ".whats-that-sound"
                    tracker_data = {
                        "proposal": {
                            "artist": "Old Artist",
                            "album": "Old Album",
                            "year": "2020",
                            "release_type": "Album",
                        },
                        "folder_name": "test_album1",
                        "organized_timestamp": "2023-01-01",
                    }
                    with open(tracker_file, "w") as f:
                        json.dump(tracker_data, f)

                    target_dir = tmp_path / "target"

                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", source_dir, target_dir
                    )
                    organizer.organize()

                    # Should only process test_folder2, not test_folder1
                    # Verify metadata extractor was only called once (for test_folder2)
                    mock_metadata_extractor.extract_folder_metadata.assert_called_once()

    def test_organize_all_already_organized(
        self, tmp_path, mock_llm, mock_metadata_extractor
    ):
        """Test when all folders are already organized."""
        mock_ui = Mock()

        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    source_dir = tmp_path / "source"
                    source_dir.mkdir()

                    # Create folder with tracker file
                    test_folder = source_dir / "test_album"
                    test_folder.mkdir()
                    tracker_file = test_folder / ".whats-that-sound"
                    tracker_data = {
                        "proposal": {
                            "artist": "Artist",
                            "album": "Album",
                            "year": "2020",
                            "release_type": "Album",
                        },
                        "folder_name": "test_album",
                        "organized_timestamp": "2023-01-01",
                    }
                    with open(tracker_file, "w") as f:
                        json.dump(tracker_data, f)

                    target_dir = tmp_path / "target"

                    organizer = MusicOrganizer(
                        tmp_path / "model.gguf", source_dir, target_dir
                    )
                    organizer.organize()

                    # Should not call metadata extractor or UI methods for processing
                    mock_metadata_extractor.extract_folder_metadata.assert_not_called()
                    mock_ui.display_folder_info.assert_not_called()

    def test_save_proposal_tracker(self, tmp_path, mock_llm):
        """Test saving proposal tracker file."""
        with patch("src.organizer.Llama", return_value=mock_llm):
            source_dir = tmp_path / "source"
            test_folder = source_dir / "test_album"
            test_folder.mkdir(parents=True)

            target_dir = tmp_path / "target"

            organizer = MusicOrganizer(tmp_path / "model.gguf", source_dir, target_dir)

            proposal = {
                "artist": "Test Artist",
                "album": "Test Album",
                "year": "2023",
                "release_type": "Album",
                "confidence": "high",
                "reasoning": "Test reasoning",
            }

            organizer._save_proposal_tracker(test_folder, proposal)

            # Check that tracker file was created
            tracker_file = test_folder / ".whats-that-sound"
            assert tracker_file.exists()

            # Check file contents
            with open(tracker_file, "r") as f:
                tracker_data = json.load(f)

            assert tracker_data["proposal"] == proposal
            assert tracker_data["folder_name"] == "test_album"
            assert "organized_timestamp" in tracker_data

    def test_organize_creates_tracker_file(
        self, tmp_path, mock_llm, mock_metadata_extractor
    ):
        """Test that organizing a folder creates the tracker file."""
        mock_ui = Mock()
        mock_ui.get_user_feedback.return_value = {
            "action": "accept",
            "proposal": {
                "artist": "Test Artist",
                "album": "Test Album",
                "year": "2023",
                "release_type": "Album",
            },
        }

        with patch("src.organizer.Llama", return_value=mock_llm):
            with patch("src.organizer.InteractiveUI", return_value=mock_ui):
                with patch(
                    "src.organizer.MetadataExtractor",
                    return_value=mock_metadata_extractor,
                ):
                    with patch("src.organizer.shutil.copy2"):
                        with patch("src.organizer.MetadataExtractor") as MockExtractor:
                            MockExtractor.SUPPORTED_FORMATS = [".mp3"]

                            source_dir = tmp_path / "source"
                            source_dir.mkdir()
                            test_folder = source_dir / "test_album"
                            test_folder.mkdir()
                            (test_folder / "track.mp3").touch()
                            target_dir = tmp_path / "target"

                            organizer = MusicOrganizer(
                                tmp_path / "model.gguf", source_dir, target_dir
                            )
                            organizer.organize()

                            # Check that tracker file was created
                            tracker_file = test_folder / ".whats-that-sound"
                            assert tracker_file.exists()

                            # Check file contents
                            with open(tracker_file, "r") as f:
                                tracker_data = json.load(f)

                            assert tracker_data["proposal"]["artist"] == "Test Artist"
                            assert tracker_data["folder_name"] == "test_album"
