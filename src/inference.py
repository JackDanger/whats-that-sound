"""Unified inference provider interface and implementations.

Every inference call takes a single prompt string and returns a single string.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

# Optional, lazily used imports exposed for easier mocking in tests
try:  # pragma: no cover - best-effort optional dependency
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

try:  # pragma: no cover
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore

try:  # pragma: no cover
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore


class TextProvider(ABC):
    """Abstract text generation provider.

    Subclasses must implement generate to return plain text for a given prompt and model.
    """

    @abstractmethod
    def generate(self, prompt: str, model: str) -> str:
        raise NotImplementedError


class OpenAITextProvider(TextProvider):
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when using the OpenAI provider"
            )

    def generate(self, prompt: str, model: str) -> str:
        if OpenAI is None:
            raise RuntimeError("openai client library not installed")
        client = OpenAI(api_key=self._api_key)
        stream_enabled = (os.getenv("STREAM_PROMPTS") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        if stream_enabled:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You're an earnest, foolish author."},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            chunks = []
            for event in completion:
                # The SDK yields events with .choices[0].delta.content during streaming
                delta = getattr(event.choices[0].delta, "content", None)
                if delta:
                    chunks.append(delta)
            return "".join(chunks)
        else:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You're an earnest, foolish author."},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content  # type: ignore[attr-defined]


class GeminiTextProvider(TextProvider):
    def __init__(self, api_key: Optional[str] = None):
        # Configure client module at init
        api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY (or GEMINI_API_KEY) is required for Gemini provider"
            )
        if genai is None:
            raise RuntimeError("google-generativeai library not installed")
        genai.configure(api_key=api_key)
        self._genai = genai

    def generate(self, prompt: str, model: str) -> str:
        gm = self._genai.GenerativeModel(model)
        resp = gm.generate_content(prompt)
        text = getattr(resp, "text", None)
        if text is not None:
            return text
        # Fallback to candidate parts
        if getattr(resp, "candidates", None):
            candidate = resp.candidates[0]
            if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                part = candidate.content.parts[0]
                return getattr(part, "text", "")
        return ""


class LlamaTextProvider(TextProvider):
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or os.getenv("LLAMA_API_BASE", "http://localhost:11434/v1")
        self.api_key = api_key or os.getenv("LLAMA_API_KEY")

    def generate(self, prompt: str, model: str) -> str:
        import json as _json
        if requests is None:
            raise RuntimeError("requests library not installed")

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": (os.getenv("STREAM_PROMPTS") or "").lower() in ("1", "true", "yes"),
        }

        if payload["stream"]:
            with requests.post(url, headers=headers, json=payload, timeout=300, stream=True) as resp:
                resp.raise_for_status()
                chunks = []
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        try:
                            data = _json.loads(line[len("data: "):])
                            delta = (
                                data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content")
                            )
                            if delta:
                                chunks.append(delta)
                        except Exception:
                            # Ignore malformed lines
                            pass
                return "".join(chunks)
        else:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class InferenceProvider:
    """Facade that routes prompts to a configured provider and model.

    Usage:
        inference = InferenceProvider(provider="openai", model="gpt-5")
        text = inference.generate("hello")
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        llama_base_url: Optional[str] = None,
        llama_api_key: Optional[str] = None,
    ) -> None:
        provider = (provider or os.getenv("INFERENCE_PROVIDER") or "llama").lower()
        if provider not in ("openai", "gemini", "llama"):
            raise ValueError(f"Unsupported provider: {provider}")

        self.provider_name = provider
        if provider == "openai":
            self.provider: TextProvider = OpenAITextProvider(api_key=openai_api_key)
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")
        elif provider == "gemini":
            self.provider = GeminiTextProvider(api_key=gemini_api_key)
            self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        else:  # llama
            self.provider = LlamaTextProvider(
                base_url=llama_base_url, api_key=llama_api_key
            )
            self.model = model or os.getenv("LLAMA_MODEL", "llama3.1")

    def generate(self, prompt: str) -> str:
        return self.provider.generate(prompt, self.model)


