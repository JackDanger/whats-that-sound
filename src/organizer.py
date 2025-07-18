"""Main music organization logic using LLMs."""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
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

        console.print(
            f"\n[bold cyan]Found {len(folders)} folders to process[/bold cyan]\n"
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
        for idx, folder in enumerate(folders, 1):
            try:
                self.ui.display_progress(idx, len(folders), folder.name)

                # Extract metadata
                console.print("\n[cyan]Analyzing folder contents...[/cyan]")
                metadata = self.metadata_extractor.extract_folder_metadata(folder)

                if metadata.get("total_files", 0) == 0:
                    console.print(
                        "[yellow]No music files found in this folder, skipping...[/yellow]"
                    )
                    stats["skipped"] += 1
                    continue

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
                        # Organize the files
                        self._organize_folder(folder, feedback["proposal"])
                        stats["successful"] += 1
                        stats["organized_albums"].append(feedback["proposal"])
                        break

                    elif feedback["action"] == "reconsider":
                        # Get new proposal with user feedback
                        proposal = self._get_llm_proposal(
                            metadata, feedback.get("feedback")
                        )

                    elif feedback["action"] == "skip":
                        console.print("[yellow]Skipping this folder...[/yellow]")
                        stats["skipped"] += 1
                        break

                    elif feedback["action"] == "cancel":
                        console.print("[red]Cancelling organization...[/red]")
                        self.ui.display_completion_summary(stats)
                        return

                stats["total_processed"] += 1
                console.print("\n" + "─" * 80 + "\n")

            except Exception as e:
                console.print(f"[red]Error processing {folder.name}: {e}[/red]")
                stats["errors"] += 1

        # Display completion summary
        self.ui.display_completion_summary(stats)

    def _get_llm_proposal(
        self, metadata: Dict, user_feedback: Optional[str] = None
    ) -> Dict:
        """Get organization proposal from the LLM."""
        console.print("\n[cyan]Consulting AI for organization proposal...[/cyan]")

        # Build prompt
        prompt = self._build_prompt(metadata, user_feedback)

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
            return self._fallback_proposal(metadata)

    def _build_prompt(self, metadata: Dict, user_feedback: Optional[str] = None) -> str:
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

    def _fallback_proposal(self, metadata: Dict) -> Dict:
        """Create a fallback proposal when LLM fails."""
        analysis = metadata.get("analysis", {})

        return {
            "artist": analysis.get(
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
