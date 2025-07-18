"""Tests for the metadata extraction module."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.metadata import MetadataExtractor


@pytest.fixture
def metadata_extractor():
    """Create a MetadataExtractor instance."""
    return MetadataExtractor()


@pytest.fixture
def mock_audio_file():
    """Create a mock audio file."""
    mock = Mock()
    mock.info.length = 180.5  # 3 minutes
    mock.info.bitrate = 320000
    mock.tags = {
        'TIT2': 'Test Song',
        'TPE1': 'Test Artist',
        'TALB': 'Test Album',
        'TDRC': '2023',
        'TRCK': '1/10',
        'TCON': 'Rock',
        'TPE2': 'Test Album Artist'
    }
    return mock


class TestMetadataExtractor:
    """Test cases for MetadataExtractor class."""
    
    def test_init(self, metadata_extractor):
        """Test initialization."""
        assert metadata_extractor.SUPPORTED_FORMATS == {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.opus', '.wav'}
        assert len(metadata_extractor.handlers) > 0
    
    def test_extract_file_metadata_not_found(self, metadata_extractor, tmp_path):
        """Test extracting metadata from non-existent file."""
        result = metadata_extractor.extract_file_metadata(tmp_path / "nonexistent.mp3")
        assert result["error"] == "File not found"
    
    def test_extract_file_metadata_unsupported_format(self, metadata_extractor, tmp_path):
        """Test extracting metadata from unsupported format."""
        test_file = tmp_path / "test.xyz"
        test_file.touch()
        
        result = metadata_extractor.extract_file_metadata(test_file)
        assert result["error"] == "Unsupported format: .xyz"
    
    @patch('mutagen.File')
    def test_extract_file_metadata_success(self, mock_mutagen, metadata_extractor, tmp_path, mock_audio_file):
        """Test successful metadata extraction."""
        mock_mutagen.return_value = mock_audio_file
        
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake mp3 data")
        
        result = metadata_extractor.extract_file_metadata(test_file)
        
        assert result['filename'] == 'test.mp3'
        assert result['format'] == 'mp3'
        assert result['duration_seconds'] == 180.5
        assert result['bitrate'] == 320000
        assert result['title'] == 'Test Song'
        assert result['artist'] == 'Test Artist'
        assert result['album'] == 'Test Album'
        assert result['date'] == '2023'
        assert result['track'] == '1/10'
        assert result['genre'] == 'Rock'
        assert result['albumartist'] == 'Test Album Artist'
    
    @patch('mutagen.File')
    def test_extract_file_metadata_no_tags(self, mock_mutagen, metadata_extractor, tmp_path):
        """Test metadata extraction when no tags are present."""
        mock_audio = Mock()
        mock_audio.info.length = 120
        mock_audio.info.bitrate = 192000
        mock_audio.tags = None
        mock_mutagen.return_value = mock_audio
        
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake mp3 data")
        
        result = metadata_extractor.extract_file_metadata(test_file)
        
        assert result['duration_seconds'] == 120
        assert result['bitrate'] == 192000
        assert 'title' not in result or result['title'] is None
    
    def test_extract_folder_metadata_not_directory(self, metadata_extractor, tmp_path):
        """Test extracting metadata from a file instead of directory."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        result = metadata_extractor.extract_folder_metadata(test_file)
        assert result["error"] == "Not a directory"
    
    @patch('mutagen.File')
    def test_extract_folder_metadata_success(self, mock_mutagen, metadata_extractor, tmp_path):
        """Test successful folder metadata extraction."""
        # Create test directory structure
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        subdir = music_dir / "CD1"
        subdir.mkdir()
        
        # Create test files
        (music_dir / "track1.mp3").write_bytes(b"fake")
        (music_dir / "track2.mp3").write_bytes(b"fake")
        (subdir / "track3.mp3").write_bytes(b"fake")
        
        # Mock mutagen responses
        mock_audio = Mock()
        mock_audio.info.length = 180
        mock_audio.tags = {'TPE1': 'Test Artist', 'TALB': 'Test Album'}
        mock_mutagen.return_value = mock_audio
        
        result = metadata_extractor.extract_folder_metadata(music_dir)
        
        assert result['folder_name'] == 'music'
        assert result['total_files'] == 3
        assert len(result['files']) == 3
        assert result['subdirectories'] == ['CD1']
        assert 'analysis' in result
    
    def test_get_tag(self, metadata_extractor):
        """Test the _get_tag helper method."""
        tags = {
            'TIT2': 'Title 1',
            'TITLE': 'Title 2',
            '\xa9nam': 'Title 3'
        }
        
        # Test finding first available tag
        result = metadata_extractor._get_tag(tags, ['TIT2', 'TITLE', '\xa9nam'])
        assert result == 'Title 1'
        
        # Test with missing first key
        result = metadata_extractor._get_tag(tags, ['MISSING', 'TITLE', '\xa9nam'])
        assert result == 'Title 2'
        
        # Test with all missing keys
        result = metadata_extractor._get_tag(tags, ['MISSING1', 'MISSING2'])
        assert result is None
    
    def test_analyze_metadata_patterns_common_artist(self, metadata_extractor):
        """Test pattern analysis for common artist."""
        files_metadata = [
            {'artist': 'Artist A', 'album': 'Album 1', 'date': '2023'},
            {'artist': 'Artist A', 'album': 'Album 1', 'date': '2023'},
            {'artist': 'Artist A', 'album': 'Album 1', 'date': '2023'},
            {'artist': 'Artist B', 'album': 'Album 1', 'date': '2023'},
        ]
        
        analysis = metadata_extractor._analyze_metadata_patterns(files_metadata)
        
        assert analysis['common_artist'] == 'Artist A'
        assert analysis['common_album'] == 'Album 1'
        assert analysis['common_year'] == '2023'
        assert not analysis['likely_compilation']
    
    def test_analyze_metadata_patterns_compilation(self, metadata_extractor):
        """Test pattern analysis for compilation detection."""
        files_metadata = [
            {'artist': f'Artist {i}'} for i in range(10)
        ]
        
        analysis = metadata_extractor._analyze_metadata_patterns(files_metadata)
        
        assert analysis['likely_compilation'] is True
        assert analysis['common_artist'] is None
    
    def test_analyze_metadata_patterns_track_numbers(self, metadata_extractor):
        """Test pattern analysis for track numbers."""
        # Sequential tracks
        files_metadata = [
            {'track': '1'},
            {'track': '2'},
            {'track': '3'},
            {'track': '4'},
        ]
        
        analysis = metadata_extractor._analyze_metadata_patterns(files_metadata)
        assert analysis['track_number_pattern'] == 'sequential'
        
        # Sparse tracks
        files_metadata = [
            {'track': '1'},
            {'track': '3'},
            {'track': '5'},
            {'track': '8'},
        ]
        
        analysis = metadata_extractor._analyze_metadata_patterns(files_metadata)
        assert analysis['track_number_pattern'] == 'sparse'
        
        # No tracks
        files_metadata = [
            {'title': 'Song 1'},
            {'title': 'Song 2'},
        ]
        
        analysis = metadata_extractor._analyze_metadata_patterns(files_metadata)
        assert analysis['track_number_pattern'] == 'unknown' 