"""Tests for the StructureClassifier class."""

import pytest
from pathlib import Path
from src.analyzers.directory_analyzer import DirectoryAnalyzer
from src.analyzers.structure_classifier import StructureClassifier
from src.inference import build_provider_from_env


def _fixture_path(*parts: str) -> Path:
    base = Path(__file__).resolve().parent.parent / "fixtures" / "src_dir"
    return base.joinpath(*parts)


class TestStructureClassifier:

    @pytest.fixture
    def classifier(self):
        # Use the real inference provider configured via WTS_INFERENCE_URL/WTS_MODEL
        provider = build_provider_from_env()
        return StructureClassifier(provider)


    def test_weezers_raditude_is_single_album_from_fs(self, classifier: StructureClassifier):
        analyzer = DirectoryAnalyzer()
        root = _fixture_path("Weezer", "2009 - Raditude")
        analysis = analyzer.analyze_directory_structure(root)
        result = classifier.classify_directory_structure(analysis)
        assert result == "multi_disc_album"


    def test_acdc_is_artist_collection_from_fs(self, classifier: StructureClassifier):
        analyzer = DirectoryAnalyzer()
        root = _fixture_path("AC-DC")
        analysis = analyzer.analyze_directory_structure(root)
        result = classifier.classify_directory_structure(analysis)
        assert result == "artist_collection"


    def test_toplevel_is_undefined_from_fs(self, classifier: StructureClassifier):
        analyzer = DirectoryAnalyzer()
        root = _fixture_path()
        analysis = analyzer.analyze_directory_structure(root)
        result = classifier.classify_directory_structure(analysis)
        assert result == "undefined"


    def test_classify_directory_structure_with_llm_success(self, classifier: StructureClassifier):
        structure = {
            "folder_name": "Test Album",
            "total_music_files": 20,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "Disc 1", "music_files": 10, "subdirectories": []},
                {"name": "Disc 2", "music_files": 10, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Test tree",
        }

        classification = classifier.classify_directory_structure(structure)

        assert classification == "multi_disc_album"

    def test_classify_directory_structure_with_llm_invalid_response(
        self, classifier: StructureClassifier
    ):

        structure = {
            "folder_name": "Test Album",
            "total_music_files": 10,
            "direct_music_files": 10,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Test tree",
        }

        classification = classifier.classify_directory_structure(structure)

        assert classification == "single_album"

    def test_classify_directory_structure_with_llm_error(self, classifier: StructureClassifier):

        structure = {
            "folder_name": "Test Album",
            "total_music_files": 10,
            "direct_music_files": 10,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "Test tree",
        }

        classification = classifier.classify_directory_structure(structure)

        assert classification == "single_album"

    def test_heuristic_classification_single_album(self, classifier: StructureClassifier):
        structure = {
            "subdirectories": [],
            "direct_music_files": 10,
        }

        classification = classifier._heuristic_classification(structure)
        assert classification == "single_album"

    def test_heuristic_classification_multi_disc_album(self, classifier: StructureClassifier):
        structure = {
            "subdirectories": [
                {"name": "CD1", "music_files": 12, "subdirectories": []},
                {"name": "CD2", "music_files": 8, "subdirectories": []},
            ],
            "direct_music_files": 0,
        }

        classification = classifier._heuristic_classification(structure)
        assert classification == "multi_disc_album"

    def test_heuristic_classification_artist_collection(self, classifier: StructureClassifier):
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

    def test_heuristic_classification_mixed_disc_patterns(self, classifier: StructureClassifier):
        structure = {
            "subdirectories": [
                {"name": "Volume 1", "music_files": 12, "subdirectories": []},
                {"name": "Random Folder", "music_files": 8, "subdirectories": []},
                {"name": "Disc 2", "music_files": 10, "subdirectories": []},
            ],
            "direct_music_files": 0,
        }

        classification = classifier._heuristic_classification(structure)
        assert classification == "multi_disc_album"

    def test_heuristic_classification_with_direct_files_and_subdirs(self, classifier: StructureClassifier):
        structure = {
            "subdirectories": [
                {"name": "Bonus Tracks", "music_files": 3, "subdirectories": []},
            ],
            "direct_music_files": 12,
        }

        classification = classifier._heuristic_classification(structure)
        assert classification == "single_album"

    def test_format_subdirectories_empty(self, classifier: StructureClassifier):
        result = classifier._format_subdirectories([])
        assert result == "None"

    def test_format_subdirectories_normal(self, classifier: StructureClassifier):
        subdirs = [
            {"name": "Album 1", "music_files": 10, "subdirectories": []},
            {"name": "Album 2", "music_files": 15, "subdirectories": ["Bonus"]},
        ]

        result = classifier._format_subdirectories(subdirs)

        assert "Album 1: 10 music files, 0 subdirs" in result
        assert "Album 2: 15 music files, 1 subdirs" in result

    def test_format_subdirectories_truncated(self, classifier: StructureClassifier):
        subdirs = []
        for i in range(15):  # More than 10 to test truncation
            subdirs.append(
                {"name": f"Album {i}", "music_files": 10 + i, "subdirectories": []}
            )

        result = classifier._format_subdirectories(subdirs)

        assert "Album 0: 10 music files, 0 subdirs" in result
        assert "Album 9: 19 music files, 0 subdirs" in result
        assert "... and 5 more subdirectories" in result

    def test_build_classification_prompt(self, classifier):
        structure = {
            "folder_name": "Test Album",
            "total_music_files": 20,
            "direct_music_files": 0,
            "subdirectories": [
                {"name": "CD1", "music_files": 10, "subdirectories": []},
                {"name": "CD2", "music_files": 10, "subdirectories": []},
            ],
            "max_depth": 1,
            "directory_tree": "Test Album\n├── CD1\n└── CD2",
        }

        prompt = classifier.build_classification_prompt(structure)

        assert "Test Album" in prompt
        assert "20" in prompt  # total music files
        assert "0" in prompt  # direct music files
        assert "2" in prompt  # number of subdirectories
        assert "CD1: 10 music files, 0 subdirs" in prompt
        assert "CD2: 10 music files, 0 subdirs" in prompt
        assert "single_album" in prompt
        assert "multi_disc_album" in prompt
        assert "artist_collection" in prompt
