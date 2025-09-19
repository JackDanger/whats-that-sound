from pathlib import Path

from src.analyzers import DirectoryAnalyzer, StructureClassifier


class DummyInference:
    def generate(self, prompt: str) -> str:
        # Force heuristic path
        return "unknown"


def _fixture_path(*parts: str) -> Path:
    base = Path(__file__).resolve().parent / "fixtures" / "src_dir"
    return base.joinpath(*parts)


def test_cranberries_box_is_multidisc_from_fs():
    analyzer = DirectoryAnalyzer()
    clf = StructureClassifier(DummyInference())
    root = _fixture_path(
        "The Cranberries",
        "2002 - Treasure Box, Complete Sessions 91-99",
    )
    analysis = analyzer.analyze_directory_structure(root)
    result = clf.classify_directory_structure(analysis)
    assert result == "multi_disc_album"


def test_a_perfect_circle_is_artist_collection_from_fs():
    analyzer = DirectoryAnalyzer()
    clf = StructureClassifier(DummyInference())
    root = _fixture_path("A Perfect Circle")
    analysis = analyzer.analyze_directory_structure(root)
    result = clf.classify_directory_structure(analysis)
    assert result == "artist_collection"


