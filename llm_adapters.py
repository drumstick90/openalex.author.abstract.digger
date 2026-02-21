"""
LLM Provider Adapters -- uniform interface for Gemini, OpenAI, and Anthropic.

Each adapter exposes:
  generate(prompt, system_prompt=None, json_mode=False) -> str
  get_model_name() -> str

Factory:
  create_adapter(provider, api_key, model=None) -> BaseLLMAdapter
"""

import os
from abc import ABC, abstractmethod


PROVIDER_CATALOG = {
    "gemini": {
        "name": "Google Gemini",
        "models": ["gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro"],
        "default": "gemini-2.0-flash",
        "env_key": "GEMINI_API_KEY",
    },
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
        "default": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
        "default": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
    },
}


class BaseLLMAdapter(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None,
                 json_mode: bool = False) -> str:
        """Send a prompt and return the text response."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier actually used."""


class GeminiAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str | None = None):
        import google.generativeai as genai
        self._genai = genai
        genai.configure(api_key=api_key)
        self._model = model or PROVIDER_CATALOG["gemini"]["default"]

    def generate(self, prompt, system_prompt=None, json_mode=False):
        config = {}
        if json_mode:
            config["response_mime_type"] = "application/json"

        kwargs = {"model_name": self._model}
        if system_prompt:
            kwargs["system_instruction"] = system_prompt

        model = self._genai.GenerativeModel(**kwargs, generation_config=config or None)

        gen_config = self._genai.types.GenerationConfig(temperature=0.5) if not json_mode else None
        response = model.generate_content(prompt, generation_config=gen_config)
        return response.text

    def get_model_name(self):
        return self._model


class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str | None = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model or PROVIDER_CATALOG["openai"]["default"]

    def generate(self, prompt, system_prompt=None, json_mode=False):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.5,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def get_model_name(self):
        return self._model


class AnthropicAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str | None = None):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._model = model or PROVIDER_CATALOG["anthropic"]["default"]

    def generate(self, prompt, system_prompt=None, json_mode=False):
        kwargs = {
            "model": self._model,
            "max_tokens": 4096,
            "temperature": 0.5,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        return response.content[0].text

    def get_model_name(self):
        return self._model


def resolve_api_key(provider: str, user_key: str | None) -> str:
    """Return user key if given, else fall back to env var."""
    if user_key:
        return user_key
    env_var = PROVIDER_CATALOG.get(provider, {}).get("env_key", "")
    key = os.environ.get(env_var, "")
    if not key:
        raise ValueError(
            f"No API key provided for {provider} and {env_var} is not set in environment"
        )
    return key


def create_adapter(provider: str = "gemini", api_key: str | None = None,
                   model: str | None = None) -> BaseLLMAdapter:
    """Factory: instantiate the right adapter for the given provider."""
    key = resolve_api_key(provider, api_key)

    if provider == "gemini":
        return GeminiAdapter(key, model)
    elif provider == "openai":
        return OpenAIAdapter(key, model)
    elif provider == "anthropic":
        return AnthropicAdapter(key, model)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_providers_info() -> list[dict]:
    """Return catalog info for the frontend settings panel."""
    result = []
    for pid, info in PROVIDER_CATALOG.items():
        result.append({
            "id": pid,
            "name": info["name"],
            "models": info["models"],
            "default_model": info["default"],
            "has_server_key": bool(os.environ.get(info["env_key"], "")),
        })
    return result
