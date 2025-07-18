"""Tests for the DirectoryAnalyzer class."""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.analyzers.directory_analyzer import DirectoryAnalyzer
from src.metadata import MetadataExtractor


class TestDirectoryAnalyzer:
    """Test cases for DirectoryAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a DirectoryAnalyzer instance for testing."""
        return DirectoryAnalyzer()

    def test_analyze_directory_structure_single_album(self, analyzer, tmp_path):
        """Test directory structure analysis for single album."""
        with patch.object(MetadataExtractor, 'SUPPORTED_FORMATS', [".mp3", ".flac"]):
            # Create test folder structure
            test_folder = tmp_path / "test_album"
            test_folder.mkdir()
            (test_folder / "track1.mp3").touch()
            (test_folder / "track2.mp3").touch()
            (test_folder / "cover.jpg").touch()  # Non-music file

            analysis = analyzer.analyze_directory_structure(test_folder)

            assert analysis["folder_name"] == "test_album"
            assert analysis["total_music_files"] == 2
            assert analysis["direct_music_files"] == 2
            assert len(analysis["subdirectories"]) == 0
            assert analysis["max_depth"] == 0
            assert "track1.mp3" in analysis["directory_tree"]
            assert "track2.mp3" in analysis["directory_tree"]

    def test_analyze_directory_structure_multi_disc(self, analyzer, tmp_path):
        """Test directory structure analysis for multi-disc album."""
        with patch.object(MetadataExtractor, 'SUPPORTED_FORMATS', [".mp3", ".flac"]):
            # Create test folder structure
            test_folder = tmp_path / "test_album"
            test_folder.mkdir()

            cd1_folder = test_folder / "CD1"
            cd1_folder.mkdir()
            (cd1_folder / "track1.mp3").touch()
            (cd1_folder / "track2.mp3").touch()

            cd2_folder = test_folder / "CD2"
            cd2_folder.mkdir()
            (cd2_folder / "track3.mp3").touch()
            (cd2_folder / "track4.mp3").touch()

            analysis = analyzer.analyze_directory_structure(test_folder)

            assert analysis["folder_name"] == "test_album"
            assert analysis["total_music_files"] == 4
            assert analysis["direct_music_files"] == 0
            assert len(analysis["subdirectories"]) == 2
            assert analysis["max_depth"] == 1

            # Check subdirectory details
            subdir_names = [sub["name"] for sub in analysis["subdirectories"]]
            assert "CD1" in subdir_names
            assert "CD2" in subdir_names

    def test_analyze_directory_structure_artist_collection(self, analyzer, tmp_path):
        """Test directory structure analysis for artist collection."""
        with patch.object(MetadataExtractor, 'SUPPORTED_FORMATS', [".mp3", ".flac"]):
            # Create test folder structure
            test_folder = tmp_path / "Artist Name"
            test_folder.mkdir()

            album1_folder = test_folder / "First Album"
            album1_folder.mkdir()
            (album1_folder / "track1.mp3").touch()
            (album1_folder / "track2.mp3").touch()

            album2_folder = test_folder / "Second Album"
            album2_folder.mkdir()
            (album2_folder / "track3.mp3").touch()

            analysis = analyzer.analyze_directory_structure(test_folder)

            assert analysis["folder_name"] == "Artist Name"
            assert analysis["total_music_files"] == 3
            assert analysis["direct_music_files"] == 0
            assert len(analysis["subdirectories"]) == 2

            # Check subdirectory details
            subdir_names = [sub["name"] for sub in analysis["subdirectories"]]
            assert "First Album" in subdir_names
            assert "Second Album" in subdir_names

    def test_analyze_empty_directory(self, analyzer, tmp_path):
        """Test analysis of empty directory."""
        test_folder = tmp_path / "empty_folder"
        test_folder.mkdir()

        analysis = analyzer.analyze_directory_structure(test_folder)

        assert analysis["folder_name"] == "empty_folder"
        assert analysis["total_music_files"] == 0
        assert analysis["direct_music_files"] == 0
        assert len(analysis["subdirectories"]) == 0
        assert analysis["max_depth"] == 0

    def test_analyze_deep_directory_structure(self, analyzer, tmp_path):
        """Test analysis of deeply nested directory structure."""
        with patch.object(MetadataExtractor, 'SUPPORTED_FORMATS', [".mp3"]):
            # Create deep structure
            test_folder = tmp_path / "deep_structure"
            test_folder.mkdir()

            # Create nested structure: deep_structure/level1/level2/level3/track.mp3
            level1 = test_folder / "level1"
            level1.mkdir()
            level2 = level1 / "level2"
            level2.mkdir()
            level3 = level2 / "level3"
            level3.mkdir()
            (level3 / "deep_track.mp3").touch()

            analysis = analyzer.analyze_directory_structure(test_folder)

            assert analysis["folder_name"] == "deep_structure"
            assert analysis["total_music_files"] == 1
            assert analysis["direct_music_files"] == 0
            assert analysis["max_depth"] >= 3  # Should traverse at least 3 levels

    def test_permission_error_handling(self, analyzer, tmp_path):
        """Test handling of permission errors."""
        test_folder = tmp_path / "test_folder"
        test_folder.mkdir()

        # Mock permission error
        with patch.object(Path, 'iterdir', side_effect=PermissionError("Access denied")):
            analysis = analyzer.analyze_directory_structure(test_folder)

            assert analysis["folder_name"] == "test_folder"
            assert "[Permission Denied]" in analysis["directory_tree"]

    def test_extract_folder_metadata(self, analyzer, tmp_path):
        """Test metadata extraction delegation."""
        test_folder = tmp_path / "test_folder"
        test_folder.mkdir()

        # Mock the metadata extractor
        with patch.object(analyzer.metadata_extractor, 'extract_folder_metadata') as mock_extract:
            mock_extract.return_value = {"test": "metadata"}

            result = analyzer.extract_folder_metadata(test_folder)

            mock_extract.assert_called_once_with(test_folder)
            assert result == {"test": "metadata"} 