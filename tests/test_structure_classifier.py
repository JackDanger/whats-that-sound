from src.analyzers.structure_classifier import StructureClassifier


class DummyInference:
    def generate(self, prompt: str) -> str:
        # Force heuristic path by returning invalid label
        return "unknown"


def test_numeric_prefixed_subdirs_are_multi_disc():
    clf = StructureClassifier(DummyInference())
    analysis = {
        "folder_name": "2002 - Treasure Box, Complete Sessions 91-99",
        "folder_path": "/music/The Cranberries/Treasure Box",
        "total_music_files": 0,
        "direct_music_files": 0,
        "subdirectories": [
            {"name": "1 - Everybody Else Is Doing It So Why Can't We (Complete Sessions 91-93)", "path": "", "depth": 1, "music_files": 18, "music_basenames": ["01.flac","02.flac"], "subdirectories": []},
            {"name": "2 - No Need To Argue (Complete Sessions 94-95)", "path": "", "depth": 1, "music_files": 18, "music_basenames": ["03.flac","04.flac"], "subdirectories": []},
            {"name": "3 - To The Faithful Departed (Complete Sessions 96-97)", "path": "", "depth": 1, "music_files": 19, "music_basenames": ["05.flac"], "subdirectories": []},
            {"name": "4 - Bury The Hatchet (Complete Sessions 98-99)", "path": "", "depth": 1, "music_files": 19, "music_basenames": ["06.flac"], "subdirectories": []},
        ],
        "max_depth": 2,
        "directory_tree": "",
    }

    result = clf.classify_directory_structure(analysis)
    assert result == "multi_disc_album"


def test_count_based_multi_disc_vs_single_album():
    clf = StructureClassifier(DummyInference())
    # Root has more files than combined distinct in subdirs => single_album
    analysis_single = {
        "folder_name": "Album Root",
        "folder_path": "/music/Artist/Album",
        "total_music_files": 12,
        "direct_music_files": 10,
        "subdirectories": [
            {"name": "CD1", "path": "", "depth": 1, "music_files": 2, "music_basenames": ["01.flac","02.flac"], "subdirectories": []},
            {"name": "CD2", "path": "", "depth": 1, "music_files": 2, "music_basenames": ["02.flac"], "subdirectories": []},
        ],
        "max_depth": 1,
        "directory_tree": "",
    }
    assert clf.classify_directory_structure(analysis_single) == "single_album"

    # Root has no files; subdirs have distinct tracks => multi_disc_album
    analysis_multi = {
        "folder_name": "Box Set",
        "folder_path": "/music/Artist/Box",
        "total_music_files": 20,
        "direct_music_files": 0,
        "subdirectories": [
            {"name": "Disc 1", "path": "", "depth": 1, "music_files": 10, "music_basenames": ["a.flac","b.flac"], "subdirectories": []},
            {"name": "Disc 2", "path": "", "depth": 1, "music_files": 10, "music_basenames": ["c.flac","d.flac"], "subdirectories": []},
        ],
        "max_depth": 1,
        "directory_tree": "",
    }
    assert clf.classify_directory_structure(analysis_multi) == "multi_disc_album"


def test_artist_collection_many_album_subdirs():
    clf = StructureClassifier(DummyInference())
    # Simulate 'A Perfect Circle' artist folder with many album subdirs and no root files
    analysis_artist = {
        "folder_name": "A Perfect Circle",
        "folder_path": "/music/A Perfect Circle",
        "total_music_files": 0,
        "direct_music_files": 0,
        "subdirectories": [
            {"name": "2000 - Mer de noms", "path": "", "depth": 1, "music_files": 12, "music_basenames": [f"{i:02d}.flac" for i in range(1, 13)], "subdirectories": []},
            {"name": "2003 - Thirteenth Step", "path": "", "depth": 1, "music_files": 12, "music_basenames": [f"{i:02d}.flac" for i in range(1, 13)], "subdirectories": []},
            {"name": "2004 - aMOTION", "path": "", "depth": 1, "music_files": 9, "music_basenames": [f"{i:02d}.flac" for i in range(1, 10)], "subdirectories": []},
            {"name": "2004 - eMOTIVe", "path": "", "depth": 1, "music_files": 12, "music_basenames": [f"{i:02d}.flac" for i in range(1, 13)], "subdirectories": []},
            {"name": "2013 - Three Sixty", "path": "", "depth": 1, "music_files": 19, "music_basenames": [f"a{i}.flac" for i in range(1, 20)], "subdirectories": []},
            {"name": "2018 - Eat the Elephant", "path": "", "depth": 1, "music_files": 12, "music_basenames": [f"{i:02d}.flac" for i in range(1, 13)], "subdirectories": []},
        ],
        "max_depth": 1,
        "directory_tree": "",
    }
    assert clf.classify_directory_structure(analysis_artist) == "artist_collection"


