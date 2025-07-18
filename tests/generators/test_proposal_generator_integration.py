"""Integration tests for ProposalGenerator."""

import pytest
import json
from unittest.mock import Mock

from src.generators.proposal_generator import ProposalGenerator


class TestProposalGeneratorIntegration:
    """Test ProposalGenerator with realistic LLM interactions."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM that gives realistic responses."""
        return Mock()

    @pytest.fixture
    def generator(self, mock_llm):
        """Create a ProposalGenerator instance."""
        return ProposalGenerator(mock_llm)

    def test_successful_proposal_generation(self, generator, mock_llm):
        """Test successful proposal generation with realistic LLM response."""
        # Mock LLM to return valid JSON response
        mock_llm.return_value = {
            "choices": [{
                "text": '{"artist": "The Beatles", "album": "Abbey Road", "year": "1969", "release_type": "Album", "confidence": "high", "reasoning": "Classic Beatles album with distinctive tracks"}'
            }]
        }
        
        # Create realistic metadata
        metadata = {
            "folder_name": "The Beatles - Abbey Road (1969)",
            "total_files": 17,
            "files": [
                {"filename": "01 - Come Together.mp3", "artist": "The Beatles", "title": "Come Together"},
                {"filename": "02 - Something.mp3", "artist": "The Beatles", "title": "Something"},
                {"filename": "03 - Maxwell's Silver Hammer.mp3", "artist": "The Beatles", "title": "Maxwell's Silver Hammer"},
            ],
            "analysis": {
                "common_artist": "The Beatles",
                "common_album": "Abbey Road",
                "common_year": "1969",
                "likely_compilation": False,
                "track_number_pattern": "sequential"
            }
        }
        
        proposal = generator.get_llm_proposal(metadata)
        
        # Verify the proposal
        assert proposal["artist"] == "The Beatles"
        assert proposal["album"] == "Abbey Road"
        assert proposal["year"] == "1969"
        assert proposal["release_type"] == "Album"
        assert proposal["confidence"] == "high"
        assert "reasoning" in proposal
        
        # Verify LLM was called with proper prompt
        mock_llm.assert_called_once()
        call_args = mock_llm.call_args[0]
        prompt = call_args[0]
        
        # Check that prompt contains metadata
        assert "The Beatles - Abbey Road (1969)" in prompt
        assert "Come Together" in prompt
        assert "Something" in prompt
        assert "Maxwell's Silver Hammer" in prompt

    def test_proposal_with_artist_hint(self, generator, mock_llm):
        """Test proposal generation with artist hint."""
        mock_llm.return_value = {
            "choices": [{
                "text": '{"artist": "Led Zeppelin", "album": "Led Zeppelin IV", "year": "1971", "release_type": "Album", "confidence": "high", "reasoning": "Part of Led Zeppelin collection"}'
            }]
        }
        
        metadata = {
            "folder_name": "Led Zeppelin IV",
            "total_files": 8,
            "files": [
                {"filename": "01 - Black Dog.mp3", "artist": "Led Zeppelin", "title": "Black Dog"},
                {"filename": "02 - Rock and Roll.mp3", "artist": "Led Zeppelin", "title": "Rock and Roll"},
            ],
            "analysis": {
                "common_artist": "Led Zeppelin",
                "common_album": "Led Zeppelin IV",
                "common_year": "1971",
                "likely_compilation": False,
                "track_number_pattern": "sequential"
            }
        }
        
        proposal = generator.get_llm_proposal(metadata, artist_hint="Led Zeppelin")
        
        # Verify the proposal uses the artist hint
        assert proposal["artist"] == "Led Zeppelin"
        assert proposal["album"] == "Led Zeppelin IV"
        assert proposal["year"] == "1971"
        
        # Verify prompt includes artist hint
        call_args = mock_llm.call_args[0]
        prompt = call_args[0]
        assert "Led Zeppelin" in prompt
        assert "artist collection" in prompt

    def test_proposal_with_user_feedback(self, generator, mock_llm):
        """Test proposal generation with user feedback."""
        mock_llm.return_value = {
            "choices": [{
                "text": '{"artist": "Pink Floyd", "album": "The Dark Side of the Moon", "year": "1973", "release_type": "Album", "confidence": "high", "reasoning": "Corrected based on user feedback"}'
            }]
        }
        
        metadata = {
            "folder_name": "Unknown Album",
            "total_files": 10,
            "files": [
                {"filename": "01 - Speak to Me.mp3", "artist": "Pink Floyd", "title": "Speak to Me"},
                {"filename": "02 - Breathe.mp3", "artist": "Pink Floyd", "title": "Breathe"},
            ],
            "analysis": {
                "common_artist": "Pink Floyd",
                "common_album": "Unknown",
                "common_year": "Unknown",
                "likely_compilation": False,
                "track_number_pattern": "sequential"
            }
        }
        
        user_feedback = "This is actually The Dark Side of the Moon from 1973"
        proposal = generator.get_llm_proposal(metadata, user_feedback=user_feedback)
        
        # Verify the proposal incorporates feedback
        assert proposal["artist"] == "Pink Floyd"
        assert proposal["album"] == "The Dark Side of the Moon"
        assert proposal["year"] == "1973"
        
        # Verify prompt includes user feedback
        call_args = mock_llm.call_args[0]
        prompt = call_args[0]
        assert user_feedback in prompt
        assert "reconsider" in prompt

    def test_invalid_json_response_parsing(self, generator, mock_llm):
        """Test handling of invalid JSON response from LLM."""
        # Mock LLM to return invalid JSON
        mock_llm.return_value = {
            "choices": [{
                "text": "artist: The Beatles\nalbum: Abbey Road\nyear: 1969\nrelease_type: Album"
            }]
        }
        
        metadata = {
            "folder_name": "Test Album",
            "total_files": 5,
            "files": [],
            "analysis": {}
        }
        
        proposal = generator.get_llm_proposal(metadata)
        
        # Should parse what it can from the text
        assert proposal["artist"] == "The Beatles"
        assert proposal["album"] == "Abbey Road"
        assert proposal["year"] == "1969"
        assert proposal["release_type"] == "Album"  # Should be extracted from text

    def test_llm_failure_fallback(self, generator, mock_llm):
        """Test fallback behavior when LLM fails."""
        # Mock LLM to fail
        mock_llm.side_effect = Exception("LLM connection failed")
        
        metadata = {
            "folder_name": "Test Album",
            "total_files": 5,
            "files": [],
            "analysis": {
                "common_artist": "Test Artist",
                "common_album": "Test Album",
                "common_year": "2023",
                "likely_compilation": False
            }
        }
        
        proposal = generator.get_llm_proposal(metadata)
        
        # Should return fallback proposal
        assert proposal["artist"] == "Test Artist"
        assert proposal["album"] == "Test Album"
        assert proposal["year"] == "2023"
        assert proposal["release_type"] == "Album"
        assert proposal["confidence"] == "low"
        assert "LLM unavailable" in proposal["reasoning"]

    def test_fallback_with_artist_hint(self, generator, mock_llm):
        """Test fallback behavior with artist hint."""
        mock_llm.side_effect = Exception("LLM failed")
        
        metadata = {
            "folder_name": "Some Album",
            "total_files": 8,
            "files": [],
            "analysis": {
                "common_artist": "Unknown",
                "common_album": "Some Album",
                "common_year": "2023",
                "likely_compilation": False
            }
        }
        
        proposal = generator.get_llm_proposal(metadata, artist_hint="Hinted Artist")
        
        # Should use artist hint in fallback
        assert proposal["artist"] == "Hinted Artist"
        assert proposal["album"] == "Some Album"
        assert proposal["year"] == "2023"
        assert proposal["confidence"] == "low"

    def test_compilation_detection(self, generator, mock_llm):
        """Test handling of compilation albums."""
        mock_llm.return_value = {
            "choices": [{
                "text": '{"artist": "Various Artists", "album": "Greatest Hits of the 80s", "year": "2020", "release_type": "Compilation", "confidence": "high", "reasoning": "Multiple artists indicate compilation"}'
            }]
        }
        
        metadata = {
            "folder_name": "Greatest Hits of the 80s",
            "total_files": 20,
            "files": [
                {"filename": "01 - Billie Jean.mp3", "artist": "Michael Jackson", "title": "Billie Jean"},
                {"filename": "02 - Sweet Child O' Mine.mp3", "artist": "Guns N' Roses", "title": "Sweet Child O' Mine"},
                {"filename": "03 - Livin' on a Prayer.mp3", "artist": "Bon Jovi", "title": "Livin' on a Prayer"},
            ],
            "analysis": {
                "common_artist": "Various Artists",
                "common_album": "Greatest Hits of the 80s",
                "common_year": "2020",
                "likely_compilation": True,
                "track_number_pattern": "sequential"
            }
        }
        
        proposal = generator.get_llm_proposal(metadata)
        
        # Should detect compilation
        assert proposal["artist"] == "Various Artists"
        assert proposal["album"] == "Greatest Hits of the 80s"
        assert proposal["release_type"] == "Compilation"
        
        # Verify prompt indicates compilation
        call_args = mock_llm.call_args[0]
        prompt = call_args[0]
        assert "Yes" in prompt  # Is Compilation: Yes

    def test_prompt_building_completeness(self, generator, mock_llm):
        """Test that prompts contain all necessary information."""
        mock_llm.return_value = {
            "choices": [{"text": '{"artist": "Test", "album": "Test", "year": "2023", "release_type": "Album", "confidence": "medium", "reasoning": "Test"}'}]
        }
        
        metadata = {
            "folder_name": "Complex Album Name",
            "total_files": 15,
            "files": [
                {"filename": "track1.mp3", "artist": "Artist1", "title": "Title1"},
                {"filename": "track2.mp3", "artist": "Artist2", "title": "Title2"},
                {"filename": "track3.mp3", "artist": "Artist3", "title": "Title3"},
            ],
            "analysis": {
                "common_artist": "Various Artists",
                "common_album": "Complex Album Name",
                "common_year": "2023",
                "likely_compilation": True,
                "track_number_pattern": "inconsistent"
            }
        }
        
        generator.get_llm_proposal(metadata, user_feedback="Test feedback", artist_hint="Test hint")
        
        # Verify prompt contains all expected elements
        call_args = mock_llm.call_args[0]
        prompt = call_args[0]
        
        # Check folder information
        assert "Complex Album Name" in prompt
        assert "15" in prompt  # total files
        assert "Various Artists" in prompt
        assert "2023" in prompt
        
        # Check file samples
        assert "track1.mp3" in prompt
        assert "Artist1" in prompt
        assert "Title1" in prompt
        
        # Check user feedback
        assert "Test feedback" in prompt
        assert "reconsider" in prompt
        
        # Check artist hint
        assert "Test hint" in prompt
        assert "artist collection" in prompt
        
        # Check compilation flag
        assert "Yes" in prompt  # Is Compilation: Yes
        
        # Check track pattern
        assert "inconsistent" in prompt
        
        # Check JSON format requirement
        assert "JSON response" in prompt
        assert "artist" in prompt
        assert "album" in prompt
        assert "year" in prompt
        assert "release_type" in prompt
        assert "confidence" in prompt
        assert "reasoning" in prompt 