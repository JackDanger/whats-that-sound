"""Terminal UI components for interactive music organization."""
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
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
    
    def display_folder_info(self, metadata: Dict):
        """Display information about a folder being processed."""
        # Create main panel
        folder_name = metadata.get('folder_name', 'Unknown')
        total_files = metadata.get('total_files', 0)
        
        # Create a table for folder overview
        table = Table(title=f"📁 {folder_name}", show_header=True, header_style="bold cyan")
        table.add_column("Property", style="dim", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("Total Music Files", str(total_files))
        table.add_row("Subdirectories", ", ".join(metadata.get('subdirectories', [])) or "None")
        
        # Add analysis info
        analysis = metadata.get('analysis', {})
        if analysis.get('common_artist'):
            table.add_row("Detected Artist", analysis['common_artist'])
        if analysis.get('common_album'):
            table.add_row("Detected Album", analysis['common_album'])
        if analysis.get('common_year'):
            table.add_row("Detected Year", analysis['common_year'])
        
        table.add_row("Track Pattern", analysis.get('track_number_pattern', 'unknown'))
        table.add_row("Compilation", "Yes" if analysis.get('likely_compilation') else "No")
        
        self.console.print(table)
    
    def display_file_samples(self, files_metadata: List[Dict], max_files: int = 5):
        """Display a sample of files from the folder."""
        self.console.print("\n[bold cyan]Sample Files:[/bold cyan]")
        
        # Show first few files
        for i, file_meta in enumerate(files_metadata[:max_files]):
            if 'error' in file_meta:
                self.console.print(f"  ❌ {file_meta.get('filename', 'Unknown')} - Error: {file_meta['error']}")
            else:
                path = file_meta.get('relative_path', file_meta.get('filename', 'Unknown'))
                artist = file_meta.get('artist', 'Unknown Artist')
                title = file_meta.get('title', 'Unknown Title')
                self.console.print(f"  🎵 {path}")
                self.console.print(f"     → {artist} - {title}", style="dim")
        
        if len(files_metadata) > max_files:
            self.console.print(f"  ... and {len(files_metadata) - max_files} more files\n")
    
    def display_llm_proposal(self, proposal: Dict):
        """Display the LLM's proposal for organization."""
        panel = Panel(
            f"[bold yellow]Artist:[/bold yellow] {proposal.get('artist', 'Unknown')}\n"
            f"[bold yellow]Album:[/bold yellow] {proposal.get('album', 'Unknown')}\n"
            f"[bold yellow]Year:[/bold yellow] {proposal.get('year', 'Unknown')}\n"
            f"[bold yellow]Release Type:[/bold yellow] {proposal.get('release_type', 'Album')}",
            title="🤖 AI Proposal",
            border_style="yellow"
        )
        self.console.print(panel)
        
        if proposal.get('confidence'):
            self.console.print(f"Confidence: {proposal['confidence']}", style="dim")
        
        if proposal.get('reasoning'):
            self.console.print("\n[dim]Reasoning:[/dim]")
            self.console.print(proposal['reasoning'], style="dim italic")
    
    def get_user_feedback(self, proposal: Dict) -> Dict:
        """Get user feedback on the proposal with rich interaction."""
        self.console.print("\n[bold cyan]Options:[/bold cyan]")
        self.console.print("  [1] ✅ Accept this proposal")
        self.console.print("  [2] ✏️  Edit the proposal")
        self.console.print("  [3] 🔄 Ask AI to reconsider")
        self.console.print("  [4] ⏭️  Skip this folder")
        self.console.print("  [5] ❌ Cancel organization")
        
        choice = Prompt.ask(
            "\n[bold]Your choice[/bold]",
            choices=["1", "2", "3", "4", "5"],
            default="1"
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
        
        edited['artist'] = Prompt.ask(
            f"Artist [{proposal.get('artist', '')}]",
            default=proposal.get('artist', '')
        )
        
        edited['album'] = Prompt.ask(
            f"Album [{proposal.get('album', '')}]",
            default=proposal.get('album', '')
        )
        
        edited['year'] = Prompt.ask(
            f"Year [{proposal.get('year', '')}]",
            default=str(proposal.get('year', ''))
        )
        
        # Release type selection
        release_types = ["Album", "EP", "Single", "Compilation", "Live", "Remix", "Bootleg"]
        current_type = proposal.get('release_type', 'Album')
        
        self.console.print(f"\nRelease Type (current: {current_type})")
        for i, rt in enumerate(release_types, 1):
            marker = "→" if rt == current_type else " "
            self.console.print(f"  {marker} [{i}] {rt}")
        
        type_choice = Prompt.ask(
            "Select release type",
            choices=[str(i) for i in range(1, len(release_types) + 1)],
            default=str(release_types.index(current_type) + 1) if current_type in release_types else "1"
        )
        
        edited['release_type'] = release_types[int(type_choice) - 1]
        
        return {"action": "accept", "proposal": edited}
    
    def display_progress(self, current: int, total: int, current_folder: str):
        """Display overall progress."""
        progress_text = f"[bold green]Progress:[/bold green] {current}/{total} folders processed"
        current_text = f"[yellow]Current:[/yellow] {current_folder}"
        
        panel = Panel(
            f"{progress_text}\n{current_text}",
            title="🎵 Music Organization Progress",
            border_style="green"
        )
        self.console.print(panel)
    
    def display_completion_summary(self, summary: Dict):
        """Display a summary when organization is complete."""
        table = Table(title="✨ Organization Complete!", show_header=True, header_style="bold green")
        table.add_column("Metric", style="dim", width=30)
        table.add_column("Value", style="white")
        
        table.add_row("Total Folders Processed", str(summary.get('total_processed', 0)))
        table.add_row("Successfully Organized", str(summary.get('successful', 0)))
        table.add_row("Skipped", str(summary.get('skipped', 0)))
        table.add_row("Errors", str(summary.get('errors', 0)))
        
        self.console.print("\n")
        self.console.print(table)
        
        if summary.get('organized_albums'):
            self.console.print("\n[bold cyan]Organized Albums:[/bold cyan]")
            for album in summary['organized_albums'][:10]:
                self.console.print(f"  ✓ {album['artist']} - {album['album']} ({album['year']})")
            
            if len(summary['organized_albums']) > 10:
                self.console.print(f"  ... and {len(summary['organized_albums']) - 10} more")
    
    def confirm_action(self, message: str) -> bool:
        """Get confirmation for an action."""
        return Confirm.ask(message, default=True) 