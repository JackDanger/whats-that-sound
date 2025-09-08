"""Test JSON parsing fix for ProposalGenerator."""

import pytest
from unittest.mock import Mock

from src.generators.proposal_generator import ProposalGenerator


class TestJsonParsingFix:
    """Test that JSON parsing fix handles complex JSON responses correctly."""

    @pytest.fixture
    def mock_llm(self):
        """Deprecated: retained name but now returns a mock inference provider."""
        m = Mock()
        m.generate.return_value = "{}"
        return m

    @pytest.fixture
    def generator(self, mock_llm):
        """Create a ProposalGenerator instance."""
        return ProposalGenerator(mock_llm)

    def test_complex_json_parsing(self, generator, mock_llm):
        """Test that complex JSON with nested content is parsed correctly."""
        # Mock LLM to return complex JSON with nested quotes and special characters
        complex_json = """
        {
            "artist": "Ruby My Dear",
            "album": "La Mort Du Colibri",
            "year": "2010",
            "release_type": "Album",
            "confidence": "high",
            "reasoning": "Based on metadata analysis: folder shows 'Ruby My Dear' as artist with album 'La Mort Du Colibri' from 2010. Sample files confirm pattern 'Ruby My Dear - song title'. This matches detected metadata perfectly."
        }
        """

        mock_llm.generate.return_value = complex_json

        # Create test metadata
        metadata = {
            "folder_name": "[2010] - La Mort Du Colibri (Web, Illphabetik, ILLEP054)",
            "total_files": 4,
            "files": [
                {
                    "filename": "01. If I Give My heart.mp3",
                    "artist": "Ruby My Dear",
                    "title": "If I Give My heart",
                },
                {
                    "filename": "02. Where's The Music.mp3",
                    "artist": "Ruby My Dear",
                    "title": "Where's The Music",
                },
            ],
            "analysis": {
                "common_artist": "Ruby My Dear",
                "common_album": "La Mort Du Colibri",
                "common_year": "2010",
                "likely_compilation": False,
                "track_number_pattern": "sequential",
            },
        }

        # Test with artist hint
        proposal = generator.get_llm_proposal(metadata, artist_hint="Ruby My Dear")

        # Verify the proposal was parsed correctly
        assert proposal["artist"] == "Ruby My Dear"
        assert proposal["album"] == "La Mort Du Colibri"
        assert proposal["year"] == "2010"
        assert proposal["release_type"] == "Album"
        assert proposal["confidence"] == "high"
        assert "Ruby My Dear" in proposal["reasoning"]
        assert "La Mort Du Colibri" in proposal["reasoning"]

    def test_json_with_special_characters(self, generator, mock_llm):
        """Test JSON parsing with special characters that could break regex."""
        # Mock LLM to return JSON with special characters
        special_json = """
        {
            "artist": "Artist with \\"quotes\\" and {braces}",
            "album": "Album with } closing brace",
            "year": "2023",
            "release_type": "Album",
            "confidence": "medium",
            "reasoning": "Contains special characters: {}, \\", '"
        }
        """

        mock_llm.generate.return_value = special_json

        metadata = {
            "folder_name": "Test Album",
            "total_files": 1,
            "files": [],
            "analysis": {},
        }

        proposal = generator.get_llm_proposal(metadata)

        # Should parse correctly despite special characters
        assert proposal["artist"] == 'Artist with "quotes" and {braces}'
        assert proposal["album"] == "Album with } closing brace"
        assert proposal["year"] == "2023"

    def test_json_parsing_with_extra_text(self, generator, mock_llm):
        """Test JSON parsing when LLM returns extra text around JSON."""
        # Mock LLM to return JSON with extra text before and after
        response_with_extra = """
        Here's my analysis of the music folder:
        
        Based on the metadata, I can see this is clearly an album by Ruby My Dear.
        
        {
            "artist": "Ruby My Dear",
            "album": "La Mort Du Colibri",
            "year": "2010",
            "release_type": "Album",
            "confidence": "high",
            "reasoning": "Clear artist pattern in metadata"
        }
        
        This should be organized under the Ruby My Dear artist folder.
        """

        mock_llm.generate.return_value = response_with_extra

        metadata = {
            "folder_name": "Test Album",
            "total_files": 4,
            "files": [],
            "analysis": {
                "common_artist": "Ruby My Dear",
                "common_album": "La Mort Du Colibri",
                "common_year": "2010",
            },
        }

        proposal = generator.get_llm_proposal(metadata)

        # Should extract JSON correctly despite extra text
        assert proposal["artist"] == "Ruby My Dear"
        assert proposal["album"] == "La Mort Du Colibri"
        assert proposal["year"] == "2010"
        assert proposal["confidence"] == "high"

    def test_invalid_json_fallback_uses_metadata(self, generator, mock_llm):
        """Test that when JSON parsing fails, fallback uses detected metadata."""
        # Mock LLM to return invalid JSON
        mock_llm.generate.return_value = "This is not valid JSON at all"

        metadata = {
            "folder_name": "[2010] - La Mort Du Colibri",
            "total_files": 4,
            "files": [],
            "analysis": {
                "common_artist": "Ruby My Dear",
                "common_album": "La Mort Du Colibri",
                "common_year": "2010",
                "likely_compilation": False,
            },
        }

        # Test with artist hint
        proposal = generator.get_llm_proposal(metadata, artist_hint="Ruby My Dear")

        # Should use fallback which prioritizes artist_hint and detected metadata
        assert proposal["artist"] == "Ruby My Dear"  # From artist_hint
        assert proposal["album"] == "La Mort Du Colibri"  # From analysis
        assert proposal["year"] == "2010"  # From analysis
        assert proposal["release_type"] == "Album"  # Default since not compilation
        assert proposal["confidence"] == "low"  # Fallback confidence
        assert "LLM unavailable" in proposal["reasoning"]
