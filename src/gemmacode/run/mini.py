#!/usr/bin/env python3

"""Run gemma-code in your local environment. This is the default executable `mini`."""
# Read this first: https://gemma-code.com/latest/usage/mini/  (usage)

import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from gemmacode import global_config_dir
from gemmacode.agents import get_agent
from gemmacode.agents.utils.prompt_user import _multiline_prompt
from gemmacode.config import builtin_config_dir, get_config_from_spec
from gemmacode.environments import get_environment
from gemmacode.models import get_model
from gemmacode.run.utilities.config import configure_if_first_time
from gemmacode.utils.serialize import UNSET, recursive_merge

DEFAULT_CONFIG_FILE = Path(os.getenv("MSWEA_MINI_CONFIG_PATH", builtin_config_dir / "mini.yaml"))
DEFAULT_OUTPUT_FILE = global_config_dir / "last_mini_run.traj.json"


_HELP_TEXT = """Run gemma-code in your local environment.

[not dim]
More information about the usage: [bold green]https://gemma-code.com/latest/usage/mini/[/bold green]
[/not dim]

The model is selected automatically by the codebase.
"""

_CONFIG_SPEC_HELP_TEXT = """Path to config files, filenames, or key-value pairs.

[bold red]IMPORTANT:[/bold red] [red]If you set this option, the default config file will not be used.[/red]
So you need to explicitly set it e.g., with [bold green]-c mini.yaml <other options>[/bold green]

Multiple configs will be recursively merged.

Examples:

[bold red]-c model.model_kwargs.temperature=0[/bold red] [red]You forgot to add the default config file! See above.[/red]

[bold green]-c mini.yaml -c model.model_kwargs.temperature=0.5[/bold green]

[bold green]-c swebench.yaml agent.mode=yolo[/bold green]
"""

console = Console(highlight=False)
app = typer.Typer(rich_markup_mode="rich")


# fmt: off
@app.command(help=_HELP_TEXT)
def main(
    model_name: str | None = typer.Option(None, "-m", "--model", help="Model to use", hidden=True),
    model_class: str | None = typer.Option(
        None,
        "--model-class",
        help="Model class to use (e.g., 'litellm' or 'gemmacode.models.litellm_model.LitellmModel')",
        hidden=True,
        rich_help_panel="Advanced",
    ),
    agent_class: str | None = typer.Option(None, "--agent-class", help="Agent class to use (e.g., 'interactive' or 'gemmacode.agents.interactive.InteractiveAgent')", rich_help_panel="Advanced"),
    environment_class: str | None = typer.Option(None, "--environment-class", help="Environment class to use (e.g., 'local' or 'gemmacode.environments.local.LocalEnvironment')", rich_help_panel="Advanced"),
    task: str | None = typer.Option(None, "-t", "--task", help="Task/problem statement", show_default=False),
    yolo: bool = typer.Option(False, "-y", "--yolo", help="Run without confirmation"),
    cost_limit: float | None = typer.Option(None, "-l", "--cost-limit", help="Cost limit. Set to 0 to disable."),
    config_spec: list[str] = typer.Option([str(DEFAULT_CONFIG_FILE)], "-c", "--config", help=_CONFIG_SPEC_HELP_TEXT),
    output: Path | None = typer.Option(DEFAULT_OUTPUT_FILE, "-o", "--output", help="Output trajectory file"),
    exit_immediately: bool = typer.Option(False, "--exit-immediately", help="Exit immediately when the agent wants to finish instead of prompting.", rich_help_panel="Advanced"),
) -> Any:
    # fmt: on
    configure_if_first_time()

    # Build the config from the command line arguments
    console.print(f"Building agent config from specs: [bold green]{config_spec}[/bold green]")
    configs = [get_config_from_spec(spec) for spec in config_spec]
    configs.append({
        "run": {
            "task": task or UNSET,
        },
        "agent": {
            "agent_class": agent_class or UNSET,
            "mode": "yolo" if yolo else UNSET,
            "cost_limit": cost_limit or UNSET,
            "confirm_exit": False if exit_immediately else UNSET,
            "output_path": output or UNSET,
        },
        "environment": {
            "environment_class": environment_class or UNSET,
        },
    })
    config = recursive_merge(*configs)

    if (run_task := config.get("run", {}).get("task", UNSET)) is UNSET:
        console.print("[bold yellow]What do you want to do?")
        run_task = _multiline_prompt()
        console.print("[bold green]Got that, thanks![/bold green]")

    model = get_model(config=config.get("model", {}))
    env = get_environment(config.get("environment", {}), default_type="local")
    agent = get_agent(model, env, config.get("agent", {}), default_type="interactive")
    agent.run(run_task)
    if (output_path := config.get("agent", {}).get("output_path")):
        console.print(f"Saved trajectory to [bold green]'{output_path}'[/bold green]")
    return agent


if __name__ == "__main__":
    app()
