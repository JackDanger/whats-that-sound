"""Integration tests for processor components."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from src.processors.album_processor import AlbumProcessor
from src.processors.collection_processor import CollectionProcessor
from src.analyzers.directory_analyzer import DirectoryAnalyzer
from src.generators.proposal_generator import ProposalGenerator
from src.organizers.file_organizer import FileOrganizer
from src.trackers.state_manager import StateManager
from src.ui import InteractiveUI


class TestAlbumProcessorIntegration:
    """Test AlbumProcessor with real component interactions."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM for testing."""
        return Mock()

    @pytest.fixture
    def processor(self, mock_llm, tmp_path):
        """Create an AlbumProcessor with real components."""
        # Create real components
        directory_analyzer = DirectoryAnalyzer()
        proposal_generator = ProposalGenerator(mock_llm)
        target_dir = tmp_path / "organized"
        target_dir.mkdir()
        file_organizer = FileOrganizer(target_dir)
        state_manager = StateManager()
        ui = InteractiveUI()

        return AlbumProcessor(
            directory_analyzer, proposal_generator, file_organizer, state_manager, ui
        )

    def test_process_single_album_complete_workflow(
        self, processor, mock_llm, tmp_path
    ):
        """Test complete single album processing workflow."""
        # Create realistic single album structure
        album_dir = tmp_path / "Test Album"
        album_dir.mkdir()

        # Create music files
        (album_dir / "01 - First Song.mp3").write_text("fake mp3 content")
        (album_dir / "02 - Second Song.flac").write_text("fake flac content")
        (album_dir / "03 - Third Song.wav").write_text("fake wav content")

        # Create structure analysis
        structure_analysis = {
            "folder_name": "Test Album",
            "total_music_files": 3,
            "direct_music_files": 3,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Test Album\n├── 01 - First Song.mp3\n├── 02 - Second Song.flac\n└── 03 - Third Song.wav",
        }

        # Mock LLM response
        mock_llm.return_value = {
            "choices": [
                {
                    "text": '{"artist": "Test Artist", "album": "Test Album", "year": "2023", "release_type": "Album", "confidence": "high", "reasoning": "Clear album structure"}'
                }
            ]
        }

        # Mock UI to accept proposal
        processor.ui.display_folder_info = Mock()
        processor.ui.display_file_samples = Mock()
        processor.ui.display_llm_proposal = Mock()
        processor.ui.get_user_feedback = Mock(
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

        # Process the album
        result = processor.process_single_album(album_dir, structure_analysis)

        # Verify success
        assert result is True

        # Verify files were organized
        target_dir = (
            processor.file_organizer.target_dir / "Test Artist" / "Test Album (2023)"
        )
        assert target_dir.exists()
        assert (target_dir / "01 - First Song.mp3").exists()
        assert (target_dir / "02 - Second Song.flac").exists()
        assert (target_dir / "03 - Third Song.wav").exists()

        # Verify tracker file was created
        tracker_file = album_dir / ".whats-that-sound"
        assert tracker_file.exists()

        # Verify tracker content
        with open(tracker_file, "r") as f:
            tracker_data = json.load(f)
        assert tracker_data["proposal"]["artist"] == "Test Artist"
        assert tracker_data["proposal"]["album"] == "Test Album"
        assert tracker_data["folder_name"] == "Test Album"

    def test_process_single_album_user_reconsider(self, processor, mock_llm, tmp_path):
        """Test single album processing with user reconsideration."""
        # Create album structure
        album_dir = tmp_path / "Unclear Album"
        album_dir.mkdir()
        (album_dir / "song1.mp3").write_text("content1")
        (album_dir / "song2.mp3").write_text("content2")

        structure_analysis = {
            "folder_name": "Unclear Album",
            "total_music_files": 2,
            "direct_music_files": 2,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Unclear Album\n├── song1.mp3\n└── song2.mp3",
        }

        # Mock LLM responses (initial and reconsidered)
        mock_llm.side_effect = [
            {
                "choices": [
                    {
                        "text": '{"artist": "Wrong Artist", "album": "Wrong Album", "year": "2000", "release_type": "Album", "confidence": "low", "reasoning": "Uncertain"}'
                    }
                ]
            },
            {
                "choices": [
                    {
                        "text": '{"artist": "Correct Artist", "album": "Correct Album", "year": "2023", "release_type": "Album", "confidence": "high", "reasoning": "Corrected with feedback"}'
                    }
                ]
            },
        ]

        # Mock UI interaction sequence
        processor.ui.display_folder_info = Mock()
        processor.ui.display_file_samples = Mock()
        processor.ui.display_llm_proposal = Mock()

        # First interaction: user requests reconsideration
        # Second interaction: user accepts
        processor.ui.get_user_feedback = Mock(
            side_effect=[
                {
                    "action": "reconsider",
                    "feedback": "This is actually by Correct Artist from 2023",
                },
                {
                    "action": "accept",
                    "proposal": {
                        "artist": "Correct Artist",
                        "album": "Correct Album",
                        "year": "2023",
                        "release_type": "Album",
                    },
                },
            ]
        )

        # Process the album
        result = processor.process_single_album(album_dir, structure_analysis)

        # Verify success
        assert result is True

        # Verify LLM was called twice (initial + reconsideration)
        assert mock_llm.call_count == 2

        # Verify files were organized with corrected information
        target_dir = (
            processor.file_organizer.target_dir
            / "Correct Artist"
            / "Correct Album (2023)"
        )
        assert target_dir.exists()
        assert (target_dir / "song1.mp3").exists()
        assert (target_dir / "song2.mp3").exists()

        # Verify tracker file contains corrected information
        tracker_file = album_dir / ".whats-that-sound"
        assert tracker_file.exists()
        with open(tracker_file, "r") as f:
            tracker_data = json.load(f)
        assert tracker_data["proposal"]["artist"] == "Correct Artist"
        assert tracker_data["proposal"]["album"] == "Correct Album"

    def test_process_single_album_user_skip(self, processor, mock_llm, tmp_path):
        """Test single album processing with user skip."""
        # Create album structure
        album_dir = tmp_path / "Skip Album"
        album_dir.mkdir()
        (album_dir / "track.mp3").write_text("content")

        structure_analysis = {
            "folder_name": "Skip Album",
            "total_music_files": 1,
            "direct_music_files": 1,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Skip Album\n└── track.mp3",
        }

        # Mock LLM response
        mock_llm.return_value = {
            "choices": [
                {
                    "text": '{"artist": "Some Artist", "album": "Some Album", "year": "2023", "release_type": "Album", "confidence": "medium", "reasoning": "Guess"}'
                }
            ]
        }

        # Mock UI to skip
        processor.ui.display_folder_info = Mock()
        processor.ui.display_file_samples = Mock()
        processor.ui.display_llm_proposal = Mock()
        processor.ui.get_user_feedback = Mock(return_value={"action": "skip"})

        # Process the album
        result = processor.process_single_album(album_dir, structure_analysis)

        # Verify skipped
        assert result is False

        # Verify no files were organized
        target_dirs = list(processor.file_organizer.target_dir.iterdir())
        assert len(target_dirs) == 0

        # Verify no tracker file was created
        tracker_file = album_dir / ".whats-that-sound"
        assert not tracker_file.exists()

    def test_process_multi_disc_album_workflow(self, processor, mock_llm, tmp_path):
        """Test multi-disc album processing workflow."""
        # Create multi-disc structure
        album_dir = tmp_path / "Multi-Disc Album"
        album_dir.mkdir()

        # Create disc folders
        disc1_dir = album_dir / "Disc 1"
        disc1_dir.mkdir()
        (disc1_dir / "01 - Track1.mp3").write_text("disc1 track1")
        (disc1_dir / "02 - Track2.mp3").write_text("disc1 track2")

        disc2_dir = album_dir / "Disc 2"
        disc2_dir.mkdir()
        (disc2_dir / "01 - Track3.mp3").write_text("disc2 track1")
        (disc2_dir / "02 - Track4.mp3").write_text("disc2 track2")

        structure_analysis = {
            "folder_name": "Multi-Disc Album",
            "total_music_files": 4,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "Disc 1", "music_files": 2, "subdirectories": []},
                {"name": "Disc 2", "music_files": 2, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Multi-Disc Album\n├── Disc 1/\n└── Disc 2/",
        }

        # Mock LLM response
        mock_llm.return_value = {
            "choices": [
                {
                    "text": '{"artist": "Multi Artist", "album": "Multi Album", "year": "2024", "release_type": "Album", "confidence": "high", "reasoning": "Multi-disc structure"}'
                }
            ]
        }

        # Mock UI to accept proposal
        processor.ui.display_folder_info = Mock()
        processor.ui.display_file_samples = Mock()
        processor.ui.display_llm_proposal = Mock()
        processor.ui.get_user_feedback = Mock(
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

        # Process the album
        result = processor.process_multi_disc_album(album_dir, structure_analysis)

        # Verify success
        assert result is True

        # Verify files were organized with disc structure preserved
        target_dir = (
            processor.file_organizer.target_dir / "Multi Artist" / "Multi Album (2024)"
        )
        assert target_dir.exists()
        assert (target_dir / "Disc 1" / "01 - Track1.mp3").exists()
        assert (target_dir / "Disc 1" / "02 - Track2.mp3").exists()
        assert (target_dir / "Disc 2" / "01 - Track3.mp3").exists()
        assert (target_dir / "Disc 2" / "02 - Track4.mp3").exists()

        # Verify file contents preserved
        assert (target_dir / "Disc 1" / "01 - Track1.mp3").read_text() == "disc1 track1"
        assert (target_dir / "Disc 2" / "01 - Track3.mp3").read_text() == "disc2 track1"

        # Verify tracker file created
        tracker_file = album_dir / ".whats-that-sound"
        assert tracker_file.exists()


class TestCollectionProcessorIntegration:
    """Test CollectionProcessor with real component interactions."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM for testing."""
        return Mock()

    @pytest.fixture
    def processor(self, mock_llm, tmp_path):
        """Create a CollectionProcessor with real components."""
        # Create real components
        directory_analyzer = DirectoryAnalyzer()
        proposal_generator = ProposalGenerator(mock_llm)
        target_dir = tmp_path / "organized"
        target_dir.mkdir()
        file_organizer = FileOrganizer(target_dir)
        state_manager = StateManager()
        ui = InteractiveUI()

        return CollectionProcessor(
            directory_analyzer, proposal_generator, file_organizer, state_manager, ui
        )

    def test_process_artist_collection_complete_workflow(
        self, processor, mock_llm, tmp_path
    ):
        """Test complete artist collection processing workflow."""
        # Create realistic artist collection structure
        artist_dir = tmp_path / "Test Artist"
        artist_dir.mkdir()

        # Create album folders
        album1_dir = artist_dir / "First Album"
        album1_dir.mkdir()
        (album1_dir / "01 - Song1.mp3").write_text("album1 song1")
        (album1_dir / "02 - Song2.mp3").write_text("album1 song2")

        album2_dir = artist_dir / "Second Album"
        album2_dir.mkdir()
        (album2_dir / "01 - Song3.mp3").write_text("album2 song1")
        (album2_dir / "02 - Song4.mp3").write_text("album2 song2")

        # Create structure analysis
        structure_analysis = {
            "folder_name": "Test Artist",
            "total_music_files": 4,
            "direct_music_files": 0,
            "subdirectories": [
                {
                    "name": "First Album",
                    "path": str(album1_dir),
                    "music_files": 2,
                    "subdirectories": [],
                },
                {
                    "name": "Second Album",
                    "path": str(album2_dir),
                    "music_files": 2,
                    "subdirectories": [],
                },
            ],
            "max_depth": 1,
            "directory_tree": "Test Artist\n├── First Album/\n└── Second Album/",
        }

        # Mock LLM responses for each album
        mock_llm.side_effect = [
            {
                "choices": [
                    {
                        "text": '{"artist": "Test Artist", "album": "First Album", "year": "2022", "release_type": "Album", "confidence": "high", "reasoning": "First album"}'
                    }
                ]
            },
            {
                "choices": [
                    {
                        "text": '{"artist": "Test Artist", "album": "Second Album", "year": "2023", "release_type": "Album", "confidence": "high", "reasoning": "Second album"}'
                    }
                ]
            },
        ]

        # Mock UI to accept both proposals
        processor.ui.display_folder_info = Mock()
        processor.ui.display_file_samples = Mock()
        processor.ui.display_llm_proposal = Mock()
        processor.ui.get_user_feedback = Mock(
            side_effect=[
                {
                    "action": "accept",
                    "proposal": {
                        "artist": "Test Artist",
                        "album": "First Album",
                        "year": "2022",
                        "release_type": "Album",
                    },
                },
                {
                    "action": "accept",
                    "proposal": {
                        "artist": "Test Artist",
                        "album": "Second Album",
                        "year": "2023",
                        "release_type": "Album",
                    },
                },
            ]
        )

        # Process the collection
        result = processor.process_artist_collection(artist_dir, structure_analysis)

        # Verify success
        assert result is True

        # Verify both albums were organized
        target_base = processor.file_organizer.target_dir / "Test Artist"

        first_album_dir = target_base / "First Album (2022)"
        assert first_album_dir.exists()
        assert (first_album_dir / "01 - Song1.mp3").exists()
        assert (first_album_dir / "02 - Song2.mp3").exists()

        second_album_dir = target_base / "Second Album (2023)"
        assert second_album_dir.exists()
        assert (second_album_dir / "01 - Song3.mp3").exists()
        assert (second_album_dir / "02 - Song4.mp3").exists()

        # Verify file contents preserved
        assert (first_album_dir / "01 - Song1.mp3").read_text() == "album1 song1"
        assert (second_album_dir / "01 - Song3.mp3").read_text() == "album2 song1"

        # Verify collection tracker file was created
        tracker_file = artist_dir / ".whats-that-sound"
        assert tracker_file.exists()

        # Verify tracker content
        with open(tracker_file, "r") as f:
            tracker_data = json.load(f)
        assert tracker_data["collection_type"] == "artist_collection"
        assert tracker_data["folder_name"] == "Test Artist"
        assert len(tracker_data["albums"]) == 2
        assert tracker_data["albums"][0]["artist"] == "Test Artist"
        assert tracker_data["albums"][0]["album"] == "First Album"
        assert tracker_data["albums"][1]["artist"] == "Test Artist"
        assert tracker_data["albums"][1]["album"] == "Second Album"

    def test_process_artist_collection_mixed_actions(
        self, processor, mock_llm, tmp_path
    ):
        """Test artist collection processing with mixed user actions."""
        # Create artist collection structure
        artist_dir = tmp_path / "Mixed Artist"
        artist_dir.mkdir()

        # Create album folders
        album1_dir = artist_dir / "Good Album"
        album1_dir.mkdir()
        (album1_dir / "track1.mp3").write_text("good content")

        album2_dir = artist_dir / "Skip Album"
        album2_dir.mkdir()
        (album2_dir / "track2.mp3").write_text("skip content")

        album3_dir = artist_dir / "Another Good Album"
        album3_dir.mkdir()
        (album3_dir / "track3.mp3").write_text("another good content")

        # Create structure analysis
        structure_analysis = {
            "folder_name": "Mixed Artist",
            "total_music_files": 3,
            "direct_music_files": 0,
            "subdirectories": [
                {
                    "name": "Good Album",
                    "path": str(album1_dir),
                    "music_files": 1,
                    "subdirectories": [],
                },
                {
                    "name": "Skip Album",
                    "path": str(album2_dir),
                    "music_files": 1,
                    "subdirectories": [],
                },
                {
                    "name": "Another Good Album",
                    "path": str(album3_dir),
                    "music_files": 1,
                    "subdirectories": [],
                },
            ],
            "max_depth": 1,
            "directory_tree": "Mixed Artist\n├── Good Album/\n├── Skip Album/\n└── Another Good Album/",
        }

        # Mock LLM responses
        mock_llm.side_effect = [
            {
                "choices": [
                    {
                        "text": '{"artist": "Mixed Artist", "album": "Good Album", "year": "2021", "release_type": "Album", "confidence": "high", "reasoning": "Good album"}'
                    }
                ]
            },
            {
                "choices": [
                    {
                        "text": '{"artist": "Mixed Artist", "album": "Skip Album", "year": "2022", "release_type": "Album", "confidence": "low", "reasoning": "Uncertain"}'
                    }
                ]
            },
            {
                "choices": [
                    {
                        "text": '{"artist": "Mixed Artist", "album": "Another Good Album", "year": "2023", "release_type": "Album", "confidence": "high", "reasoning": "Another good album"}'
                    }
                ]
            },
        ]

        # Mock UI with mixed responses: accept, skip, accept
        processor.ui.display_folder_info = Mock()
        processor.ui.display_file_samples = Mock()
        processor.ui.display_llm_proposal = Mock()
        processor.ui.get_user_feedback = Mock(
            side_effect=[
                {
                    "action": "accept",
                    "proposal": {
                        "artist": "Mixed Artist",
                        "album": "Good Album",
                        "year": "2021",
                        "release_type": "Album",
                    },
                },
                {"action": "skip"},
                {
                    "action": "accept",
                    "proposal": {
                        "artist": "Mixed Artist",
                        "album": "Another Good Album",
                        "year": "2023",
                        "release_type": "Album",
                    },
                },
            ]
        )

        # Process the collection
        result = processor.process_artist_collection(artist_dir, structure_analysis)

        # Verify success (some albums organized)
        assert result is True

        # Verify only accepted albums were organized
        target_base = processor.file_organizer.target_dir / "Mixed Artist"

        good_album_dir = target_base / "Good Album (2021)"
        assert good_album_dir.exists()
        assert (good_album_dir / "track1.mp3").exists()

        another_good_album_dir = target_base / "Another Good Album (2023)"
        assert another_good_album_dir.exists()
        assert (another_good_album_dir / "track3.mp3").exists()

        # Verify skipped album was NOT organized
        skip_album_dirs = [d for d in target_base.iterdir() if "Skip Album" in d.name]
        assert len(skip_album_dirs) == 0

        # Verify collection tracker file was created with only successful albums
        tracker_file = artist_dir / ".whats-that-sound"
        assert tracker_file.exists()

        with open(tracker_file, "r") as f:
            tracker_data = json.load(f)
        assert tracker_data["collection_type"] == "artist_collection"
        assert len(tracker_data["albums"]) == 2  # Only the accepted albums
        album_names = [album["album"] for album in tracker_data["albums"]]
        assert "Good Album" in album_names
        assert "Another Good Album" in album_names
        assert "Skip Album" not in album_names

    def test_process_artist_collection_no_music_files(
        self, processor, mock_llm, tmp_path
    ):
        """Test artist collection processing with folders containing no music files."""
        # Create artist collection structure with some empty folders
        artist_dir = tmp_path / "Empty Artist"
        artist_dir.mkdir()

        # Create album folders
        album1_dir = artist_dir / "Real Album"
        album1_dir.mkdir()
        (album1_dir / "song.mp3").write_text("real content")

        empty_dir = artist_dir / "Empty Folder"
        empty_dir.mkdir()
        (empty_dir / "readme.txt").write_text("no music here")

        # Create structure analysis
        structure_analysis = {
            "folder_name": "Empty Artist",
            "total_music_files": 1,
            "direct_music_files": 0,
            "subdirectories": [
                {
                    "name": "Real Album",
                    "path": str(album1_dir),
                    "music_files": 1,
                    "subdirectories": [],
                },
                {
                    "name": "Empty Folder",
                    "path": str(empty_dir),
                    "music_files": 0,
                    "subdirectories": [],
                },
            ],
            "max_depth": 1,
            "directory_tree": "Empty Artist\n├── Real Album/\n└── Empty Folder/",
        }

        # Mock LLM response (should only be called once for the real album)
        mock_llm.return_value = {
            "choices": [
                {
                    "text": '{"artist": "Empty Artist", "album": "Real Album", "year": "2023", "release_type": "Album", "confidence": "high", "reasoning": "Only real album"}'
                }
            ]
        }

        # Mock UI to accept the proposal
        processor.ui.display_folder_info = Mock()
        processor.ui.display_file_samples = Mock()
        processor.ui.display_llm_proposal = Mock()
        processor.ui.get_user_feedback = Mock(
            return_value={
                "action": "accept",
                "proposal": {
                    "artist": "Empty Artist",
                    "album": "Real Album",
                    "year": "2023",
                    "release_type": "Album",
                },
            }
        )

        # Process the collection
        result = processor.process_artist_collection(artist_dir, structure_analysis)

        # Verify success
        assert result is True

        # Verify only the real album was processed
        mock_llm.assert_called_once()  # Should only be called once
        processor.ui.get_user_feedback.assert_called_once()  # Should only be called once

        # Verify only the real album was organized
        target_dir = (
            processor.file_organizer.target_dir / "Empty Artist" / "Real Album (2023)"
        )
        assert target_dir.exists()
        assert (target_dir / "song.mp3").exists()

        # Verify tracker file contains only one album
        tracker_file = artist_dir / ".whats-that-sound"
        assert tracker_file.exists()

        with open(tracker_file, "r") as f:
            tracker_data = json.load(f)
        assert len(tracker_data["albums"]) == 1
        assert tracker_data["albums"][0]["album"] == "Real Album"
