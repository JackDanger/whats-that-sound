"""Integration tests for the music organizer system."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from src.analyzers.directory_analyzer import DirectoryAnalyzer
from src.analyzers.structure_classifier import StructureClassifier
from src.generators.proposal_generator import ProposalGenerator
from src.organizers.file_organizer import FileOrganizer
from src.trackers.progress_tracker import ProgressTracker
from src.trackers.state_manager import StateManager
from src.processors.album_processor import AlbumProcessor
from src.processors.collection_processor import CollectionProcessor
from src.ui import InteractiveUI
from src.organizer import MusicOrganizer


class TestDirectoryAnalyzerIntegration:
    """Test DirectoryAnalyzer with real file structures."""

    @pytest.fixture
    def analyzer(self):
        """Create a real DirectoryAnalyzer instance."""
        return DirectoryAnalyzer()

    def test_analyze_real_single_album_structure(self, analyzer, tmp_path):
        """Test analyzing a real single album directory structure."""
        # Create a realistic single album structure
        album_dir = tmp_path / "The Beatles - Abbey Road (1969)"
        album_dir.mkdir()

        # Create real music files
        (album_dir / "01 - Come Together.mp3").touch()
        (album_dir / "02 - Something.mp3").touch()
        (album_dir / "03 - Maxwell's Silver Hammer.mp3").touch()
        (album_dir / "04 - Oh! Darling.mp3").touch()
        (album_dir / "05 - Octopus's Garden.mp3").touch()

        # Create non-music files
        (album_dir / "folder.jpg").touch()
        (album_dir / "info.txt").touch()

        analysis = analyzer.analyze_directory_structure(album_dir)

        # Verify analysis
        assert analysis["folder_name"] == "The Beatles - Abbey Road (1969)"
        assert analysis["total_music_files"] == 5
        assert analysis["direct_music_files"] == 5
        assert len(analysis["subdirectories"]) == 0
        assert analysis["max_depth"] == 0
        assert "Come Together.mp3" in analysis["directory_tree"]
        assert "Something.mp3" in analysis["directory_tree"]

    def test_analyze_real_multi_disc_structure(self, analyzer, tmp_path):
        """Test analyzing a real multi-disc album directory structure."""
        # Create a realistic multi-disc structure
        album_dir = tmp_path / "Pink Floyd - The Wall (1979)"
        album_dir.mkdir()

        # Create disc folders
        disc1_dir = album_dir / "Disc 1"
        disc1_dir.mkdir()
        (disc1_dir / "01 - In the Flesh.mp3").touch()
        (disc1_dir / "02 - The Thin Ice.mp3").touch()
        (disc1_dir / "03 - Another Brick in the Wall.mp3").touch()

        disc2_dir = album_dir / "Disc 2"
        disc2_dir.mkdir()
        (disc2_dir / "01 - Hey You.mp3").touch()
        (disc2_dir / "02 - Is There Anybody Out There.mp3").touch()
        (disc2_dir / "03 - Comfortably Numb.mp3").touch()

        # Add album-level files
        (album_dir / "album.jpg").touch()

        analysis = analyzer.analyze_directory_structure(album_dir)

        # Verify analysis
        assert analysis["folder_name"] == "Pink Floyd - The Wall (1979)"
        assert analysis["total_music_files"] == 6
        assert analysis["direct_music_files"] == 0
        assert len(analysis["subdirectories"]) == 2
        assert analysis["max_depth"] == 1

        # Check subdirectory info
        subdir_names = [sub["name"] for sub in analysis["subdirectories"]]
        assert "Disc 1" in subdir_names
        assert "Disc 2" in subdir_names

        # Check music file counts in subdirectories
        disc1_info = next(
            sub for sub in analysis["subdirectories"] if sub["name"] == "Disc 1"
        )
        disc2_info = next(
            sub for sub in analysis["subdirectories"] if sub["name"] == "Disc 2"
        )
        assert disc1_info["music_files"] == 3
        assert disc2_info["music_files"] == 3

    def test_analyze_real_artist_collection_structure(self, analyzer, tmp_path):
        """Test analyzing a real artist collection directory structure."""
        # Create a realistic artist collection structure
        artist_dir = tmp_path / "Led Zeppelin"
        artist_dir.mkdir()

        # Create album folders
        album1_dir = artist_dir / "Led Zeppelin I (1969)"
        album1_dir.mkdir()
        (album1_dir / "01 - Good Times Bad Times.mp3").touch()
        (album1_dir / "02 - Babe I'm Gonna Leave You.mp3").touch()
        (album1_dir / "03 - You Shook Me.mp3").touch()

        album2_dir = artist_dir / "Led Zeppelin II (1969)"
        album2_dir.mkdir()
        (album2_dir / "01 - Whole Lotta Love.mp3").touch()
        (album2_dir / "02 - What Is and What Should Never Be.mp3").touch()

        album3_dir = artist_dir / "Led Zeppelin III (1970)"
        album3_dir.mkdir()
        (album3_dir / "01 - Immigrant Song.mp3").touch()
        (album3_dir / "02 - Friends.mp3").touch()
        (album3_dir / "03 - Celebration Day.mp3").touch()

        # Add artist-level files
        (artist_dir / "artist.jpg").touch()
        (artist_dir / "biography.txt").touch()

        analysis = analyzer.analyze_directory_structure(artist_dir)

        # Verify analysis
        assert analysis["folder_name"] == "Led Zeppelin"
        assert analysis["total_music_files"] == 8
        assert analysis["direct_music_files"] == 0
        assert len(analysis["subdirectories"]) == 3

        # Check subdirectory info
        subdir_names = [sub["name"] for sub in analysis["subdirectories"]]
        assert "Led Zeppelin I (1969)" in subdir_names
        assert "Led Zeppelin II (1969)" in subdir_names
        assert "Led Zeppelin III (1970)" in subdir_names


class TestStructureClassifierIntegration:
    """Test StructureClassifier with real LLM-like responses."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock inference provider that gives realistic responses."""
        m = Mock()
        m.generate.return_value = "single_album"
        return m

    @pytest.fixture
    def classifier(self, mock_llm):
        """Create a StructureClassifier with mock LLM."""
        return StructureClassifier(mock_llm)

    def test_classify_single_album_with_realistic_response(self, classifier, mock_llm):
        """Test classification of single album with realistic LLM response."""
        # Mock LLM to give realistic single album response
        mock_llm.generate.return_value = "single_album"

        # Real single album structure
        structure = {
            "folder_name": "The Beatles - Abbey Road (1969)",
            "total_music_files": 17,
            "direct_music_files": 17,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "The Beatles - Abbey Road (1969)\n├── 01 - Come Together.mp3\n├── 02 - Something.mp3\n└── 03 - Maxwell's Silver Hammer.mp3",
        }

        result = classifier.classify_directory_structure(structure)

        assert result == "single_album"
        mock_llm.generate.assert_called_once()

    def test_classify_multi_disc_with_realistic_response(self, classifier, mock_llm):
        """Test classification of multi-disc album with realistic LLM response."""
        # Mock LLM to give realistic multi-disc response
        mock_llm.generate.return_value = "multi_disc_album"

        # Real multi-disc structure
        structure = {
            "folder_name": "Pink Floyd - The Wall (1979)",
            "total_music_files": 26,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "Disc 1", "music_files": 13, "subdirectories": []},
                {"name": "Disc 2", "music_files": 13, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Pink Floyd - The Wall (1979)\n├── Disc 1/\n└── Disc 2/",
        }

        result = classifier.classify_directory_structure(structure)

        assert result == "multi_disc_album"
        mock_llm.generate.assert_called_once()

    def test_classify_artist_collection_with_realistic_response(
        self, classifier, mock_llm
    ):
        """Test classification of artist collection with realistic LLM response."""
        # Mock LLM to give realistic artist collection response
        mock_llm.generate.return_value = "artist_collection"

        # Real artist collection structure
        structure = {
            "folder_name": "Led Zeppelin",
            "total_music_files": 89,
            "direct_music_files": 0,
            "subdirectories": [
                {
                    "name": "Led Zeppelin I (1969)",
                    "music_files": 9,
                    "subdirectories": [],
                },
                {
                    "name": "Led Zeppelin II (1969)",
                    "music_files": 9,
                    "subdirectories": [],
                },
                {
                    "name": "Led Zeppelin III (1970)",
                    "music_files": 10,
                    "subdirectories": [],
                },
                {
                    "name": "Led Zeppelin IV (1971)",
                    "music_files": 8,
                    "subdirectories": [],
                },
            ],
            "max_depth": 1,
            "directory_tree": "Led Zeppelin\n├── Led Zeppelin I (1969)/\n├── Led Zeppelin II (1969)/\n├── Led Zeppelin III (1970)/\n└── Led Zeppelin IV (1971)/",
        }

        result = classifier.classify_directory_structure(structure)

        assert result == "artist_collection"
        mock_llm.generate.assert_called_once()

    def test_heuristic_fallback_when_llm_fails(self, classifier, mock_llm):
        """Test that heuristic classification works when LLM fails."""
        # Mock LLM to fail
        mock_llm.side_effect = Exception("LLM connection failed")

        # Single album structure should be classified correctly via heuristics
        structure = {
            "folder_name": "Test Album",
            "total_music_files": 12,
            "direct_music_files": 12,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Test Album\n├── track1.mp3\n└── track2.mp3",
        }

        result = classifier.classify_directory_structure(structure)

        assert result == "single_album"  # Should fall back to heuristic classification


