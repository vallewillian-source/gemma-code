"""Automatic model defaults for gemma-code.

This module keeps the primary agent model selection code-driven instead of
asking the user at runtime. The current default policy is:

- local execution model: Gemma via Ollama
- future validator/orchestrator: DeepSeek via API
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv

repo_env_file = Path(__file__).resolve().parents[2] / ".env"
if repo_env_file.exists():
    load_dotenv(dotenv_path=repo_env_file, override=False)

DEFAULT_OLLAMA_BASE_URL = os.getenv(
    "GEMMACODE_OLLAMA_BASE_URL",
    os.getenv("OLLAMA_HOST", "http://192.168.0.23:11434"),
)


def normalize_local_model_name(model_name: str) -> str:
    if model_name == "ollama/gemma4":
        return "ollama/gemma4:26b"
    return model_name


DEFAULT_LOCAL_MODEL_NAME = normalize_local_model_name(os.getenv("GEMMACODE_LOCAL_MODEL_NAME", "ollama/gemma4:26b"))
DEFAULT_LOCAL_MODEL_CLASS = os.getenv("GEMMACODE_LOCAL_MODEL_CLASS", "litellm")
DEFAULT_VALIDATOR_MODEL_NAME = os.getenv("GEMMACODE_VALIDATOR_MODEL_NAME", "deepseek-v3.2")
DEFAULT_VALIDATOR_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_VALIDATOR_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


def get_local_model_name() -> str:
    """Return the automatic local model name used by the main agent."""
    return normalize_local_model_name(os.getenv("GEMMACODE_LOCAL_MODEL_NAME", DEFAULT_LOCAL_MODEL_NAME))


def get_local_model_base_url() -> str:
    """Return the Ollama endpoint used by the main agent."""
    return os.getenv("GEMMACODE_OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_BASE_URL))


def _ollama_tags_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/tags"


def is_ollama_available(base_url: str | None = None) -> bool:
    """Check whether the configured Ollama server is reachable."""
    url = _ollama_tags_url(base_url or get_local_model_base_url())
    try:
        with urlopen(url, timeout=2) as response:
            return 200 <= getattr(response, "status", 200) < 300
    except URLError:
        return False
    except Exception:
        return False


def get_local_model_kwargs() -> dict[str, str]:
    """Return the default kwargs for the local Ollama model."""
    return {"api_base": get_local_model_base_url()}


def get_validator_settings() -> dict[str, str]:
    """Return the validator/orchestrator connection settings.

    This is intentionally small for now, so future orchestration code can
    consume a single dict without re-reading env vars.
    """

    return {
        "api_key": DEFAULT_VALIDATOR_API_KEY,
        "base_url": DEFAULT_VALIDATOR_BASE_URL,
        "model_name": DEFAULT_VALIDATOR_MODEL_NAME,
    }
