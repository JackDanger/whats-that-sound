"""Music metadata extraction utilities."""
from pathlib import Path
from typing import Dict, List, Optional, Any
import mutagen
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis


class MetadataExtractor:
    """Extract metadata from music files."""
    
    SUPPORTED_FORMATS = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.opus', '.wav'}
    
    def __init__(self):
        """Initialize the metadata extractor."""
        self.handlers = {
            '.mp3': self._extract_mp3,
            '.flac': self._extract_flac,
            '.m4a': self._extract_mp4,
            '.mp4': self._extract_mp4,
            '.ogg': self._extract_ogg,
            '.opus': self._extract_ogg,
        }
    
    def extract_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from a single music file.
        
        Args:
            file_path: Path to the music file
            
        Returns:
            Dictionary containing metadata fields
        """
        if not file_path.exists():
            return {"error": "File not found"}
        
        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            return {"error": f"Unsupported format: {suffix}"}
        
        try:
            handler = self.handlers.get(suffix, self._extract_generic)
            metadata = handler(file_path)
            
            # Add file information
            metadata['filename'] = file_path.name
            metadata['file_size_mb'] = file_path.stat().st_size / (1024 * 1024)
            metadata['format'] = suffix[1:]  # Remove the dot
            
            return metadata
        except Exception as e:
            return {"error": str(e), "filename": file_path.name}
    
    def extract_folder_metadata(self, folder_path: Path) -> Dict[str, Any]:
        """Extract metadata from all music files in a folder.
        
        Args:
            folder_path: Path to the folder
            
        Returns:
            Dictionary containing folder info and file metadata
        """
        if not folder_path.is_dir():
            return {"error": "Not a directory"}
        
        # Get all music files recursively
        music_files = []
        for ext in self.SUPPORTED_FORMATS:
            music_files.extend(folder_path.rglob(f"*{ext}"))
        
        # Sort by path for consistent ordering
        music_files.sort()
        
        # Extract metadata from each file
        files_metadata = []
        for file_path in music_files:
            relative_path = file_path.relative_to(folder_path)
            metadata = self.extract_file_metadata(file_path)
            metadata['relative_path'] = str(relative_path)
            files_metadata.append(metadata)
        
        # Analyze common patterns
        analysis = self._analyze_metadata_patterns(files_metadata)
        
        return {
            'folder_name': folder_path.name,
            'folder_path': str(folder_path),
            'total_files': len(music_files),
            'files': files_metadata,
            'analysis': analysis,
            'subdirectories': [d.name for d in folder_path.iterdir() if d.is_dir()]
        }
    
    def _extract_generic(self, file_path: Path) -> Dict[str, Any]:
        """Generic metadata extraction using mutagen."""
        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return {"error": "Could not read file"}
            
            metadata = {
                'duration_seconds': audio.info.length if hasattr(audio.info, 'length') else None,
                'bitrate': audio.info.bitrate if hasattr(audio.info, 'bitrate') else None,
            }
            
            # Extract common tags
            if audio.tags:
                metadata.update({
                    'title': self._get_tag(audio.tags, ['TIT2', 'TITLE', '\xa9nam']),
                    'artist': self._get_tag(audio.tags, ['TPE1', 'ARTIST', '\xa9ART']),
                    'album': self._get_tag(audio.tags, ['TALB', 'ALBUM', '\xa9alb']),
                    'date': self._get_tag(audio.tags, ['TDRC', 'DATE', '\xa9day']),
                    'track': self._get_tag(audio.tags, ['TRCK', 'TRACKNUMBER', 'trkn']),
                    'genre': self._get_tag(audio.tags, ['TCON', 'GENRE', '\xa9gen']),
                    'albumartist': self._get_tag(audio.tags, ['TPE2', 'ALBUMARTIST', 'aART']),
                })
            
            return metadata
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_mp3(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from MP3 files."""
        return self._extract_generic(file_path)
    
    def _extract_flac(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from FLAC files."""
        return self._extract_generic(file_path)
    
    def _extract_mp4(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from MP4/M4A files."""
        return self._extract_generic(file_path)
    
    def _extract_ogg(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from OGG files."""
        return self._extract_generic(file_path)
    
    def _get_tag(self, tags: Any, keys: List[str]) -> Optional[str]:
        """Get the first available tag from a list of possible keys."""
        for key in keys:
            if key in tags:
                value = tags[key]
                if isinstance(value, list) and value:
                    return str(value[0])
                elif value:
                    return str(value)
        return None
    
    def _analyze_metadata_patterns(self, files_metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in the metadata to make intelligent guesses."""
        analysis = {
            'common_artist': None,
            'common_album': None,
            'common_year': None,
            'likely_compilation': False,
            'track_number_pattern': 'unknown',
            'folder_structure_hints': []
        }
        
        # Count occurrences
        artists = {}
        albums = {}
        years = {}
        
        for file_meta in files_metadata:
            if 'error' not in file_meta:
                artist = file_meta.get('artist')
                album = file_meta.get('album')
                year = file_meta.get('date')
                
                if artist:
                    artists[artist] = artists.get(artist, 0) + 1
                if album:
                    albums[album] = albums.get(album, 0) + 1
                if year:
                    # Extract just the year
                    year_str = str(year)[:4]
                    if year_str.isdigit():
                        years[year_str] = years.get(year_str, 0) + 1
        
        # Find most common values
        if artists:
            most_common_artist = max(artists.items(), key=lambda x: x[1])
            if most_common_artist[1] > len(files_metadata) * 0.7:
                analysis['common_artist'] = most_common_artist[0]
            elif len(set(artists.keys())) > 5:
                analysis['likely_compilation'] = True
        
        if albums:
            most_common_album = max(albums.items(), key=lambda x: x[1])
            if most_common_album[1] > len(files_metadata) * 0.7:
                analysis['common_album'] = most_common_album[0]
        
        if years:
            most_common_year = max(years.items(), key=lambda x: x[1])
            if most_common_year[1] > len(files_metadata) * 0.5:
                analysis['common_year'] = most_common_year[0]
        
        # Analyze track numbering
        track_numbers = []
        for file_meta in files_metadata:
            if 'track' in file_meta and file_meta['track']:
                try:
                    # Handle "1/12" format
                    track_str = str(file_meta['track']).split('/')[0]
                    track_num = int(track_str)
                    track_numbers.append(track_num)
                except (ValueError, AttributeError):
                    pass
        
        if track_numbers:
            track_numbers.sort()
            if track_numbers == list(range(1, len(track_numbers) + 1)):
                analysis['track_number_pattern'] = 'sequential'
            elif all(t > 0 for t in track_numbers):
                analysis['track_number_pattern'] = 'sparse'
        
        return analysis 