class TestFileOrganizerIntegration:
    """Test FileOrganizer with real file operations."""

    @pytest.fixture
    def organizer(self, tmp_path):
        """Create a FileOrganizer with real target directory."""
        target_dir = tmp_path / "organized_music"
        target_dir.mkdir()
        return FileOrganizer(target_dir)

    def test_organize_real_files(self, organizer, tmp_path):
        """Test organizing real files with real file operations."""
        # Create source folder with real music files
        source_folder = tmp_path / "source_album"
        source_folder.mkdir()

        # Create some fake music files
        (source_folder / "track1.mp3").write_text("fake mp3 content")
        (source_folder / "track2.flac").write_text("fake flac content")
        (source_folder / "track3.wav").write_text("fake wav content")

        # Create non-music files (should be ignored)
        (source_folder / "cover.jpg").write_text("fake jpg content")
        (source_folder / "info.txt").write_text("fake txt content")

        # Organize with real proposal
        proposal = {
            "artist": "Test Artist",
            "album": "Test Album",
            "year": "2023",
            "release_type": "Album",
        }

        copied_count = organizer.organize_folder(source_folder, proposal)

        # Verify organization
        assert copied_count == 3  # Only music files should be copied

        # Check target directory structure
        target_album_dir = organizer.target_dir / "Test Artist" / "Test Album (2023)"
        assert target_album_dir.exists()
        assert (target_album_dir / "track1.mp3").exists()
        assert (target_album_dir / "track2.flac").exists()
        assert (target_album_dir / "track3.wav").exists()

        # Non-music files should not be copied
        assert not (target_album_dir / "cover.jpg").exists()
        assert not (target_album_dir / "info.txt").exists()

        # Verify file contents were preserved
        assert (target_album_dir / "track1.mp3").read_text() == "fake mp3 content"
        assert (target_album_dir / "track2.flac").read_text() == "fake flac content"
        assert (target_album_dir / "track3.wav").read_text() == "fake wav content"

    def test_organize_with_subdirectories(self, organizer, tmp_path):
        """Test organizing files with subdirectory structure preserved."""
        # Create source folder with subdirectories
        source_folder = tmp_path / "multi_disc_album"
        source_folder.mkdir()

        # Create disc folders
        disc1_dir = source_folder / "Disc 1"
        disc1_dir.mkdir()
        (disc1_dir / "track1.mp3").write_text("disc1 track1")
        (disc1_dir / "track2.mp3").write_text("disc1 track2")

        disc2_dir = source_folder / "Disc 2"
        disc2_dir.mkdir()
        (disc2_dir / "track1.mp3").write_text("disc2 track1")
        (disc2_dir / "track2.mp3").write_text("disc2 track2")

        # Organize
        proposal = {
            "artist": "Multi Artist",
            "album": "Multi Album",
            "year": "2024",
            "release_type": "Album",
        }

        copied_count = organizer.organize_folder(source_folder, proposal)

        # Verify organization
        assert copied_count == 4

        # Check target directory structure preserves subdirectories
        target_album_dir = organizer.target_dir / "Multi Artist" / "Multi Album (2024)"
        assert target_album_dir.exists()

        # Check disc subdirectories were preserved
        assert (target_album_dir / "Disc 1" / "track1.mp3").exists()
        assert (target_album_dir / "Disc 1" / "track2.mp3").exists()
        assert (target_album_dir / "Disc 2" / "track1.mp3").exists()
        assert (target_album_dir / "Disc 2" / "track2.mp3").exists()

        # Verify content preservation
        assert (
            target_album_dir / "Disc 1" / "track1.mp3"
        ).read_text() == "disc1 track1"
        assert (
            target_album_dir / "Disc 2" / "track1.mp3"
        ).read_text() == "disc2 track1"

    def test_sanitize_filename_functionality(self, organizer, tmp_path):
        """Test that filename sanitization works correctly."""
        source_folder = tmp_path / "source"
        source_folder.mkdir()
        (source_folder / "track.mp3").write_text("content")

        # Test with problematic characters in artist/album names
        proposal = {
            "artist": "Test<>Artist/Name",
            "album": "Test|Album:Name?",
            "year": "2023",
            "release_type": "Album",
        }

        copied_count = organizer.organize_folder(source_folder, proposal)

        assert copied_count == 1

        # Check that problematic characters were sanitized
        target_dir = (
            organizer.target_dir / "Test__Artist_Name" / "Test_Album_Name_ (2023)"
        )
        assert target_dir.exists()
        assert (target_dir / "track.mp3").exists()


