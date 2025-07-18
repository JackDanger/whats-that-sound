"""Tests for the UI module."""

import pytest
from unittest.mock import Mock, patch
from rich.console import Console

from src.ui import InteractiveUI


class TestInteractiveUI:
    """Test cases for InteractiveUI class."""

    @pytest.fixture
    def ui(self):
        """Create a UI instance for testing."""
        return InteractiveUI()

    @patch("src.ui.console.print")
    def test_display_folder_info(self, mock_print, ui):
        """Test displaying folder information."""
        metadata = {
            "folder_name": "Test Album",
            "total_files": 12,
            "subdirectories": ["CD1", "CD2"],
            "analysis": {
                "common_artist": "Test Artist",
                "common_album": "Test Album",
                "common_year": "2023",
                "track_number_pattern": "sequential",
                "likely_compilation": False,
            },
        }

        ui.display_folder_info(metadata)

        # Should call print with a table
        assert mock_print.called

    @patch("src.ui.console.print")
    def test_display_structure_analysis_single_album(self, mock_print, ui):
        """Test displaying structure analysis for single album."""
        structure = {
            "folder_name": "Single Album",
            "total_music_files": 12,
            "direct_music_files": 12,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Single Album\n├── track1.mp3\n└── track2.mp3",
        }

        ui.display_structure_analysis(structure)

        # Should call print multiple times (table + tree panel)
        assert mock_print.call_count >= 2

    @patch("src.ui.console.print")
    def test_display_structure_analysis_multi_disc(self, mock_print, ui):
        """Test displaying structure analysis for multi-disc album."""
        structure = {
            "folder_name": "Multi-Disc Album",
            "total_music_files": 24,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "CD1", "music_files": 12, "subdirectories": []},
                {"name": "CD2", "music_files": 12, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Multi-Disc Album\n├── CD1/\n│   ├── track1.mp3\n└── CD2/\n    └── track1.mp3",
        }

        ui.display_structure_analysis(structure)

        # Should call print multiple times (main table + subdir table + tree)
        assert mock_print.call_count >= 3

    @patch("src.ui.console.print")
    def test_display_structure_analysis_artist_collection(self, mock_print, ui):
        """Test displaying structure analysis for artist collection."""
        structure = {
            "folder_name": "Artist Name",
            "total_music_files": 50,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "First Album", "music_files": 12, "subdirectories": []},
                {"name": "Second Album", "music_files": 15, "subdirectories": []},
                {"name": "Third Album", "music_files": 23, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Artist Name\n├── First Album/\n├── Second Album/\n└── Third Album/",
        }

        ui.display_structure_analysis(structure)

        # Should call print multiple times (main table + subdir table + tree)
        assert mock_print.call_count >= 3

    @patch("src.ui.console.print")
    def test_display_structure_analysis_large_tree_truncation(self, mock_print, ui):
        """Test that large directory trees are handled without error."""
        # Create a long directory tree (more than 20 lines)
        tree_lines = []
        for i in range(25):
            tree_lines.append(f"├── file{i}.mp3")
        long_tree = "\n".join(tree_lines)

        structure = {
            "folder_name": "Large Collection",
            "total_music_files": 25,
            "direct_music_files": 25,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": long_tree,
        }

        # Should complete without error
        ui.display_structure_analysis(structure)

        # Should have called print (table and panel)
        assert mock_print.call_count >= 2

    @patch("src.ui.console.print")
    def test_display_structure_analysis_many_subdirectories(self, mock_print, ui):
        """Test displaying structure with many subdirectories."""
        subdirs = []
        for i in range(15):  # More than 10 to test truncation
            subdirs.append(
                {"name": f"Album {i}", "music_files": 10 + i, "subdirectories": []}
            )

        structure = {
            "folder_name": "Prolific Artist",
            "total_music_files": 200,
            "direct_music_files": 0,
            "subdirectories": subdirs,
            "max_depth": 1,
            "directory_tree": "Prolific Artist\n├── Album 0/\n├── Album 1/\n... etc",
        }

        ui.display_structure_analysis(structure)

        # Should show main table, subdirectory table (with truncation), and tree
        assert mock_print.call_count >= 3

    @patch("src.ui.console.print")
    def test_display_file_samples(self, mock_print, ui):
        """Test displaying file samples."""
        files = [
            {
                "filename": "track1.mp3",
                "artist": "Test Artist",
                "title": "Track 1",
                "relative_path": "track1.mp3",
            },
            {
                "filename": "track2.mp3",
                "artist": "Test Artist",
                "title": "Track 2",
                "relative_path": "track2.mp3",
            },
        ]

        ui.display_file_samples(files)

        # Should print sample files header and file info
        assert mock_print.call_count >= 3

    @patch("src.ui.console.print")
    def test_display_llm_proposal(self, mock_print, ui):
        """Test displaying LLM proposal."""
        proposal = {
            "artist": "Test Artist",
            "album": "Test Album",
            "year": "2023",
            "release_type": "Album",
            "confidence": "high",
            "reasoning": "Based on metadata analysis",
        }

        ui.display_llm_proposal(proposal)

        # Should print panel and additional info
        assert mock_print.call_count >= 3

    @patch("builtins.input", return_value="1")
    @patch("src.ui.console.print")
    def test_get_user_feedback_accept(self, mock_print, mock_input, ui):
        """Test user feedback with accept choice."""
        proposal = {
            "artist": "Test Artist",
            "album": "Test Album",
            "year": "2023",
            "release_type": "Album",
        }

        with patch("src.ui.Prompt.ask", return_value="1"):
            feedback = ui.get_user_feedback(proposal)

        assert feedback["action"] == "accept"
        assert feedback["proposal"] == proposal

    @patch("builtins.input", return_value="4")
    @patch("src.ui.console.print")
    def test_get_user_feedback_skip(self, mock_print, mock_input, ui):
        """Test user feedback with skip choice."""
        proposal = {"artist": "Test Artist"}

        with patch("src.ui.Prompt.ask", return_value="4"):
            feedback = ui.get_user_feedback(proposal)

        assert feedback["action"] == "skip"

    @patch("src.ui.console.print")
    def test_display_progress(self, mock_print, ui):
        """Test progress display."""
        ui.display_progress(5, 10, "Current Folder")

        # Should print progress panel
        assert mock_print.called

    @patch("src.ui.console.print")
    def test_display_completion_summary(self, mock_print, ui):
        """Test completion summary display."""
        summary = {
            "total_processed": 10,
            "successful": 8,
            "skipped": 1,
            "errors": 1,
            "organized_albums": [
                {"artist": "Artist 1", "album": "Album 1", "year": "2023"},
                {"artist": "Artist 2", "album": "Album 2", "year": "2024"},
            ],
        }

        ui.display_completion_summary(summary)

        # Should print table and album list
        assert mock_print.call_count >= 3

    def test_confirm_action_true(self, ui):
        """Test confirmation dialog returning True."""
        with patch("src.ui.Confirm.ask", return_value=True):
            result = ui.confirm_action("Test message")
            assert result is True

    def test_confirm_action_false(self, ui):
        """Test confirmation dialog returning False."""
        with patch("src.ui.Confirm.ask", return_value=False):
            result = ui.confirm_action("Test message")
            assert result is False
