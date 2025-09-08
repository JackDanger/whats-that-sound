"""Proposal generation for music organization."""

import json
import re
from typing import Dict, Optional
from src.inference import InferenceProvider
from rich.console import Console

console = Console()


class ProposalGenerator:
    """Generates organization proposals using LLM."""

    def __init__(self, inference: InferenceProvider):
        """Initialize the proposal generator with a unified inference interface."""
        self.inference = inference

    def get_llm_proposal(
        self,
        metadata: Dict,
        user_feedback: Optional[str] = None,
        artist_hint: Optional[str] = None,
    ) -> Dict:
        """Get organization proposal from the LLM.

        Args:
            metadata: Folder metadata from DirectoryAnalyzer
            user_feedback: Optional user feedback for reconsideration
            artist_hint: Optional artist hint for collections

        Returns:
            Dictionary containing the proposal
        """
        console.print("\n[cyan]Consulting AI for organization proposal...[/cyan]")

        # Build prompt
        prompt = self._build_prompt(metadata, user_feedback, artist_hint)
        print(prompt)

        # Get LLM response
        try:
            # Parse response
            text = self.inference.generate(prompt).strip()
            print(text)

            # Try to extract JSON
            proposal = self._parse_llm_response(text)

            # If JSON parsing succeeded, return the proposal
            if proposal:
                return proposal

            # If JSON parsing failed, use fallback logic
            console.print("[yellow]Falling back to metadata-based proposal[/yellow]")
            return self._fallback_proposal(metadata, artist_hint)

        except Exception as e:
            print(e)
            console.print(f"[red]Error getting LLM proposal: {e}[/red]")
            # Return a basic proposal based on metadata analysis
            return self._fallback_proposal(metadata, artist_hint)

    def _build_prompt(
        self,
        metadata: Dict,
        user_feedback: Optional[str] = None,
        artist_hint: Optional[str] = None,
    ) -> str:
        """Build prompt for the LLM.

        Args:
            metadata: Folder metadata
            user_feedback: Optional user feedback
            artist_hint: Optional artist hint

        Returns:
            Formatted prompt string
        """
        analysis = metadata.get("analysis", {})

        prompt = """You are a music organization expert. Analyze the following music folder and suggest how to organize it.

IMPORTANT: Use the detected metadata below as your PRIMARY source of information.

Folder Information:
- Folder Name: {folder_name}
- Total Files: {total_files}
- **DETECTED ARTIST: {detected_artist}** ← USE THIS
- **DETECTED ALBUM: {detected_album}** ← USE THIS  
- **DETECTED YEAR: {detected_year}** ← USE THIS
- Is Compilation: {is_compilation}
- Track Pattern: {track_pattern}
{artist_hint_section}

Sample Files (showing consistent artist/title pattern):
{file_samples}

{user_feedback_section}

INSTRUCTIONS: 
- PRIORITIZE the detected artist, album, and year shown above
- The sample files confirm the artist pattern
- Only deviate from detected metadata if there's a clear error

Based on this information, provide a JSON response with your best guess for:
1. artist - Use the DETECTED ARTIST unless clearly wrong
2. album - Use the DETECTED ALBUM unless clearly wrong  
3. year - Use the DETECTED YEAR unless clearly wrong
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
            artist_hint_section = f"\n- **ARTIST HINT: {artist_hint}** ← This folder is part of an artist collection, USE THIS ARTIST NAME"

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
        """Parse LLM response to extract proposal.

        Args:
            text: Raw LLM response text

        Returns:
            Dictionary containing the parsed proposal
        """
        try:
            # Find JSON in response - fix the regex to capture complete JSON
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                proposal = json.loads(json_str)

                # Validate required fields
                required = ["artist", "album", "year", "release_type"]
                if all(field in proposal for field in required):
                    return proposal
        except Exception as e:
            console.print(f"[red]JSON parsing failed: {e}[/red]")
            console.print(f"[dim]Raw LLM response: {text[:100]}...[/dim]")

        # If parsing fails, return None so caller can handle fallback
        return None

    def _fallback_proposal(
        self, metadata: Dict, artist_hint: Optional[str] = None
    ) -> Dict:
        """Create a fallback proposal when LLM fails.

        Args:
            metadata: Folder metadata
            artist_hint: Optional artist hint

        Returns:
            Dictionary containing fallback proposal
        """
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
