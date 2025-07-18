"""Tests for the StructureClassifier class."""

import pytest
from unittest.mock import Mock

from src.analyzers.structure_classifier import StructureClassifier


class TestStructureClassifier:
    """Test cases for StructureClassifier class."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM for testing."""
        return Mock()

    @pytest.fixture
    def classifier(self, mock_llm):
        """Create a StructureClassifier instance for testing."""
        return StructureClassifier(mock_llm)

    def test_classify_directory_structure_with_llm_success(self, classifier, mock_llm):
        """Test successful LLM-based directory structure classification."""
        # Mock LLM to return specific classification
        mock_llm.return_value = {
            "choices": [{"text": "multi_disc_album"}]
        }

        structure = {
            "folder_name": "Test Album",
            "total_music_files": 20,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "Disc 1", "music_files": 10, "subdirectories": []},
                {"name": "Disc 2", "music_files": 10, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Test tree"
        }

        classification = classifier.classify_directory_structure(structure)
        
        assert classification == "multi_disc_album"
        mock_llm.assert_called_once()

    def test_classify_directory_structure_with_llm_invalid_response(self, classifier, mock_llm):
        """Test classification with invalid LLM response falls back to heuristics."""
        # Mock LLM to return invalid classification
        mock_llm.return_value = {
            "choices": [{"text": "invalid_classification"}]
        }

        structure = {
            "folder_name": "Test Album",
            "total_music_files": 10,
            "direct_music_files": 10,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Test tree"
        }

        classification = classifier.classify_directory_structure(structure)
        
        # Should fall back to heuristic classification
        assert classification == "single_album"

    def test_classify_directory_structure_with_llm_error(self, classifier, mock_llm):
        """Test classification with LLM error falls back to heuristics."""
        # Mock LLM to raise an error
        mock_llm.side_effect = Exception("LLM error")

        structure = {
            "folder_name": "Test Album",
            "total_music_files": 10,
            "direct_music_files": 10,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Test tree"
        }

        classification = classifier.classify_directory_structure(structure)
        
        # Should fall back to heuristic classification
        assert classification == "single_album"

    def test_heuristic_classification_single_album(self, classifier):
        """Test heuristic classification for single album."""
        structure = {
            "subdirectories": [],
            "direct_music_files": 10,
        }

        classification = classifier._heuristic_classification(structure)
        assert classification == "single_album"

    def test_heuristic_classification_multi_disc_album(self, classifier):
        """Test heuristic classification for multi-disc album."""
        structure = {
            "subdirectories": [
                {"name": "CD1", "music_files": 12, "subdirectories": []},
                {"name": "CD2", "music_files": 8, "subdirectories": []},
            ],
            "direct_music_files": 0,
        }

        classification = classifier._heuristic_classification(structure)
        assert classification == "multi_disc_album"

    def test_heuristic_classification_artist_collection(self, classifier):
        """Test heuristic classification for artist collection."""
        structure = {
            "subdirectories": [
                {"name": "First Album", "music_files": 12, "subdirectories": []},
                {"name": "Second Album", "music_files": 15, "subdirectories": []},
                {"name": "Third Album", "music_files": 10, "subdirectories": []},
            ],
            "direct_music_files": 0,
        }

        classification = classifier._heuristic_classification(structure)
        assert classification == "artist_collection"

    def test_heuristic_classification_mixed_disc_patterns(self, classifier):
        """Test heuristic classification with mixed disc patterns."""
        structure = {
            "subdirectories": [
                {"name": "Volume 1", "music_files": 12, "subdirectories": []},
                {"name": "Random Folder", "music_files": 8, "subdirectories": []},
                {"name": "Disc 2", "music_files": 10, "subdirectories": []},
            ],
            "direct_music_files": 0,
        }

        classification = classifier._heuristic_classification(structure)
        # Should detect as multi-disc since 2 out of 3 have disc patterns (>= 50%)
        assert classification == "multi_disc_album"

    def test_heuristic_classification_with_direct_files_and_subdirs(self, classifier):
        """Test heuristic classification with both direct files and subdirectories."""
        structure = {
            "subdirectories": [
                {"name": "Bonus Tracks", "music_files": 3, "subdirectories": []},
            ],
            "direct_music_files": 12,
        }

        classification = classifier._heuristic_classification(structure)
        # Should still be classified as single album due to direct files
        assert classification == "single_album"

    def test_format_subdirectories_empty(self, classifier):
        """Test formatting of empty subdirectories list."""
        result = classifier._format_subdirectories([])
        assert result == "None"

    def test_format_subdirectories_normal(self, classifier):
        """Test formatting of normal subdirectories list."""
        subdirs = [
            {"name": "Album 1", "music_files": 10, "subdirectories": []},
            {"name": "Album 2", "music_files": 15, "subdirectories": ["Bonus"]},
        ]

        result = classifier._format_subdirectories(subdirs)
        
        assert "Album 1: 10 music files, 0 subdirs" in result
        assert "Album 2: 15 music files, 1 subdirs" in result

    def test_format_subdirectories_truncated(self, classifier):
        """Test formatting of large subdirectories list gets truncated."""
        subdirs = []
        for i in range(15):  # More than 10 to test truncation
            subdirs.append({
                "name": f"Album {i}",
                "music_files": 10 + i,
                "subdirectories": []
            })

        result = classifier._format_subdirectories(subdirs)
        
        assert "Album 0: 10 music files, 0 subdirs" in result
        assert "Album 9: 19 music files, 0 subdirs" in result
        assert "... and 5 more subdirectories" in result

    def test_build_classification_prompt(self, classifier):
        """Test building classification prompt."""
        structure = {
            "folder_name": "Test Album",
            "total_music_files": 20,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "CD1", "music_files": 10, "subdirectories": []},
                {"name": "CD2", "music_files": 10, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Test Album\n├── CD1\n└── CD2"
        }

        prompt = classifier._build_classification_prompt(structure)
        
        assert "Test Album" in prompt
        assert "20" in prompt  # total music files
        assert "0" in prompt   # direct music files
        assert "2" in prompt   # number of subdirectories
        assert "CD1: 10 music files, 0 subdirs" in prompt
        assert "CD2: 10 music files, 0 subdirs" in prompt
        assert "single_album" in prompt
        assert "multi_disc_album" in prompt
        assert "artist_collection" in prompt 