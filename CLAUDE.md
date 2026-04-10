# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### Installation & Setup

```bash
# Install in editable mode with dev dependencies
pip install -e '.[dev]'

# Set up pre-commit hooks for automatic linting
pre-commit install
```

### Common Commands

```bash
# Run tests in parallel (typical time: ~3min)
pytest -n auto

# Run a specific test file
pytest tests/agents/test_default.py

# Run a single test
pytest tests/agents/test_default.py::test_agent_basic

# Check code style with ruff (runs automatically via pre-commit)
ruff check src/gemmacode

# Fix style issues automatically
ruff check --fix src/gemmacode

# Run the CLI interactively
gemma-code

# Run an example script
python src/gemmacode/run/hello_world.py
```

## Project Overview

**gemma-code** is an AI software engineering agent optimized for local Gemma 4 models and unattended overnight workflows. It's a minimal fork of SWE-agent with:

- **Minimal core**: No complex tool implementations; agents use bash directly
- **Linear history**: All messages append to history; easy to debug and understand
- **Independent subprocess execution**: Every action runs in isolation (no stateful shell sessions)
- **Protocol-based extensibility**: Use Python protocols/duck typing for custom implementations

## Architecture

### Core Components

1. **Agents** (`src/gemmacode/agents/`)
   - `default.py`: Minimal agent implementation
   - `interactive.py`: Extends default with human-in-the-loop confirmations
   - Both implement the `Agent` protocol from `src/gemmacode/__init__.py`

2. **Models** (`src/gemmacode/models/`)
   - `litellm_model.py`: Primary model integration (supports OpenAI, Anthropic, local models, etc.)
   - `openrouter_model.py`, `portkey_model.py`: Alternative providers
   - All models implement the `Model` protocol
   - Models handle streaming, retry logic, and token counting via litellm

3. **Runtime** (`src/gemmacode/runtime/`)
   - `model_policy.py`: Controls agent behavior (retry strategies, message composition)
   - Defines how agents interact with models

4. **Environments** (`src/gemmacode/environments/`)
   - `LocalEnvironment`: Local filesystem operations
   - Implements the `Environment` protocol for extensibility

5. **Config** (`src/gemmacode/config/`)
   - YAML-based configuration system
   - Command configuration, model settings, agent parameters

6. **Repomap** (`src/gemmacode/repomap/`)
   - Repository structure analysis
   - Summarizes codebase for context injection

### Entry Points

- `src/gemmacode/run/mini.py`: Main CLI (installed as `gemma-code` command)
- `src/gemmacode/run/hello_world.py`: Minimal example of agent usage
- Extra utilities in `src/gemmacode/run/extra/` and `src/gemmacode/run/benchmarks/`

## Code Style & Conventions

### From `.github/copilot-instructions.md`:

**General**
- Target Python 3.10+ with type annotations (use `list` not `List`)
- Use `pathlib.Path` instead of `os.path`
- Use `typer` for CLI interfaces
- Use `jinja` for template formatting
- Keep comments minimal; only explain logically challenging sections
- Write concise, minimal code—this repo rewards brevity
- Use `dataclass` for configuration tracking
- **Don't catch exceptions unless explicitly asked**—let them propagate to show problems to the user

**Testing**
- Use `pytest`, not `unittest`
- **Do NOT mock/patch** unless explicitly requested in the task
- Avoid trivial tests; every test should catch multiple points of failure
- Keep test code concise: `assert func() == expected`, not multi-line setups
- `pytest.mark.parametrize` first arg: tuple (not string/list), second arg: list (not tuple)
- Print statements in tests are fine and won't trigger warnings

## Testing Strategy

Tests live in `tests/` with structure mirroring `src/gemmacode/`:
- `tests/agents/`, `tests/models/`, `tests/runtime/`, etc.
- Use `pytest.fixture` for setup (see `tests/conftest.py`)
- Integration tests preferred over mocks (especially for environments and models)

Run tests in parallel: `pytest -n auto` (much faster than serial)

## Key Design Decisions

1. **No stateful shell sessions**: Each command runs via `subprocess.run` in isolation. This trades minor efficiency for major stability and debuggability.

2. **Protocol-based design**: The `Model`, `Agent`, and `Environment` protocols in `src/gemmacode/__init__.py` define contracts. You can swap implementations without changing the rest of the system.

3. **Opinionated, not configurable**: Not all behavior is exposed in YAML config. For customization, create a Python run script (like `hello_world.py`) rather than trying to configure everything.

4. **Minimal model integration**: Models don't get custom tool implementations. Instead, agents tell the model to use bash to accomplish tasks.

5. **Linear message history**: Every step appends to the same message list. This makes debugging, logging, and external validation straightforward.

## When Adding Features

- **New agent behavior?** Create a new `Agent` implementation (possibly in `src/gemmacode/agents/` or a run script).
- **New model provider?** Add a model class to `src/gemmacode/models/` that implements the `Model` protocol.
- **New command?** Add to `src/gemmacode/config/commands/` or create a YAML config file.
- **New environment?** Implement the `Environment` protocol in `src/gemmacode/environments/`.
- **Small/specific features?** Put them in `extra/` subdirectories (e.g., `src/gemmacode/run/extra/`).

Keep new components self-contained. Share utilities only if they're genuinely reusable across multiple components.

## Important Files & Patterns

- `src/gemmacode/__init__.py`: Defines `Model`, `Agent`, `Environment` protocols; sets up global config paths
- `pyproject.toml`: Build config, dependencies, ruff/pytest settings
- `.pre-commit-config.yaml`: Runs ruff check + format automatically on commits
- `docs/contributing.md`: More on contribution guidelines
- `docs/quickstart.md`: User-facing installation and setup

## Testing & Validation

- Pre-commit hooks run ruff automatically (format + lint)
- No need to manually run `ruff format` or `ruff check --fix`—pre-commit handles it
- Failing tests block commits; fix them before pushing
- For new features, write tests *before* or *alongside* the implementation

## Frequently Needed Context

### Global Config Directory
Set via `MSWEA_GLOBAL_CONFIG_DIR` env var; defaults to `~/.config/gemma-code` on Linux/Mac.

### Model Configuration
Models are initialized via litellm's model string (e.g., `anthropic/claude-3-sonnet-20240229`). Setup wizard guides users through this on first run.

### Command Configuration
Bash commands agents can run are defined in YAML config files. See `src/gemmacode/config/commands/` for examples.

### Version
Current version is in `src/gemmacode/__init__.py` (`__version__`).
