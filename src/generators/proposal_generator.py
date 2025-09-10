"""Proposal generation for music organization."""

import json
import re
from pathlib import Path
from typing import Dict, Optional
from src.inference import InferenceProvider
import re as _re
import logging
import os



class ProposalGenerator:
    """Generates organization proposals using LLM."""

    def __init__(self, inference: InferenceProvider):
        """Initialize the proposal generator with a unified inference interface."""
        self.inference = inference
        self._logger = logging.getLogger("wts.inference")
        if not self._logger.handlers:
            log_path = os.getenv("WTS_LOG_PATH", str(os.path.join(os.getcwd(), "wts_inference.log")))
            handler = logging.FileHandler(log_path, encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    def get_llm_proposal(
        self,
        metadata: Dict,
        user_feedback: Optional[str] = None,
        artist_hint: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict:
        """Get organization proposal from the LLM.

        Args:
            metadata: Folder metadata from DirectoryAnalyzer
            user_feedback: Optional user feedback for reconsideration
            artist_hint: Optional artist hint for collections

        Returns:
            Dictionary containing the proposal
        """
        # Quiet terminal; logs capture details

        # Build prompt (folder_path optional for backward compatibility)
        prompt = self._build_prompt(metadata, user_feedback, artist_hint, folder_path)
        self._logger.debug("PROMPT BEGIN\n%s\nPROMPT END", prompt)

        # Get LLM response
        try:
            # Parse response
            text = self.inference.generate(prompt).strip()
            self._logger.debug("RESPONSE BEGIN\n%s\nRESPONSE END", text)

            # Try to extract JSON
            proposal = self._parse_llm_response(text)

            # If JSON parsing succeeded, return the proposal
            if proposal:
                return proposal

            # If JSON parsing failed, use fallback logic
            console.print("[yellow]Falling back to metadata-based proposal[/yellow]")
            return self._fallback_proposal(metadata, artist_hint, folder_path)

        except Exception as e:
            self._logger.error("INFERENCE ERROR: %s", e)
            # Return a basic proposal based on metadata analysis
            return self._fallback_proposal(metadata, artist_hint, folder_path)

    def _build_prompt(
        self,
        metadata: Dict,
        user_feedback: Optional[str] = None,
        artist_hint: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> str:
        """Build prompt for the LLM.

        Args:
            metadata: Folder metadata
            user_feedback: Optional user feedback
            artist_hint: Optional artist hint

        Returns:
            Formatted prompt string
        """
        folder_name = (
            Path(folder_path).name if folder_path else metadata.get("folder_name", "Unknown")
        )
        analysis = metadata.get("analysis", {})

        # Heuristic parsing from folder name like "YYYY - Album Title"
        def _parse_from_folder(name: str):
            m = _re.match(r"^(?P<year>\d{4})\s*-\s*(?P<album>.+)$", name)
            if m:
                return m.group("album").strip(), m.group("year").strip()
            return name.strip(), None

        album_from_folder, year_from_folder = _parse_from_folder(folder_name)

        # Compose best-guess values, prioritizing explicit analysis, then folder hints
        detected_artist = artist_hint or analysis.get("common_artist") or folder_name
        detected_album = analysis.get("common_album") or album_from_folder
        detected_year = analysis.get("common_year") or year_from_folder or "Unknown"

        prompt = """You are a music organization expert. Produce exactly one JSON object with your best guess.

Detected Values:
- Folder Name: {folder_name}
- Total Files: {total_files}
- Artist (detected): {detected_artist}
- Album (detected or folder-based): {detected_album}
- Year (detected or folder-based): {detected_year}
- Compilation: {is_compilation}
- Track Numbering: {track_pattern}
{artist_hint_section}

Heuristic Hints:
- Album from folder name: {album_from_folder}
- Year from folder name: {year_from_folder}

All Files (recursive relative paths):
{all_files_listing}

User Feedback:
{user_feedback_section}

Constraints:
- Use Artist/Album/Year above unless clearly wrong.
- Choose release_type from: Album, EP, Single, Compilation, Live, Remix, Bootleg.
- Respond with ONLY JSON (no markdown fences, no commentary).

JSON schema:
{{
  "artist": "...",
  "album": "...",
  "year": "...",
  "release_type": "Album|EP|Single|Compilation|Live|Remix|Bootleg",
  "confidence": "low|medium|high",
  "reasoning": "..."
}}"""

        # Full recursive listing (relative paths)
        all_files_listing = []
        for f in metadata.get("files", []):
            rp = f.get("relative_path") or f.get("filename")
            if rp:
                all_files_listing.append(f"- {rp}")

        # Add user feedback if provided
        user_feedback_section = user_feedback or "(none)"

        # Add artist hint if provided
        artist_hint_section = ""
        if artist_hint:
            artist_hint_section = f"- Artist Hint (collection): {artist_hint}"

        return prompt.format(
            folder_name=folder_name,
            total_files=metadata.get("total_files", 0),
            detected_artist=detected_artist,
            detected_album=detected_album,
            detected_year=detected_year,
            is_compilation="Yes" if analysis.get("likely_compilation") else "No",
            track_pattern=analysis.get("track_number_pattern", "unknown"),
            album_from_folder=album_from_folder,
            year_from_folder=year_from_folder or "Unknown",
            all_files_listing="\n".join(all_files_listing) or "(none)",
            user_feedback_section=user_feedback_section,
            artist_hint_section=("\n" + artist_hint_section) if artist_hint_section else "",
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
            # Quiet terminal; log details
            try:
                self._logger.warning("JSON PARSE ERROR: %s", e)
                self._logger.debug("RAW RESPONSE SNIPPET: %s", text[:500])
            except Exception:
                pass

        # If parsing fails, return None so caller can handle fallback
        return None

    def _fallback_proposal(
        self, metadata: Dict, artist_hint: Optional[str] = None, folder_path: Optional[str] = None
    ) -> Dict:
        """Create a fallback proposal when LLM fails.

        Args:
            metadata: Folder metadata
            artist_hint: Optional artist hint

        Returns:
            Dictionary containing fallback proposal
        """
        analysis = metadata.get("analysis", {})
        folder_name = (
            Path(folder_path).name if folder_path else metadata.get("folder_name", "Unknown")
        )
        m = _re.match(r"^(?P<year>\d{4})\s*-\s*(?P<album>.+)$", folder_name)
        album_from_folder = m.group("album").strip() if m else folder_name
        year_from_folder = m.group("year").strip() if m else None

        base_context = f"Folder: {folder_path}\n"
        if artist_hint:
            base_context += f"Artist hint: {artist_hint}\n"
        self._logger.debug("CONTEXT\n%s\nEND CONTEXT", base_context)
        return {
            "artist": artist_hint
            or analysis.get(
                "common_artist", folder_name
            ),
            "album": analysis.get(
                "common_album", album_from_folder
            ),
            "year": analysis.get("common_year", year_from_folder or "Unknown"),
            "release_type": (
                "Compilation" if analysis.get("likely_compilation") else "Album"
            ),
            "confidence": "low",
            "reasoning": "Based on metadata analysis only (LLM unavailable)",
        }
