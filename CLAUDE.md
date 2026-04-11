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

## Overnight Orchestration System

The overnight pipeline is a complete two-level task decomposition and execution system:

### Components

1. **OrchestratorAgent** (`src/gemmacode/agents/orchestrator.py`)
   - Takes a high-level task and repository context
   - Calls DeepSeek API to decompose into structured subtasks
   - Returns `DecompositionPlan` with validated subtask specs
   - Retries up to 3 times on JSON parsing failure
   - Uses litellm directly (no tool calling) for clean text-only generation

2. **SubtaskRunner** (`src/gemmacode/agents/subtask_runner.py`)
   - Executes individual subtasks using a small local model (default: ollama/qwen3-coder:30b)
   - Runs acceptance tests and retries on failure
   - Complexity-based step limits: low=20, medium=40, high=60
   - Creates RestrictedEnvironment with allowlist of readable files
   - Returns SubtaskResult with status (PASSED/FAILED), error messages, test outputs

3. **Topological Sort** (`src/gemmacode/orchestrator/ordering.py`)
   - Kahn's algorithm for dependency ordering
   - Validates DAG (no cycles), preserves original order within levels
   - Used to execute subtasks respecting dependencies

4. **Overnight CLI** (`src/gemmacode/run/overnight.py`)
   - Entry point: `gemma-code-overnight`
   - Options: `--task` (required), `--output` (optional), `--heuristics` (optional), `--dry-run` (flag)
   - Workflow: build repo map → decompose → (optional dry-run) → topologically sort → execute → summarize
   - Saves: plan.json, result_*.json, summary.json
   - Non-blocking: continues if individual subtasks fail (summarizes failures)

### Configuration

**overnight.yaml:**
```yaml
agent:
  step_limit: 40          # Max steps per orchestrator call
  cost_limit: 0.0         # No cost limit (set > 0 to enforce)
  mode: yolo              # Continue on minor errors

model:
  model_name: deepseek/deepseek-chat
  model_kwargs:
    num_ctx: 40960        # Large context for decomposition
  cost_tracking: ignore_errors  # DeepSeek costs not fully tracked

environment:
  timeout: 60             # Subtask execution timeout
```

### Key Implementation Details

- **OrchestratorAgent bypasses tool parsing**: Calls `litellm.completion()` directly without the BASH_TOOL to avoid FormatError on text-only JSON responses
- **API Key Injection**: `get_model()` automatically injects DEEPSEEK_API_KEY and DEEPSEEK_BASE_URL from environment
- **Heuristics System**: Uses YAML-based rules in `src/gemmacode/config/heuristics/*.yaml` to guide decomposition
- **RestrictedEnvironment**: Limits file access to specified files in spec to prevent accidental modification of unrelated files
- **Test Verification Loop**: Each subtask must pass acceptance tests; failures trigger retry with feedback

### Testing

- **180 tests passing** covering all components
- Integration tests verify execution order, dependency blocking, failure handling
- Mock mocks for DeepSeek when needed; real API calls in production

### Common Workflows

```bash
# Dry-run decomposition only
gemma-code-overnight --task "..." --dry-run

# Full execution with output
gemma-code-overnight --task "..." --output /path/to/output

# Apply specific heuristics
gemma-code-overnight --task "..." --heuristics python_project testing_patterns
```

### Troubleshooting

- **Empty API responses**: Usually means tools=[] was not used (OrchestratorAgent already fixed this)
- **Subtask failures**: Check result_*.json in output directory for detailed error messages
- **Large tasks**: Increase num_ctx in overnight.yaml if task description is very long
- **Cost tracking errors**: Set cost_tracking: ignore_errors in model config
