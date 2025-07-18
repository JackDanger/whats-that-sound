"""Main music organization logic using LLMs."""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from llama_cpp import Llama
from rich.console import Console

from .metadata import MetadataExtractor
from .ui import InteractiveUI


console = Console()


class MusicOrganizer:
    """Organize music collections using local LLMs."""

    def __init__(self, model_path: Path, source_dir: Path, target_dir: Path):
        """Initialize the music organizer.

        Args:
            model_path: Path to the GGUF model file
            source_dir: Source directory with unorganized music
            target_dir: Target directory for organized music
        """
        self.model_path = model_path
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.metadata_extractor = MetadataExtractor()
        self.ui = InteractiveUI()

        # Initialize LLM
        console.print(f"[cyan]Loading model: {model_path.name}[/cyan]")
        console.print("[dim]This may take a moment...[/dim]")

        try:
            self.llm = Llama(
                model_path=str(model_path),
                n_ctx=4096,
                n_gpu_layers=-1,  # Use all GPU layers
                verbose=False,
            )
            console.print("[green]✓ Model loaded successfully![/green]")
        except Exception as e:
            console.print(f"[red]Error loading model: {e}[/red]")
            raise

    def organize(self):
        """Main organization workflow."""
        # Get all top-level folders
        folders = [d for d in self.source_dir.iterdir() if d.is_dir()]

        if not folders:
            console.print("[yellow]No folders found in source directory.[/yellow]")
            return

        # Filter out folders that have already been organized
        unorganized_folders = []
        organized_count = 0

        for folder in folders:
            tracker_file = folder / ".whats-that-sound"
            if tracker_file.exists():
                organized_count += 1
                console.print(f"[dim]Skipping {folder.name} (already organized)[/dim]")
            else:
                unorganized_folders.append(folder)

        if organized_count > 0:
            console.print(
                f"[yellow]Found {organized_count} already organized folders, skipping them.[/yellow]"
            )

        if not unorganized_folders:
            console.print("[yellow]No unorganized folders found.[/yellow]")
            return

        console.print(
            f"\n[bold cyan]Found {len(unorganized_folders)} folders to process[/bold cyan]\n"
        )

        # Process statistics
        stats = {
            "total_processed": 0,
            "successful": 0,
            "skipped": 0,
            "errors": 0,
            "organized_albums": [],
        }

        # Process each folder
        for idx, folder in enumerate(unorganized_folders, 1):
            try:
                self.ui.display_progress(idx, len(unorganized_folders), folder.name)

                # Analyze directory structure first
                console.print("\n[cyan]Analyzing directory structure...[/cyan]")
                structure_analysis = self._analyze_directory_structure(folder)

                if structure_analysis["total_music_files"] == 0:
                    console.print(
                        "[yellow]No music files found in this folder, skipping...[/yellow]"
                    )
                    stats["skipped"] += 1
                    continue

                # Display structure analysis
                self.ui.display_structure_analysis(structure_analysis)

                # Get LLM classification of the directory structure
                structure_type = self._classify_directory_structure(structure_analysis)

                console.print(f"[cyan]Detected structure type: {structure_type}[/cyan]")

                # Process based on structure type
                if structure_type == "single_album":
                    success = self._process_single_album(folder, structure_analysis)
                elif structure_type == "multi_disc_album":
                    success = self._process_multi_disc_album(folder, structure_analysis)
                elif structure_type == "artist_collection":
                    success = self._process_artist_collection(
                        folder, structure_analysis
                    )
                else:
                    console.print(
                        f"[red]Unknown structure type: {structure_type}[/red]"
                    )
                    stats["errors"] += 1
                    continue

                if success:
                    stats["successful"] += 1
                else:
                    stats["skipped"] += 1

                stats["total_processed"] += 1
                console.print("\n" + "─" * 80 + "\n")

            except Exception as e:
                console.print(f"[red]Error processing {folder.name}: {e}[/red]")
                stats["errors"] += 1

        # Display completion summary
        self.ui.display_completion_summary(stats)

    def _analyze_directory_structure(self, folder: Path) -> Dict:
        """Analyze the directory structure and return detailed information."""
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
        """Recursively build a tree representation of the directory structure."""
        if depth > analysis["max_depth"]:
            analysis["max_depth"] = depth

        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))

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
                for ext in MetadataExtractor.SUPPORTED_FORMATS:
                    subdir_info["music_files"] += len(list(item.rglob(f"*{ext}")))

                # Count subdirectories
                subdir_info["subdirectories"] = [
                    d.name for d in item.iterdir() if d.is_dir()
                ]

                if depth == 0:
                    analysis["subdirectories"].append(subdir_info)

                # Recursively process subdirectory (limit depth to avoid huge trees)
                if depth < 3:
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    self._build_tree_representation(
                        item, tree_lines, next_prefix, depth + 1, analysis
                    )

    def _classify_directory_structure(self, structure_analysis: Dict) -> str:
        """Use LLM to classify the directory structure type."""
        console.print("\n[cyan]Classifying directory structure...[/cyan]")

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

        try:
            response = self.llm(
                prompt,
                max_tokens=50,
                temperature=0.3,
                stop=["\n", " ", ".", ","],
                echo=False,
            )

            classification = response["choices"][0]["text"].strip().lower()

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

    def _format_subdirectories(self, subdirectories: List[Dict]) -> str:
        """Format subdirectory information for the prompt."""
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
        """Fallback heuristic classification when LLM fails."""
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

    def _process_single_album(self, folder: Path, structure_analysis: Dict) -> bool:
        """Process a single album directory."""
        console.print("[cyan]Processing as single album...[/cyan]")

        # Extract metadata from the entire folder
        metadata = self.metadata_extractor.extract_folder_metadata(folder)

        if metadata.get("total_files", 0) == 0:
            return False

        # Display folder info
        self.ui.display_folder_info(metadata)
        self.ui.display_file_samples(metadata.get("files", []))

        # Get LLM proposal
        proposal = self._get_llm_proposal(metadata)

        # Interactive loop for user feedback
        while True:
            self.ui.display_llm_proposal(proposal)
            feedback = self.ui.get_user_feedback(proposal)

            if feedback["action"] == "accept":
                # Save proposal to tracker file before organizing
                self._save_proposal_tracker(folder, feedback["proposal"])

                # Organize the files
                self._organize_folder(folder, feedback["proposal"])
                return True

            elif feedback["action"] == "reconsider":
                # Get new proposal with user feedback
                proposal = self._get_llm_proposal(metadata, feedback.get("feedback"))

            elif feedback["action"] == "skip":
                console.print("[yellow]Skipping this folder...[/yellow]")
                return False

            elif feedback["action"] == "cancel":
                console.print("[red]Cancelling organization...[/red]")
                return False

    def _process_multi_disc_album(self, folder: Path, structure_analysis: Dict) -> bool:
        """Process a multi-disc album directory."""
        console.print("[cyan]Processing as multi-disc album...[/cyan]")

        # Extract metadata from the entire folder (including all discs)
        metadata = self.metadata_extractor.extract_folder_metadata(folder)

        if metadata.get("total_files", 0) == 0:
            return False

        # Display folder info
        self.ui.display_folder_info(metadata)
        self.ui.display_file_samples(metadata.get("files", []))

        # Get LLM proposal
        proposal = self._get_llm_proposal(metadata)

        # Interactive loop for user feedback
        while True:
            self.ui.display_llm_proposal(proposal)
            feedback = self.ui.get_user_feedback(proposal)

            if feedback["action"] == "accept":
                # Save proposal to tracker file before organizing
                self._save_proposal_tracker(folder, feedback["proposal"])

                # Organize the files (maintaining disc structure)
                self._organize_folder(folder, feedback["proposal"])
                return True

            elif feedback["action"] == "reconsider":
                # Get new proposal with user feedback
                proposal = self._get_llm_proposal(metadata, feedback.get("feedback"))

            elif feedback["action"] == "skip":
                console.print("[yellow]Skipping this folder...[/yellow]")
                return False

            elif feedback["action"] == "cancel":
                console.print("[red]Cancelling organization...[/red]")
                return False

    def _process_artist_collection(
        self, folder: Path, structure_analysis: Dict
    ) -> bool:
        """Process an artist collection directory with multiple albums."""
        console.print("[cyan]Processing as artist collection...[/cyan]")

        # Get the artist name from the folder
        artist_name = folder.name

        # Process each album subdirectory
        successful_albums = []

        for subdir_info in structure_analysis["subdirectories"]:
            if subdir_info["music_files"] == 0:
                continue

            album_folder = Path(subdir_info["path"])
            console.print(f"\n[cyan]Processing album: {album_folder.name}[/cyan]")

            # Extract metadata for this album
            metadata = self.metadata_extractor.extract_folder_metadata(album_folder)

            if metadata.get("total_files", 0) == 0:
                continue

            # Display folder info
            self.ui.display_folder_info(metadata)
            self.ui.display_file_samples(metadata.get("files", []))

            # Get LLM proposal with artist hint
            proposal = self._get_llm_proposal(metadata, artist_hint=artist_name)

            # Interactive loop for user feedback
            while True:
                self.ui.display_llm_proposal(proposal)
                feedback = self.ui.get_user_feedback(proposal)

                if feedback["action"] == "accept":
                    # Organize this album
                    self._organize_folder(album_folder, feedback["proposal"])
                    successful_albums.append(feedback["proposal"])
                    break

                elif feedback["action"] == "reconsider":
                    # Get new proposal with user feedback
                    proposal = self._get_llm_proposal(
                        metadata, feedback.get("feedback"), artist_hint=artist_name
                    )

                elif feedback["action"] == "skip":
                    console.print(
                        f"[yellow]Skipping album: {album_folder.name}[/yellow]"
                    )
                    break

                elif feedback["action"] == "cancel":
                    console.print("[red]Cancelling organization...[/red]")
                    if successful_albums:
                        # Save tracker file for what we've processed
                        self._save_collection_tracker(folder, successful_albums)
                    return False

        if successful_albums:
            # Save tracker file for the entire collection
            self._save_collection_tracker(folder, successful_albums)
            return True

        return False

    def _save_collection_tracker(self, folder: Path, albums: List[Dict]):
        """Save tracker file for an artist collection."""
        tracker_file = folder / ".whats-that-sound"

        tracker_data = {
            "collection_type": "artist_collection",
            "folder_name": folder.name,
            "albums": albums,
            "organized_timestamp": str(Path().absolute()),
        }

        try:
            with open(tracker_file, "w", encoding="utf-8") as f:
                json.dump(tracker_data, f, indent=2, ensure_ascii=False)
            console.print(f"[dim]Saved collection record to {tracker_file.name}[/dim]")
        except Exception as e:
            console.print(f"[red]Warning: Could not save tracker file: {e}[/red]")

    def _save_proposal_tracker(self, source_folder: Path, proposal: Dict):
        """Save the accepted proposal to a tracker file in the source folder."""
        tracker_file = source_folder / ".whats-that-sound"

        tracker_data = {
            "proposal": proposal,
            "folder_name": source_folder.name,
            "organized_timestamp": str(Path().absolute()),  # Current timestamp/session
        }

        try:
            with open(tracker_file, "w", encoding="utf-8") as f:
                json.dump(tracker_data, f, indent=2, ensure_ascii=False)
            console.print(
                f"[dim]Saved organization record to {tracker_file.name}[/dim]"
            )
        except Exception as e:
            console.print(f"[red]Warning: Could not save tracker file: {e}[/red]")

    def _get_llm_proposal(
        self,
        metadata: Dict,
        user_feedback: Optional[str] = None,
        artist_hint: Optional[str] = None,
    ) -> Dict:
        """Get organization proposal from the LLM."""
        console.print("\n[cyan]Consulting AI for organization proposal...[/cyan]")

        # Build prompt
        prompt = self._build_prompt(metadata, user_feedback, artist_hint)

        # Get LLM response
        try:
            response = self.llm(
                prompt,
                max_tokens=512,
                temperature=0.7,
                stop=["```", "\n\n\n"],
                echo=False,
            )

            # Parse response
            text = response["choices"][0]["text"].strip()

            # Try to extract JSON
            proposal = self._parse_llm_response(text)

            return proposal

        except Exception as e:
            console.print(f"[red]Error getting LLM proposal: {e}[/red]")
            # Return a basic proposal based on metadata analysis
            return self._fallback_proposal(metadata, artist_hint)

    def _build_prompt(
        self,
        metadata: Dict,
        user_feedback: Optional[str] = None,
        artist_hint: Optional[str] = None,
    ) -> str:
        """Build prompt for the LLM."""
        analysis = metadata.get("analysis", {})

        prompt = """You are a music organization expert. Analyze the following music folder and suggest how to organize it.

Folder Information:
- Folder Name: {folder_name}
- Total Files: {total_files}
- Detected Artist: {detected_artist}
- Detected Album: {detected_album}
- Detected Year: {detected_year}
- Is Compilation: {is_compilation}
- Track Pattern: {track_pattern}
{artist_hint_section}

Sample Files:
{file_samples}

{user_feedback_section}

Based on this information, provide a JSON response with your best guess for:
1. artist - The primary artist name
2. album - The album title
3. year - The release year (4 digits)
4. release_type - One of: Album, EP, Single, Compilation, Live, Remix, Bootleg
5. confidence - Your confidence level (low, medium, high)
6. reasoning - Brief explanation of your decision

Response format:
```json
{{
    "artist": "Artist Name",
    "album": "Album Title",
    "year": "2023",
    "release_type": "Album",
    "confidence": "high",
    "reasoning": "Based on metadata and folder structure..."
}}
```

Provide ONLY the JSON response."""

        # Format file samples
        file_samples = []
        for f in metadata.get("files", [])[:5]:
            if "error" not in f:
                file_samples.append(
                    f"- {f.get('filename', 'Unknown')}: "
                    f"{f.get('artist', 'Unknown')} - {f.get('title', 'Unknown')}"
                )

        # Add user feedback if provided
        user_feedback_section = ""
        if user_feedback:
            user_feedback_section = f"\nUser Feedback: {user_feedback}\nPlease reconsider your proposal based on this feedback.\n"

        # Add artist hint if provided
        artist_hint_section = ""
        if artist_hint:
            artist_hint_section = f"\n- Artist Hint: {artist_hint} (this folder is part of an artist collection)"

        return prompt.format(
            folder_name=metadata.get("folder_name", "Unknown"),
            total_files=metadata.get("total_files", 0),
            detected_artist=analysis.get("common_artist", "Unknown"),
            detected_album=analysis.get("common_album", "Unknown"),
            detected_year=analysis.get("common_year", "Unknown"),
            is_compilation="Yes" if analysis.get("likely_compilation") else "No",
            track_pattern=analysis.get("track_number_pattern", "unknown"),
            file_samples="\n".join(file_samples),
            user_feedback_section=user_feedback_section,
            artist_hint_section=artist_hint_section,
        )

    def _parse_llm_response(self, text: str) -> Dict:
        """Parse LLM response to extract proposal."""
        try:
            # Find JSON in response
            import re

            json_match = re.search(r"\{[^}]+\}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                proposal = json.loads(json_str)

                # Validate required fields
                required = ["artist", "album", "year", "release_type"]
                if all(field in proposal for field in required):
                    return proposal
        except:
            pass

        # If parsing fails, extract what we can
        lines = text.split("\n")
        proposal = {
            "artist": "Unknown Artist",
            "album": "Unknown Album",
            "year": "2023",
            "release_type": "Album",
            "confidence": "low",
            "reasoning": text[:200],
        }

        # Try to extract from text
        for line in lines:
            lower_line = line.lower()
            if "artist:" in lower_line:
                proposal["artist"] = line.split(":", 1)[1].strip().strip("\"'")
            elif "album:" in lower_line:
                proposal["album"] = line.split(":", 1)[1].strip().strip("\"'")
            elif "year:" in lower_line:
                year_text = line.split(":", 1)[1].strip().strip("\"'")
                if year_text.isdigit() and len(year_text) == 4:
                    proposal["year"] = year_text

        return proposal

    def _fallback_proposal(
        self, metadata: Dict, artist_hint: Optional[str] = None
    ) -> Dict:
        """Create a fallback proposal when LLM fails."""
        analysis = metadata.get("analysis", {})

        return {
            "artist": artist_hint
            or analysis.get(
                "common_artist", metadata.get("folder_name", "Unknown Artist")
            ),
            "album": analysis.get(
                "common_album", metadata.get("folder_name", "Unknown Album")
            ),
            "year": analysis.get("common_year", "2023"),
            "release_type": (
                "Compilation" if analysis.get("likely_compilation") else "Album"
            ),
            "confidence": "low",
            "reasoning": "Based on metadata analysis only (LLM unavailable)",
        }

    def _organize_folder(self, source_folder: Path, proposal: Dict):
        """Actually organize the folder based on the accepted proposal."""
        console.print("\n[cyan]Organizing files...[/cyan]")

        # Create target directory structure
        artist = self._sanitize_filename(proposal["artist"])
        album = self._sanitize_filename(proposal["album"])
        year = proposal.get("year", "Unknown")

        # Create directory: Artist/Album (Year)
        album_dir = self.target_dir / artist / f"{album} ({year})"
        album_dir.mkdir(parents=True, exist_ok=True)

        # Copy all music files
        copied = 0
        for ext in MetadataExtractor.SUPPORTED_FORMATS:
            # Find all files with this extension
            for file_path in source_folder.rglob(f"*{ext}"):
                try:
                    # Maintain relative structure within the album folder
                    relative_path = file_path.relative_to(source_folder)
                    target_path = album_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(file_path, target_path)
                    copied += 1
                except Exception as e:
                    console.print(f"[red]Error copying {file_path.name}: {e}[/red]")

        console.print(
            f"[green]✓ Organized {copied} files to: {album_dir.relative_to(self.target_dir)}[/green]"
        )

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # Limit length
        return name[:120].strip()
