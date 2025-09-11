"""Structure classification for music directories."""

from typing import Dict
from src.inference import InferenceProvider
import logging

logger = logging.getLogger("wts.structure_classifier")

class StructureClassifier:
    """Classifies directory structures using LLM and heuristics."""

    def __init__(self, inference: InferenceProvider):
        """Initialize the structure classifier with a unified inference interface."""
        self.inference = inference

    def classify_directory_structure(self, structure_analysis: Dict) -> str:
        """Classify the directory structure type using LLM with heuristic fallback.

        Args:
            structure_analysis: Directory structure analysis from DirectoryAnalyzer

        Returns:
            One of: "single_album", "multi_disc_album", "artist_collection"
        """
        prompt = self._build_classification_prompt(structure_analysis)

        try:
            classification = self.inference.generate(prompt).strip().lower()

            # Validate classification
            valid_types = ["single_album", "multi_disc_album", "artist_collection"]
            if classification in valid_types:
                return classification
            else:
                # Fallback classification based on heuristics
                return self._heuristic_classification(structure_analysis)

        except Exception as e:
            return self._heuristic_classification(structure_analysis)

    def _build_classification_prompt(self, structure_analysis: Dict) -> str:
        """Build prompt for LLM structure classification.
        

        Args:
            structure_analysis: Directory structure analysis

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are a music collection organization expert. Analyze the following directory structure and classify it into one of these types:

1. "single_album" - All music files are in the root directory or it's clearly a single album
2. "multi_disc_album" - Multiple subdirectories that appear to be discs of the same album (e.g., "CD1", "CD2", "Disc 1", "Disc 2")
3. "artist_collection" - Multiple subdirectories that appear to be different albums by the same artist

Directory Analysis:
- Folder Name: {structure_analysis["folder_name"]}
- Total Music Files: {structure_analysis["total_music_files"]}
- Direct Music Files (in root): {structure_analysis["direct_music_files"]}
- Number of Subdirectories: {len(structure_analysis["subdirectories"])}
- Max Depth: {structure_analysis["max_depth"]}

Subdirectories:
{self._format_subdirectories(structure_analysis["subdirectories"])}

Directory Tree:
{structure_analysis["directory_tree"]}

Based on this structure, classify it as exactly one of: single_album, multi_disc_album, or artist_collection

Respond with ONLY the classification (one of the three options above)."""

        return prompt

    def _format_subdirectories(self, subdirectories: list) -> str:
        """Format subdirectory information for the prompt.

        Args:
            subdirectories: List of subdirectory info dictionaries

        Returns:
            Formatted string describing subdirectories
        """
        if not subdirectories:
            return "None"

        lines = []
        for subdir in subdirectories[:10]:  # Limit to avoid huge prompts
            lines.append(
                f"- {subdir['name']}: {subdir['music_files']} music files, "
                f"{len(subdir['subdirectories'])} subdirs"
            )

        if len(subdirectories) > 10:
            lines.append(f"... and {len(subdirectories) - 10} more subdirectories")

        return "\n".join(lines)

    def _heuristic_classification(self, structure_analysis: Dict) -> str:
        """Fallback heuristic classification when LLM fails.

        Args:
            structure_analysis: Directory structure analysis

        Returns:
            Classification string
        """
        subdirs = structure_analysis["subdirectories"]
        direct_files = structure_analysis["direct_music_files"]

        # Early case: single folder with files
        if direct_files > 0 and len(subdirs) <= 1:
            return "single_album"

        disc_patterns = ["cd", "disc", "disk", "volume", "vol"]
        disc_like = [s for s in subdirs if any(p in s["name"].lower() for p in disc_patterns)]
        other_subdirs = [s for s in subdirs if s not in disc_like]
        disc_like_count = len(disc_like)
        disc_total_files = sum(int(s.get("music_files", 0) or 0) for s in disc_like)

        # Mixed case: both root files and disc-like subfolders exist
        if direct_files > 0 and disc_like_count >= 1:
            # Pick the larger grouping: root vs combined disc subfolders
            if direct_files >= disc_total_files or disc_like_count < 2:
                return "single_album"
            # If discs clearly dominate and are majority of subdirs, treat as multi-disc
            if disc_like_count >= max(2, int(0.5 * max(1, len(subdirs)))) and disc_total_files > direct_files:
                return "multi_disc_album"
            return "single_album"

        # No root files; decide between multi-disc and artist-collection
        if disc_like_count >= max(2, int(0.5 * max(1, len(subdirs)))) and 2 <= len(subdirs) <= 8:
            return "multi_disc_album"

        if len(subdirs) >= 2:
            return "artist_collection"

        return "single_album"
