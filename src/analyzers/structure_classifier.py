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
        prompt = self.build_classification_prompt(structure_analysis)

        try:
            print(f"Prompt: {prompt}")
            classification = self.inference.generate(prompt).strip().lower()
            print(f"Classification: {classification}")

            # Validate classification
            valid_types = ["single_album", "multi_disc_album", "artist_collection"]
            if classification in valid_types:
                return classification
            else:
                # Fallback classification based on heuristics
                return self._heuristic_classification(structure_analysis)

        except Exception as e:
            print(e)
            return self._heuristic_classification(structure_analysis)

    def build_classification_prompt(self, structure_analysis: Dict) -> str:
        prompt = f"""You are a music collection organization expert. Analyze the following directory structure and classify it into one of these types:

1. "single_album" - All music files are in the root directory or it's clearly a single album
2. "multi_disc_album" - Multiple subdirectories that appear to be discs of the same album (e.g., "CD1", "CD2", "Disc 1", "Disc 2"). This includes if there are tracks at the top level and then a subdir with some bonus content.
3. "artist_collection" - Multiple subdirectories that appear to be different albums by the same artist
4. "unknown" - The structure is not clear or not enough information to classify

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

Based on this structure, classify it as exactly one of: single_album, multi_disc_album, artist_collection, or unknown

Respond with ONLY the classification (one of the four options above)."""
        return prompt

    def _format_subdirectories(self, subdirectories: list) -> str:
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
        subdirs = structure_analysis["subdirectories"]
        direct_files = structure_analysis["direct_music_files"]

        # Early case: single folder with files
        if direct_files > 0 and len(subdirs) <= 1:
            return "single_album"

        # Mixed case with some root files: compare root vs subdir distinct track names (to avoid false positives)
        if self._has_multi_disk_pattern(subdirs):
            return "multi_disc_album"

        if len(subdirs) >= 2:
            return "artist_collection"

        return "undefined"

    def _has_multi_disk_pattern(self, subdirs: list) -> bool:
        for s in subdirs:
            # "Volume 1 - good sutuff" -> "volume1goodstuff"
            name = s.get("name", "").lower().replace(" ", "")
            for pattern in ["cd1", "cd2", "disc1", "disc2", "volume1", "volume2", "part1", "part2", "vol1", "vol2", "disk1", "disk2", "set1", "set2"]:
                if pattern in name:
                    return True
        return False