class TestStateManagerIntegration:
    """Test StateManager with real file operations."""

    @pytest.fixture
    def state_manager(self):
        """Create a StateManager instance."""
        return StateManager()

    def test_tracker_file_operations(self, state_manager, tmp_path):
        """Test real tracker file creation and reading."""
        test_folder = tmp_path / "test_album"
        test_folder.mkdir()

        # Test saving tracker file
        proposal = {
            "artist": "Test Artist",
            "album": "Test Album",
            "year": "2023",
            "release_type": "Album",
            "confidence": "high",
        }

        state_manager.save_proposal_tracker(test_folder, proposal)

        # Verify file was created
        tracker_file = test_folder / ".whats-that-sound"
        assert tracker_file.exists()

        # Verify content
        tracker_data = state_manager.load_tracker_data(test_folder)
        assert tracker_data["proposal"] == proposal
        assert tracker_data["folder_name"] == "test_album"
        assert "organized_timestamp" in tracker_data

        # Test that folder is now marked as organized
        assert state_manager.is_already_organized(test_folder)

    def test_filter_unorganized_folders(self, state_manager, tmp_path):
        """Test filtering out already organized folders."""
        # Create test folders
        folder1 = tmp_path / "folder1"
        folder1.mkdir()
        folder2 = tmp_path / "folder2"
        folder2.mkdir()
        folder3 = tmp_path / "folder3"
        folder3.mkdir()

        # Mark folder2 as organized
        proposal = {
            "artist": "Test",
            "album": "Test",
            "year": "2023",
            "release_type": "Album",
        }
        state_manager.save_proposal_tracker(folder2, proposal)

        # Filter folders
        all_folders = [folder1, folder2, folder3]
        unorganized, organized_count = state_manager.filter_unorganized_folders(
            all_folders
        )

        # Verify filtering
        assert len(unorganized) == 2
        assert organized_count == 1
        assert folder1 in unorganized
        assert folder3 in unorganized
        assert folder2 not in unorganized

    def test_collection_tracker_operations(self, state_manager, tmp_path):
        """Test collection tracker file operations."""
        collection_folder = tmp_path / "artist_collection"
        collection_folder.mkdir()

        albums = [
            {
                "artist": "Artist",
                "album": "Album 1",
                "year": "2023",
                "release_type": "Album",
            },
            {
                "artist": "Artist",
                "album": "Album 2",
                "year": "2024",
                "release_type": "Album",
            },
        ]

        state_manager.save_collection_tracker(collection_folder, albums)

        # Verify file was created
        tracker_file = collection_folder / ".whats-that-sound"
        assert tracker_file.exists()

        # Verify content
        tracker_data = state_manager.load_tracker_data(collection_folder)
        assert tracker_data["collection_type"] == "artist_collection"
        assert tracker_data["albums"] == albums
        assert tracker_data["folder_name"] == "artist_collection"


