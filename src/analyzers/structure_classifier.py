"""Structure classification for music directories."""

from typing import Dict
from src.inference import InferenceProvider
from rich.console import Console

console = Console()


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
        console.print("\n[cyan]Classifying directory structure...[/cyan]")

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
            console.print(f"[red]Error classifying structure: {e}[/red]")
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

        # Single album: most/all files in root directory
        if direct_files > 0 and len(subdirs) <= 1:
            return "single_album"

        # Multi-disc album: subdirectories with names like "CD1", "Disc 1", etc.
        if len(subdirs) >= 2 and len(subdirs) <= 6:
            disc_patterns = ["cd", "disc", "disk", "volume", "vol"]
            disc_like_count = 0
            for subdir in subdirs:
                name_lower = subdir["name"].lower()
                if any(pattern in name_lower for pattern in disc_patterns):
                    disc_like_count += 1

            if disc_like_count >= len(subdirs) * 0.5:  # At least half look like discs
                return "multi_disc_album"

        # Artist collection: multiple subdirectories that don't look like discs
        if len(subdirs) >= 2:
            return "artist_collection"

        # Default to single album
        return "single_album"
