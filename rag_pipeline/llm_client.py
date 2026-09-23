"""
Unified LLM Client supporting multiple providers:
- Ollama (local, free)
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude) - optional
"""

import os
import yaml
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str:
        """Generate response from prompt with optional system message."""
        pass

    @abstractmethod
    def generate_stream(self, prompt: str, system: str = ""):
        """Stream response tokens (optional implementation)."""
        pass


class OllamaClient(LLMClient):
    """Ollama local LLM client."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs
    ):
        try:
            import ollama
        except ImportError:
            raise ImportError("ollama package not installed. Run: pip install ollama")

        self.client = ollama.Client(host=base_url)
        self.model = model
        self.options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            **kwargs
        }

    def generate(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat(
            model=self.model,
            messages=messages,
            options=self.options
        )
        return response["message"]["content"]

    def generate_stream(self, prompt: str, system: str = ""):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat(
            model=self.model,
            messages=messages,
            options=self.options,
            stream=True
        )
        for chunk in stream:
            if "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]


class OpenAIClient(LLMClient):
    """OpenAI API client (GPT-4o, GPT-4o-mini, etc.)."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        # Resolve API key from env var if using ${VAR} syntax
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var)
            if not api_key:
                raise ValueError(f"Environment variable {env_var} not set")

        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

    def generate(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **self.kwargs
        )
        return response.choices[0].message.content

    def generate_stream(self, prompt: str, system: str = ""):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **self.kwargs
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicClient(LLMClient):
    """Anthropic Claude API client (optional)."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        **kwargs
    ):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var)

        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = model
        self.kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

    def generate(self, prompt: str, system: str = "") -> str:
        messages = [{"role": "user", "content": prompt}]

        response = self.client.messages.create(
            model=self.model,
            messages=messages,
            system=system if system else None,
            **self.kwargs
        )
        return response.content[0].text

    def generate_stream(self, prompt: str, system: str = ""):
        messages = [{"role": "user", "content": prompt}]

        stream = self.client.messages.create(
            model=self.model,
            messages=messages,
            system=system if system else None,
            stream=True,
            **self.kwargs
        )
        for chunk in stream:
            if chunk.type == "content_block_delta":
                yield chunk.delta.text


def get_llm_client(config: Dict[str, Any]) -> LLMClient:
    """
    Factory function to create LLM client from config.

    Args:
        config: Full config dict (e.g., from yaml.safe_load)

    Returns:
        LLMClient instance
    """
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "ollama")

    # Resolve ${ENV_VAR} placeholders in all string values
    params = {}
    for k, v in llm_config.items():
        if k == "provider":
            continue
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            params[k] = os.getenv(env_var, v)
        else:
            params[k] = v

    if provider == "ollama":
        return OllamaClient(**params)
    elif provider == "openai":
        return OpenAIClient(**params)
    elif provider == "anthropic":
        return AnthropicClient(**params)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: ollama, openai, anthropic")


# ─── Convenience function for direct use ─────────────────────────────────

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def create_llm_client(config_path: str = "config.yaml") -> LLMClient:
    """Load config and create LLM client in one call."""
    config = load_config(config_path)
    return get_llm_client(config)