"""Tests for InferenceProvider and concrete providers.

These tests mock actual client libraries to validate expected calls without side effects.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.inference import InferenceProvider, OpenAITextProvider, GeminiTextProvider, LlamaTextProvider


class TestOpenAITextProvider:
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    def test_generate_non_streaming(self):
        fake_client = MagicMock()
        fake_resp = MagicMock()
        # response.choices[0].message.content
        fake_choice = MagicMock()
        fake_choice.message.content = "hello"
        fake_resp.choices = [fake_choice]
        fake_client.chat.completions.create.return_value = fake_resp

        with patch("src.inference.OpenAI", return_value=fake_client):
            provider = OpenAITextProvider()
            result = provider.generate("hi", model="gpt-5")
            assert result == "hello"
            fake_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "STREAM_PROMPTS": "0"})
    def test_generate_streaming_toggle_off(self):
        # STREAM_PROMPTS disabled should still call non-streaming path
        fake_client = MagicMock()
        fake_resp = MagicMock()
        fake_choice = MagicMock()
        fake_choice.message.content = "world"
        fake_resp.choices = [fake_choice]
        fake_client.chat.completions.create.return_value = fake_resp

        with patch("src.inference.OpenAI", return_value=fake_client):
            provider = OpenAITextProvider()
            result = provider.generate("hi", model="gpt-5")
            assert result == "world"


class TestGeminiTextProvider:
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "g-test"})
    def test_generate_uses_text_attr_first(self):
        fake_genai = MagicMock()
        fake_model = MagicMock()
        fake_resp = MagicMock()
        fake_resp.text = "gemini-text"
        fake_model.generate_content.return_value = fake_resp
        fake_genai.GenerativeModel.return_value = fake_model

        with patch("src.inference.genai", fake_genai):
            provider = GeminiTextProvider()
            out = provider.generate("prompt", model="gemini-1.5-pro")
            assert out == "gemini-text"
            fake_model.generate_content.assert_called_once_with("prompt")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "g-test"})
    def test_generate_uses_candidates_when_no_text(self):
        fake_genai = MagicMock()
        fake_model = MagicMock()
        fake_resp = MagicMock()
        fake_resp.text = None
        fake_candidate = MagicMock()
        fake_part = MagicMock()
        fake_part.text = "from-candidate"
        fake_candidate.content.parts = [fake_part]
        fake_resp.candidates = [fake_candidate]
        fake_model.generate_content.return_value = fake_resp
        fake_genai.GenerativeModel.return_value = fake_model

        with patch("src.inference.genai", fake_genai):
            provider = GeminiTextProvider()
            out = provider.generate("prompt", model="gemini-1.5-pro")
            assert out == "from-candidate"


class TestLlamaTextProvider:
    def test_generate_non_streaming(self):
        import json as _json

        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "llama out"}}]
        }
        fake_resp.raise_for_status.return_value = None

        fake_requests = MagicMock()
        fake_requests.post.return_value = fake_resp

        with patch("src.inference.requests", fake_requests):
            provider = LlamaTextProvider(base_url="http://x")
            out = provider.generate("prompt", model="llama-xyz")
            assert out == "llama out"
            # Validate payload shape via call args
            args, kwargs = fake_requests.post.call_args
            assert args[0].endswith("/chat/completions")
            assert kwargs["json"]["model"] == "llama-xyz"
            assert kwargs["json"]["messages"][0]["content"] == "prompt"


class TestInferenceProviderFacade:
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk", "INFERENCE_PROVIDER": "openai"})
    def test_openai_facade(self):
        fake = MagicMock()
        fake_choice = MagicMock()
        fake_choice.message.content = "ok"
        fake_resp = MagicMock()
        fake_resp.choices = [fake_choice]
        fake.chat.completions.create.return_value = fake_resp

        with patch("src.inference.OpenAI", return_value=fake):
            inf = InferenceProvider()
            out = inf.generate("p")
            assert out == "ok"

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "g", "INFERENCE_PROVIDER": "gemini"})
    def test_gemini_facade(self):
        fake_genai = MagicMock()
        fake_model = MagicMock()
        fake_resp = MagicMock()
        fake_resp.text = "gem-out"
        fake_model.generate_content.return_value = fake_resp
        fake_genai.GenerativeModel.return_value = fake_model

        with patch("src.inference.genai", fake_genai):
            inf = InferenceProvider()
            assert inf.generate("p") == "gem-out"

    def test_llama_facade(self):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": "ll-out"}}]
        }
        fake_resp.raise_for_status.return_value = None
        fake_requests = MagicMock()
        fake_requests.post.return_value = fake_resp

        with patch.dict(os.environ, {"INFERENCE_PROVIDER": "llama"}, clear=False):
            with patch("src.inference.requests", fake_requests):
                inf = InferenceProvider(model="llm")
                assert inf.generate("p") == "ll-out"


