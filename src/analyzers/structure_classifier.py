"""Structure classification for music directories."""

from typing import Dict
import re
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

        # Name-agnostic, count-based logic:
        # If combined distinct audio filenames across immediate subdirs exceeds the number of direct files,
        # treat as multi-disc. If root has no files and there are at least two subdirs with any audio, also treat as multi-disc.
        subdir_distinct_names = set()
        subdir_any_files = 0
        for s in subdirs:
            mf = int(s.get("music_files", 0) or 0)
            if mf > 0:
                subdir_any_files += 1
            for bn in (s.get("music_basenames", []) or []):
                subdir_distinct_names.add(str(bn).lower())
        combined_distinct = len(subdir_distinct_names)

        # Prefer multi-disc when subdir distinct tracks dominate direct root files
        if len(subdirs) >= 2 and combined_distinct > direct_files:
            return "multi_disc_album"

        # No root files but multiple subdirs with audio: multi-disc
        if direct_files == 0 and subdir_any_files >= 2:
            return "multi_disc_album"

        # Otherwise: artist collection if multiple subdirs, else single album
        if len(subdirs) >= 2:
            return "artist_collection"

        return "single_album"
