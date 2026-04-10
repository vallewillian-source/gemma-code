# Project Structure Summary for gemma-code

## Overview

gemma-code is a fork of the upstream SWE-agent project, adapted for offline, overnight software engineering workflows with local models from the Gemma 4 family. It optimizes for:

- Strong guidance and deterministic workflows for weaker local models
- Explicit tradeoffs in time and compute, with the agent designed to run unattended overnight
- A separate external LLM orchestrator and validator, starting with DeepSeekV3.2
- A narrow, opinionated setup that helps models build complete software systems instead of only partial fixes

## Main Components

### Core Modules

1. **Agents** (`src/gemmacode/agents/`)
   - `default.py`: Basic agent class implementing the core workflow
   - `interactive.py`: Enhanced agent with user interaction capabilities

2. **Models** (`src/gemmacode/models/`)
   - `litellm_model.py`: Implementation for LiteLLM-based models
   - `openrouter_model.py`: Implementation for OpenRouter models
   - `portkey_model.py`: Implementation for Portkey models
   - `requesty_model.py`: Implementation for Requesty models
   - `test_models.py`: Test utilities for model implementations

3. **Environments** (`src/gemmacode/environments/`)
   - `local.py`: Local execution environment
   - `docker.py`: Docker-based execution environment
   - `singularity.py`: Singularity-based execution environment
   - `extra/`: Additional environment implementations (contree, bubblewrap)

4. **Configuration** (`src/gemmacode/config/`)
   - Centralized configuration handling

5. **Run Scripts** (`src/gemmacode/run/`)
   - `mini.py`: Entry point for the mini CLI interface
   - Benchmark scripts for batch processing (e.g., swebench.py)

### Key Files

- `src/gemmacode/__init__.py`: Main package initialization with core protocols
- `src/gemmacode/exceptions.py`: Custom exception definitions
- `src/gemmacode/__main__.py`: Entry point for the CLI
- `pyproject.toml`: Python project configuration
- `README.md`: Main project documentation

### Key Features

- **Local-first approach**: Optimized for Gemma 4 models running on local hardware
- **Opinionated design**: Provides scaffolding to help smaller models produce complete changes
- **Orchestrated workflow**: Uses external validator/orchestrator for quality control
- **Unattended operation**: Designed to run for long stretches without supervision
- **Shell-first interaction**: Maintains linear trace of actions and messages for debugging
- **Simple execution**: Uses `subprocess.run` for each action for stability

### CLI Usage

The project provides several ways to use it:

1. **As CLI tool**: `gemma-code` command
2. **As Python package**: `from gemmacode import DefaultAgent, LitellmModel, LocalEnvironment`
3. **Batch processing**: For benchmarking (e.g., swebench)
4. **Interactive mode**: With user prompts

### Main Entry Points

- `gemma-code` CLI command (via `src/gemmacode/__main__.py`)
- `src/gemmacode/run/mini.py` for mini workflow
- Benchmark scripts in `src/gemmacode/run/benchmarks/`

### Architecture

The architecture follows a clear separation of concerns:

1. **Model**: Language model interface (protocol)
2. **Environment**: Execution environment (protocol)
3. **Agent**: High-level workflow implementation

This design allows for easy swapping of components while maintaining consistent interfaces.
