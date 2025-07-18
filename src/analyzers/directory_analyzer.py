"""Directory analysis for music organization."""

from pathlib import Path
from typing import Dict, List

from ..metadata import MetadataExtractor


class DirectoryAnalyzer:
    """Analyzes directory structures and extracts metadata."""

    def __init__(self):
        """Initialize the directory analyzer."""
        self.metadata_extractor = MetadataExtractor()

    def analyze_directory_structure(self, folder: Path) -> Dict:
        """Analyze the directory structure and return detailed information.
        
        Args:
            folder: Path to the folder to analyze
            
        Returns:
            Dictionary containing structure analysis
        """
        analysis = {
            "folder_name": folder.name,
            "folder_path": str(folder),
            "total_music_files": 0,
            "direct_music_files": 0,
            "subdirectories": [],
            "max_depth": 0,
            "directory_tree": "",
        }

        # Build directory tree representation
        tree_lines = []
        self._build_tree_representation(folder, tree_lines, "", 0, analysis)
        analysis["directory_tree"] = "\n".join(tree_lines)

        return analysis

    def _build_tree_representation(
        self, path: Path, tree_lines: List[str], prefix: str, depth: int, analysis: Dict
    ):
        """Recursively build a tree representation of the directory structure.
        
        Args:
            path: Current path being processed
            tree_lines: List to accumulate tree lines
            prefix: Current prefix for tree formatting
            depth: Current depth in the tree
            analysis: Analysis dictionary to update
        """
        if depth > analysis["max_depth"]:
            analysis["max_depth"] = depth

        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            tree_lines.append(f"{prefix}├── [Permission Denied]")
            return

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{current_prefix}{item.name}")

            if item.is_file():
                # Check if it's a music file
                if item.suffix.lower() in MetadataExtractor.SUPPORTED_FORMATS:
                    analysis["total_music_files"] += 1
                    if depth == 0:
                        analysis["direct_music_files"] += 1
            elif item.is_dir():
                # Record subdirectory info
                subdir_info = {
                    "name": item.name,
                    "path": str(item),
                    "depth": depth + 1,
                    "music_files": 0,
                    "subdirectories": [],
                }

                # Count music files in subdirectory
                try:
                    for ext in MetadataExtractor.SUPPORTED_FORMATS:
                        subdir_info["music_files"] += len(list(item.rglob(f"*{ext}")))
                except PermissionError:
                    pass

                # Count subdirectories
                try:
                    subdir_info["subdirectories"] = [
                        d.name for d in item.iterdir() if d.is_dir()
                    ]
                except PermissionError:
                    pass

                if depth == 0:
                    analysis["subdirectories"].append(subdir_info)

                # Recursively process subdirectory (limit depth to avoid huge trees)
                if depth < 3:
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    self._build_tree_representation(
                        item, tree_lines, next_prefix, depth + 1, analysis
                    )

    def extract_folder_metadata(self, folder: Path) -> Dict:
        """Extract metadata from all music files in a folder.
        
        Args:
            folder: Path to the folder to analyze
            
        Returns:
            Dictionary containing folder metadata
        """
        return self.metadata_extractor.extract_folder_metadata(folder) 