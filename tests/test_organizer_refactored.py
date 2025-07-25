"""Tests for the refactored MusicOrganizer orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.organizer import MusicOrganizer


class TestMusicOrganizerRefactored:
    """Test cases for the refactored MusicOrganizer orchestrator."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        return Mock()

    @pytest.fixture
    def complete_structure_analysis(self):
        """Create a complete structure analysis for mocking."""
        return {
            "folder_name": "test_folder",
            "total_music_files": 10,
            "direct_music_files": 10,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "test_folder\n├── track1.mp3\n└── track2.mp3",
        }

    @patch("src.organizer.Llama")
    def test_init_success(self, mock_llama_class, tmp_path):
        """Test successful initialization."""
        mock_llm = Mock()
        mock_llama_class.return_value = mock_llm

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
        )

        assert organizer.source_dir == tmp_path / "source"
        assert organizer.target_dir == tmp_path / "target"
        assert organizer.llm == mock_llm

        # Verify components were initialized
        assert hasattr(organizer, "directory_analyzer")
        assert hasattr(organizer, "structure_classifier")
        assert hasattr(organizer, "proposal_generator")
        assert hasattr(organizer, "file_organizer")
        assert hasattr(organizer, "progress_tracker")
        assert hasattr(organizer, "state_manager")
        assert hasattr(organizer, "ui")
        assert hasattr(organizer, "album_processor")
        assert hasattr(organizer, "collection_processor")

    @patch("src.organizer.Llama")
    def test_init_llm_error(self, mock_llama_class, tmp_path):
        """Test initialization with LLM error."""
        mock_llama_class.side_effect = Exception("LLM error")

        with pytest.raises(Exception, match="LLM error"):
            MusicOrganizer(
                tmp_path / "model.gguf", tmp_path / "source", tmp_path / "target"
            )

    @patch("src.organizer.Llama")
    def test_organize_no_folders(self, mock_llama_class, tmp_path):
        """Test organize when no folders exist."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Should complete without error when no folders exist
        organizer.organize()

    @patch("src.organizer.Llama")
    def test_organize_all_already_organized(self, mock_llama_class, tmp_path):
        """Test organize when all folders are already organized."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_folder = source_dir / "test_album"
        test_folder.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Mock state manager to say folder is already organized
        organizer.state_manager.filter_unorganized_folders = Mock(return_value=([], 1))

        organizer.organize()

    @patch("src.organizer.Llama")
    def test_organize_single_album_success(
        self, mock_llama_class, tmp_path, complete_structure_analysis
    ):
        """Test organizing a single album successfully."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_folder = source_dir / "test_album"
        test_folder.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Mock components
        organizer.state_manager.filter_unorganized_folders = Mock(
            return_value=([test_folder], 0)
        )
        organizer.directory_analyzer.analyze_directory_structure = Mock(
            return_value=complete_structure_analysis
        )
        organizer.ui.display_structure_analysis = Mock()  # Mock UI display
        organizer.ui.display_completion_summary = Mock()  # Mock UI display
        organizer.structure_classifier.classify_directory_structure = Mock(
            return_value="single_album"
        )
        organizer.album_processor.process_single_album = Mock(return_value=True)
        organizer.state_manager.load_tracker_data = Mock(
            return_value={
                "proposal": {
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "year": "2023",
                }
            }
        )

        organizer.organize()

        # Verify the workflow
        organizer.directory_analyzer.analyze_directory_structure.assert_called_once_with(
            test_folder
        )
        organizer.structure_classifier.classify_directory_structure.assert_called_once()
        organizer.album_processor.process_single_album.assert_called_once()

    @patch("src.organizer.Llama")
    def test_organize_multi_disc_album_success(
        self, mock_llama_class, tmp_path, complete_structure_analysis
    ):
        """Test organizing a multi-disc album successfully."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_folder = source_dir / "test_album"
        test_folder.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Mock components
        organizer.state_manager.filter_unorganized_folders = Mock(
            return_value=([test_folder], 0)
        )
        organizer.directory_analyzer.analyze_directory_structure = Mock(
            return_value=complete_structure_analysis
        )
        organizer.ui.display_structure_analysis = Mock()  # Mock UI display
        organizer.ui.display_completion_summary = Mock()  # Mock UI display
        organizer.structure_classifier.classify_directory_structure = Mock(
            return_value="multi_disc_album"
        )
        organizer.album_processor.process_multi_disc_album = Mock(return_value=True)
        organizer.state_manager.load_tracker_data = Mock(
            return_value={
                "proposal": {
                    "artist": "Test Artist",
                    "album": "Test Album",
                    "year": "2023",
                }
            }
        )

        organizer.organize()

        # Verify the workflow
        organizer.album_processor.process_multi_disc_album.assert_called_once()

    @patch("src.organizer.Llama")
    def test_organize_artist_collection_success(
        self, mock_llama_class, tmp_path, complete_structure_analysis
    ):
        """Test organizing an artist collection successfully."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_folder = source_dir / "artist_folder"
        test_folder.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Mock components
        organizer.state_manager.filter_unorganized_folders = Mock(
            return_value=([test_folder], 0)
        )
        organizer.directory_analyzer.analyze_directory_structure = Mock(
            return_value=complete_structure_analysis
        )
        organizer.ui.display_structure_analysis = Mock()  # Mock UI display
        organizer.ui.display_completion_summary = Mock()  # Mock UI display
        organizer.structure_classifier.classify_directory_structure = Mock(
            return_value="artist_collection"
        )
        organizer.collection_processor.process_artist_collection = Mock(
            return_value=True
        )
        organizer.state_manager.load_tracker_data = Mock(
            return_value={
                "albums": [
                    {"artist": "Test Artist", "album": "Album 1", "year": "2023"}
                ]
            }
        )

        organizer.organize()

        # Verify the workflow
        organizer.collection_processor.process_artist_collection.assert_called_once()

    @patch("src.organizer.Llama")
    def test_organize_no_music_files(self, mock_llama_class, tmp_path):
        """Test organizing folder with no music files."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_folder = source_dir / "empty_folder"
        test_folder.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Mock components
        organizer.state_manager.filter_unorganized_folders = Mock(
            return_value=([test_folder], 0)
        )
        organizer.directory_analyzer.analyze_directory_structure = Mock(
            return_value={
                "total_music_files": 0,
                "folder_name": "empty_folder",
                "direct_music_files": 0,
                "subdirectories": [],
                "max_depth": 0,
                "directory_tree": "empty_folder",
            }
        )
        # Mock the structure classifier as a Mock object so it has assert methods
        organizer.structure_classifier.classify_directory_structure = Mock()

        organizer.organize()

        # Should skip folder with no music files - classifier should not be called
        organizer.structure_classifier.classify_directory_structure.assert_not_called()

    @patch("src.organizer.Llama")
    def test_organize_unknown_structure_type(
        self, mock_llama_class, tmp_path, complete_structure_analysis
    ):
        """Test organizing with unknown structure type."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_folder = source_dir / "test_folder"
        test_folder.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Mock components
        organizer.state_manager.filter_unorganized_folders = Mock(
            return_value=([test_folder], 0)
        )
        organizer.directory_analyzer.analyze_directory_structure = Mock(
            return_value=complete_structure_analysis
        )
        organizer.ui.display_structure_analysis = Mock()  # Mock UI display
        organizer.ui.display_completion_summary = Mock()  # Mock UI display
        organizer.structure_classifier.classify_directory_structure = Mock(
            return_value="unknown_type"
        )

        organizer.organize()

        # Should handle unknown structure type gracefully

    @patch("src.organizer.Llama")
    def test_organize_processing_error(self, mock_llama_class, tmp_path):
        """Test organize with processing error."""
        mock_llama_class.return_value = Mock()

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_folder = source_dir / "test_folder"
        test_folder.mkdir()

        organizer = MusicOrganizer(
            tmp_path / "model.gguf", source_dir, tmp_path / "target"
        )

        # Mock components to raise error
        organizer.state_manager.filter_unorganized_folders = Mock(
            return_value=([test_folder], 0)
        )
        organizer.directory_analyzer.analyze_directory_structure = Mock(
            side_effect=Exception("Processing error")
        )

        organizer.organize()

        # Should handle processing errors gracefully