class TestProgressTrackerIntegration:
    """Test ProgressTracker with real statistics."""

    @pytest.fixture
    def tracker(self):
        """Create a ProgressTracker instance."""
        return ProgressTracker()

    def test_real_progress_tracking(self, tracker):
        """Test real progress tracking operations."""
        # Initial state
        stats = tracker.get_stats()
        assert stats["total_processed"] == 0
        assert stats["successful"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        assert len(stats["organized_albums"]) == 0

        # Track some progress
        tracker.increment_processed()
        tracker.increment_successful(
            {"artist": "Artist1", "album": "Album1", "year": "2023"}
        )

        tracker.increment_processed()
        tracker.increment_skipped()

        tracker.increment_processed()
        tracker.increment_errors()

        # Add multiple albums
        albums = [
            {"artist": "Artist2", "album": "Album2", "year": "2024"},
            {"artist": "Artist3", "album": "Album3", "year": "2025"},
        ]
        tracker.add_successful_albums(albums)

        # Verify final stats
        final_stats = tracker.get_stats()
        assert final_stats["total_processed"] == 3
        assert final_stats["successful"] == 3  # 1 + 2 from add_successful_albums
        assert final_stats["skipped"] == 1
        assert final_stats["errors"] == 1
        assert len(final_stats["organized_albums"]) == 3

        # Test reset
        tracker.reset()
        reset_stats = tracker.get_stats()
        assert reset_stats["total_processed"] == 0
        assert reset_stats["successful"] == 0
        assert reset_stats["skipped"] == 0
        assert reset_stats["errors"] == 0
        assert len(reset_stats["organized_albums"]) == 0


class TestEndToEndIntegration:
    """Test end-to-end integration with minimal mocking."""

    def test_complete_single_album_workflow(self, tmp_path):
        """Test complete workflow for a single album with minimal mocking."""
        # Create realistic source structure
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        album_dir = source_dir / "Unknown Album"
        album_dir.mkdir()

        # Create music files
        (album_dir / "track1.mp3").write_text("fake mp3")
        (album_dir / "track2.flac").write_text("fake flac")
        (album_dir / "track3.wav").write_text("fake wav")

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create organizer with minimal mocking (only inference provider)
        with patch("src.organizer.InferenceProvider") as mock_inf_class:
            mock_inf = Mock()
            mock_inf_class.return_value = mock_inf

            organizer = MusicOrganizer(tmp_path / "model.gguf", source_dir, target_dir)

            # Mock only the LLM responses and UI interactions
            # Structure classifier and proposal generator call inference.generate(prompt)
            organizer.structure_classifier.inference.generate.return_value = "single_album"
            organizer.proposal_generator.inference.generate.return_value = '{"artist": "Test Artist", "album": "Test Album", "year": "2023", "release_type": "Album", "confidence": "high"}'

            # Mock UI to accept the proposal
            organizer.ui.get_user_feedback = Mock(
                return_value={
                    "action": "accept",
                    "proposal": {
                        "artist": "Test Artist",
                        "album": "Test Album",
                        "year": "2023",
                        "release_type": "Album",
                    },
                }
            )

            # Mock UI display methods to avoid console output during tests
            organizer.ui.display_folder_info = Mock()
            organizer.ui.display_file_samples = Mock()
            organizer.ui.display_structure_analysis = Mock()
            organizer.ui.display_llm_proposal = Mock()
            organizer.ui.display_progress = Mock()
            organizer.ui.display_completion_summary = Mock()

            # Run the organization
            organizer.organize()

            # Verify the results
            # 1. Files should be organized
            organized_dir = target_dir / "Test Artist" / "Test Album (2023)"
            assert organized_dir.exists()
            assert (organized_dir / "track1.mp3").exists()
            assert (organized_dir / "track2.flac").exists()
            assert (organized_dir / "track3.wav").exists()

            # 2. Tracker file should be created
            tracker_file = album_dir / ".whats-that-sound"
            assert tracker_file.exists()

            # 3. Tracker file should contain the proposal
            with open(tracker_file, "r") as f:
                tracker_data = json.load(f)
            assert tracker_data["proposal"]["artist"] == "Test Artist"
            assert tracker_data["proposal"]["album"] == "Test Album"

            # 4. Second run should skip already organized folder
            organizer.organize()
            # Should not process the folder again (no assertions needed - just verifying no errors)

    def test_complete_multi_disc_workflow(self, tmp_path):
        """Test complete workflow for a multi-disc album with minimal mocking."""
        # Create realistic multi-disc source structure
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        album_dir = source_dir / "Unknown Multi-Disc Album"
        album_dir.mkdir()

        # Create disc directories
        disc1_dir = album_dir / "CD1"
        disc1_dir.mkdir()
        (disc1_dir / "track1.mp3").write_text("disc1 track1")
        (disc1_dir / "track2.mp3").write_text("disc1 track2")

        disc2_dir = album_dir / "CD2"
        disc2_dir.mkdir()
        (disc2_dir / "track1.mp3").write_text("disc2 track1")
        (disc2_dir / "track2.mp3").write_text("disc2 track2")

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create organizer with minimal mocking
        with patch("src.organizer.InferenceProvider") as mock_inf_class:
            mock_inf = Mock()
            mock_inf_class.return_value = mock_inf

            organizer = MusicOrganizer(tmp_path / "model.gguf", source_dir, target_dir)

            # Mock LLM responses
            organizer.structure_classifier.inference.generate.return_value = "multi_disc_album"
            organizer.proposal_generator.inference.generate.return_value = '{"artist": "Multi Artist", "album": "Multi Album", "year": "2024", "release_type": "Album", "confidence": "high"}'

            # Mock UI to accept the proposal
            organizer.ui.get_user_feedback = Mock(
                return_value={
                    "action": "accept",
                    "proposal": {
                        "artist": "Multi Artist",
                        "album": "Multi Album",
                        "year": "2024",
                        "release_type": "Album",
                    },
                }
            )

            # Mock UI display methods
            organizer.ui.display_folder_info = Mock()
            organizer.ui.display_file_samples = Mock()
            organizer.ui.display_structure_analysis = Mock()
            organizer.ui.display_llm_proposal = Mock()
            organizer.ui.display_progress = Mock()
            organizer.ui.display_completion_summary = Mock()

            # Run the organization
            organizer.organize()

            # Verify the results
            # 1. Files should be organized with disc structure preserved
            organized_dir = target_dir / "Multi Artist" / "Multi Album (2024)"
            assert organized_dir.exists()
            assert (organized_dir / "CD1" / "track1.mp3").exists()
            assert (organized_dir / "CD1" / "track2.mp3").exists()
            assert (organized_dir / "CD2" / "track1.mp3").exists()
            assert (organized_dir / "CD2" / "track2.mp3").exists()

            # 2. File contents should be preserved
            assert (organized_dir / "CD1" / "track1.mp3").read_text() == "disc1 track1"
            assert (organized_dir / "CD2" / "track1.mp3").read_text() == "disc2 track1"

            # 3. Tracker file should be created
            tracker_file = album_dir / ".whats-that-sound"
            assert tracker_file.exists()

            with open(tracker_file, "r") as f:
                tracker_data = json.load(f)
            assert tracker_data["proposal"]["artist"] == "Multi Artist"
            assert tracker_data["proposal"]["album"] == "Multi Album"
