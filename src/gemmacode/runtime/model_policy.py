"""Automatic model defaults for gemma-code.

This module keeps the primary agent model selection code-driven instead of
asking the user at runtime. The current default policy is:

- local execution model: Gemma via Ollama
- future validator/orchestrator: DeepSeek via API
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

repo_env_file = Path(__file__).resolve().parents[2] / ".env"
if repo_env_file.exists():
    load_dotenv(dotenv_path=repo_env_file, override=False)

DEFAULT_LOCAL_MODEL_NAME = os.getenv("GEMMACODE_LOCAL_MODEL_NAME", "ollama/gemma4")
DEFAULT_LOCAL_MODEL_CLASS = os.getenv("GEMMACODE_LOCAL_MODEL_CLASS", "litellm")
DEFAULT_VALIDATOR_MODEL_NAME = os.getenv("GEMMACODE_VALIDATOR_MODEL_NAME", "deepseek-v3.2")
DEFAULT_VALIDATOR_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_VALIDATOR_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


def get_local_model_name() -> str:
    """Return the automatic local model name used by the main agent."""
    return DEFAULT_LOCAL_MODEL_NAME


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
