"""Terminal UI components for interactive music organization."""

from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import radiolist_dialog
import json


console = Console()


class InteractiveUI:
    """Interactive terminal UI for music organization."""

    def __init__(self):
        """Initialize the UI."""
        self.console = console
        self._live: Optional[Live] = None

    def display_folder_info(self, metadata: Dict):
        """Display information about a folder being processed."""
        # Create main panel
        folder_name = metadata.get("folder_name", "Unknown")
        total_files = metadata.get("total_files", 0)

        # Create a table for folder overview
        table = Table(
            title=f"📁 {folder_name}", show_header=True, header_style="bold cyan"
        )
        table.add_column("Property", style="dim", width=20)
        table.add_column("Value", style="white")

        table.add_row("Total Music Files", str(total_files))
        subdirs = metadata.get("subdirectories", [])
        table.add_row("Subdirectories", str(len(subdirs)))

        # Add analysis info
        analysis = metadata.get("analysis", {})
        if analysis.get("common_artist"):
            table.add_row("Detected Artist", analysis["common_artist"])
        if analysis.get("common_album"):
            table.add_row("Detected Album", analysis["common_album"])
        if analysis.get("common_year"):
            table.add_row("Detected Year", analysis["common_year"])

        table.add_row("Track Pattern", analysis.get("track_number_pattern", "unknown"))
        table.add_row(
            "Compilation", "Yes" if analysis.get("likely_compilation") else "No"
        )

        self.console.print(table)

    def display_structure_analysis(self, structure: Dict):
        """Display directory structure analysis."""
        # Create structure overview table
        table = Table(
            title=f"📂 Directory Structure: {structure['folder_name']}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Property", style="dim", width=25)
        table.add_column("Value", style="white")

        table.add_row("Total Music Files", str(structure["total_music_files"]))
        table.add_row("Direct Music Files", str(structure["direct_music_files"]))
        table.add_row("Subdirectories", str(len(structure["subdirectories"])))
        table.add_row("Max Depth", str(structure["max_depth"]))

        self.console.print(table)

        # Display subdirectory details if any (limit for brevity)
        if structure["subdirectories"]:
            subdir_table = Table(
                title="📁 Subdirectories", show_header=True, header_style="bold blue"
            )
            subdir_table.add_column("Name", style="white")
            subdir_table.add_column("Music Files", style="green")
            subdir_table.add_column("Subdirs", style="yellow")

            for subdir in structure["subdirectories"][:5]:  # Show first 5
                subdir_table.add_row(
                    subdir["name"],
                    str(subdir["music_files"]),
                    str(len(subdir["subdirectories"])),
                )

            if len(structure["subdirectories"]) > 5:
                subdir_table.add_row(
                    f"... {len(structure['subdirectories']) - 5} more",
                    "-",
                    "-",
                    style="dim",
                )

            self.console.print(subdir_table)

        # Display directory tree (truncated if too long)
        tree_lines = structure["directory_tree"].split("\n")
        if len(tree_lines) > 20:
            tree_preview = "\n".join(tree_lines[:20]) + "\n... (truncated)"
        else:
            tree_preview = structure["directory_tree"]

        if tree_preview:
            tree_panel = Panel(
                tree_preview,
                title="🌳 Directory Tree",
                border_style="green",
                expand=False,
            )
            self.console.print(tree_panel)

    def display_file_samples(self, files_metadata: List[Dict], max_files: int = 5):
        """Display a sample of files from the folder."""
        self.console.print("[bold cyan]Files:[/bold cyan]")

        # Show first few files
        for i, file_meta in enumerate(files_metadata[:max_files]):
            if "error" in file_meta:
                self.console.print(
                    f"  ❌ {file_meta.get('filename', 'Unknown')} - Error: {file_meta['error']}"
                )
            else:
                path = file_meta.get(
                    "relative_path", file_meta.get("filename", "Unknown")
                )
                artist = file_meta.get("artist", "Unknown Artist")
                title = file_meta.get("title", "Unknown Title")
                self.console.print(f"  🎵 {path} — {artist} - {title}")

        if len(files_metadata) > max_files:
            self.console.print(
                f"  ... and {len(files_metadata) - max_files} more files"
            )

    def display_llm_proposal(self, proposal: Dict):
        """Display the LLM's proposal for organization."""
        summary = (
            f"{proposal.get('artist', 'Unknown')} — {proposal.get('album', 'Unknown')}"
            f" ({proposal.get('year', 'Unknown')})"
            f" [{proposal.get('release_type', 'Album')}]"
        )
        panel = Panel(summary, title="🤖 AI Proposal", border_style="yellow")
        self.console.print(panel)

        if proposal.get("confidence"):
            self.console.print(f"Confidence: {proposal['confidence']}", style="dim")

        if proposal.get("reasoning"):
            reasoning_text = proposal["reasoning"]
            if len(reasoning_text) > 200:
                reasoning_text = reasoning_text[:200] + "…"
            self.console.print(f"[dim]Reasoning:[/dim] {reasoning_text}", style="dim italic")

    def get_user_feedback(self, proposal: Dict) -> Dict:
        """Get user feedback on the proposal with rich interaction."""
        self.console.print(
            "[bold cyan]Options:[/bold cyan] "
            "[1] Accept | [2] Edit | [3] Reconsider | [4] Skip | [5] Cancel"
        )

        choice = Prompt.ask(
            "\n[bold]Your choice[/bold]", choices=["1", "2", "3", "4", "5"], default="1"
        )

        if choice == "1":
            return {"action": "accept", "proposal": proposal}
        elif choice == "2":
            return self._edit_proposal(proposal)
        elif choice == "3":
            feedback = Prompt.ask("\n[yellow]What should the AI reconsider?[/yellow]")
            return {"action": "reconsider", "feedback": feedback}
        elif choice == "4":
            return {"action": "skip"}
        elif choice == "5":
            return {"action": "cancel"}

    def _edit_proposal(self, proposal: Dict) -> Dict:
        """Allow user to edit the proposal."""
        self.console.print("\n[bold cyan]Edit Proposal[/bold cyan]")
        self.console.print("[dim]Press Enter to keep current value[/dim]\n")

        edited = proposal.copy()

        edited["artist"] = Prompt.ask(
            f"Artist [{proposal.get('artist', '')}]", default=proposal.get("artist", "")
        )

        edited["album"] = Prompt.ask(
            f"Album [{proposal.get('album', '')}]", default=proposal.get("album", "")
        )

        edited["year"] = Prompt.ask(
            f"Year [{proposal.get('year', '')}]", default=str(proposal.get("year", ""))
        )

        # Release type selection
        release_types = [
            "Album",
            "EP",
            "Single",
            "Compilation",
            "Live",
            "Remix",
            "Bootleg",
        ]
        current_type = proposal.get("release_type", "Album")

        self.console.print(f"\nRelease Type (current: {current_type})")
        for i, rt in enumerate(release_types, 1):
            marker = "→" if rt == current_type else " "
            self.console.print(f"  {marker} [{i}] {rt}")

        type_choice = Prompt.ask(
            "Select release type",
            choices=[str(i) for i in range(1, len(release_types) + 1)],
            default=(
                str(release_types.index(current_type) + 1)
                if current_type in release_types
                else "1"
            ),
        )

        edited["release_type"] = release_types[int(type_choice) - 1]

        return {"action": "accept", "proposal": edited}

    def display_progress(self, current: int, total: int, current_folder: str):
        """Display overall progress."""
        progress_text = (
            f"[bold green]Progress:[/bold green] {current}/{total} folders processed"
        )
        current_text = f"[yellow]Current:[/yellow] {current_folder}"

        panel = Panel(
            f"{progress_text}\n{current_text}",
            title="🎵 Music Organization Progress",
            border_style="green",
        )
        self.console.print(panel)

    # --- New Presentation UI helpers ---
    def start_live(self):
        if self._live is None:
            self._live = Live(auto_refresh=True, console=self.console, refresh_per_second=4)
            self._live.start()

    def stop_live(self):
        if self._live is not None:
            self._live.stop()
            self._live = None

    def render_dashboard(
        self,
        source_dir: str,
        target_dir: str,
        queued: int,
        running: int,
        ready: int,
        failed: int,
        processed: int,
        total: int,
        deciding_now: Optional[str],
        ready_examples: Optional[list[str]] = None,
    ):
        # Layout: top summary, background status right, details center
        summary = Panel(
            f"Source: [cyan]{source_dir}[/cyan]\nTarget: [cyan]{target_dir}[/cyan]",
            title="Paths",
            border_style="blue",
        )

        bg_lines = [
            f"Queue: {queued}",
            f"Running: {running}",
            f"Ready: {ready}",
            f"Failed: {failed}",
            f"Processed: {processed}/{total}",
        ]
        if ready_examples:
            for name in ready_examples[:3]:
                bg_lines.append(f"Ready: {name}")
        background = Panel("\n".join(bg_lines), title="Background", border_style="dim")

        current = Panel(
            f"{deciding_now or '(waiting for a ready proposal...)'}",
            title="Current",
            border_style="green",
        )

        layout = Layout()
        layout.split_row(
            Layout(summary, name="left", ratio=2),
            Layout(current, name="center", ratio=3),
            Layout(background, name="right", ratio=2),
        )

        if self._live is not None:
            self._live.update(layout)
        else:
            self.console.print(layout)

    def display_completion_summary(self, summary: Dict):
        """Display a summary when organization is complete."""
        table = Table(
            title="✨ Organization Complete!",
            show_header=True,
            header_style="bold green",
        )
        table.add_column("Metric", style="dim", width=30)
        table.add_column("Value", style="white")

        table.add_row("Total Folders Processed", str(summary.get("total_processed", 0)))
        table.add_row("Successfully Organized", str(summary.get("successful", 0)))
        table.add_row("Skipped", str(summary.get("skipped", 0)))
        table.add_row("Errors", str(summary.get("errors", 0)))

        self.console.print(table)

        if summary.get("organized_albums"):
            self.console.print("\n[bold cyan]Organized Albums:[/bold cyan]")
            for album in summary["organized_albums"][:10]:
                artist = album.get("artist", "Unknown Artist")
                album_name = album.get("album", "Unknown Album")
                year = album.get("year", "Unknown Year")
                self.console.print(f"  ✓ {artist} - {album_name} ({year})")

            if len(summary["organized_albums"]) > 10:
                self.console.print(
                    f"  ... and {len(summary['organized_albums']) - 10} more"
                )

    def confirm_action(self, message: str) -> bool:
        """Get confirmation for an action."""
        return Confirm.ask(message, default=True)
