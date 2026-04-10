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
from gemmacode.research import build_research_plan, save_research_plan
from gemmacode.runtime import get_local_model_base_url, get_local_model_name
from gemmacode.repomap import build_repo_map, find_repo_root, load_repo_map
from gemmacode.run.utilities.config import configure_if_first_time
from gemmacode.utils.serialize import UNSET, recursive_merge
from gemmacode.utils.status import build_status_text

DEFAULT_CONFIG_FILE = Path(os.getenv("MSWEA_MINI_CONFIG_PATH", builtin_config_dir / "mini.yaml"))
DEFAULT_OUTPUT_FILE = global_config_dir / "last_mini_run.traj.json"


_HELP_TEXT = """Run gemma-code in your local environment.

[not dim]
More information about the usage: [bold green]https://gemma-code.com/latest/usage/mini/[/bold green]
[/not dim]

The model is selected automatically by the codebase.
The agent will inspect the RepoMap first, shortlist candidates, run rg, and only then edit.
Type [bold green]/init[/bold green] to build the structural RepoMap without calling the model.
"""

_CONFIG_SPEC_HELP_TEXT = """Path to config files, filenames, or key-value pairs.

[bold red]IMPORTANT:[/bold red] [red]If you set this option, the default config file will not be used.[/red]
So you need to explicitly set it e.g., with [bold green]-c mini.yaml <other options>[/bold green]

Multiple configs will be recursively merged.

Examples:

[bold red]-c model.model_kwargs.temperature=0[/bold red] [red]You forgot to add the default config file! See above.[/red]

[bold green]-c mini.yaml -c model.model_kwargs.temperature=0.5[/bold green]

[bold green]-c swebench.yaml agent.mode=yolo[/bold green]

[bold green]-c no-yolo[/bold green] to force confirmation even though yolo is enabled by default.

[bold green]-c no-repo-map[/bold green] to disable RepoMap injection into the initial prompt.

[bold green]--research-mode strict|balanced|off[/bold green] to control how strongly the research gate is enforced.
"""

console = Console(highlight=False)
app = typer.Typer(rich_markup_mode="rich")


def _split_special_config_specs(config_spec: list[str]) -> tuple[list[str], bool, bool]:
    cleaned_specs: list[str] = []
    no_yolo_requested = False
    no_repo_map_requested = False
    for spec in config_spec:
        if not isinstance(spec, str):
            cleaned_specs.append(spec)
            continue
        normalized = spec.strip().lower().replace("_", "-")
        if normalized == "no-yolo":
            no_yolo_requested = True
            continue
        if normalized == "no-repo-map":
            no_repo_map_requested = True
            continue
        cleaned_specs.append(spec)
    return cleaned_specs, no_yolo_requested, no_repo_map_requested


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
    yolo: bool = typer.Option(True, "-y", "--yolo/--no-yolo", help="Run without confirmation. Enabled by default."),
    repo_map: bool = typer.Option(True, "--repo-map/--no-repo-map", help="Inject the RepoMap context into the initial prompt. Enabled by default."),
    research_mode: str = typer.Option("balanced", "--research-mode", help="Control the research gate: strict, balanced, or off."),
    cost_limit: float | None = typer.Option(None, "-l", "--cost-limit", help="Cost limit. Set to 0 to disable."),
    config_spec: list[str] = typer.Option([str(DEFAULT_CONFIG_FILE)], "-c", "--config", help=_CONFIG_SPEC_HELP_TEXT),
    output: Path | None = typer.Option(DEFAULT_OUTPUT_FILE, "-o", "--output", help="Output trajectory file"),
    exit_immediately: bool = typer.Option(False, "--exit-immediately", help="Exit immediately when the agent wants to finish instead of prompting.", rich_help_panel="Advanced"),
) -> Any:
    # fmt: on
    console.print(build_status_text("Inicializando gemma-code", "pipeline local-first", color="cyan"))
    research_mode_value = research_mode if isinstance(research_mode, str) else "balanced"

    # Build the config from the command line arguments
    config_spec, no_yolo_requested, no_repo_map_requested = _split_special_config_specs(config_spec)
    yolo = yolo and not no_yolo_requested
    repo_map = repo_map and not no_repo_map_requested
    console.print(build_status_text("Carregando configuração", f"{len(config_spec)} spec(s)", color="blue"))
    configs = [get_config_from_spec(spec) for spec in config_spec]
    configs.append(
        {
            "run": {
                "task": task or UNSET,
            },
            "agent": {
                "agent_class": agent_class or UNSET,
                "mode": "yolo" if yolo else "confirm",
                "research_mode": research_mode_value or UNSET,
                "cost_limit": cost_limit or UNSET,
                "confirm_exit": False if exit_immediately else UNSET,
                "output_path": output or UNSET,
            },
            "environment": {
                "environment_class": environment_class or UNSET,
            },
        }
    )
    config = recursive_merge(*configs)

    if (run_task := config.get("run", {}).get("task", UNSET)) is UNSET:
        console.print("[bold yellow]What do you want to do?[/bold yellow]")
        console.print(
            "[dim]Enter envia. Shift+Enter quebra linha. Use --no-yolo ou -c no-yolo para pedir confirmação. "
            "Type /init to build the RepoMap without calling the model.[/dim]"
        )
        run_task = _multiline_prompt()
        console.print("[bold green]Got that, thanks![/bold green]")

    repo_root = find_repo_root(Path.cwd())
    if str(run_task).strip() == "/init":
        console.print(build_status_text("Construindo RepoMap", str(repo_root), color="cyan"))
        artifacts = build_repo_map(repo_root)
        console.print(build_status_text("RepoMap pronto", f"{artifacts.repo_map_path} • {artifacts.repo_map_full_path}", color="green"))
        return artifacts

    configure_if_first_time()

    console.print(
        build_status_text(
            "Montando agentes",
            f"{get_local_model_name()} @ {get_local_model_base_url()}",
            color="magenta",
        )
    )
    model = get_model(config=config.get("model", {}))
    env = get_environment(config.get("environment", {}), default_type="local")
    agent = get_agent(model, env, config.get("agent", {}), default_type="interactive")
    console.print(build_status_text("Preparando RepoMap", str(repo_root), color="cyan"))
    artifacts = load_repo_map(repo_root=repo_root)
    repo_map_state = "Reutilizado" if artifacts.reused else "Atualizado"
    console.print(
        build_status_text(
            f"RepoMap {repo_map_state.lower()}",
            f"{artifacts.repo_map_path} • {artifacts.repo_map_full_path}",
            color="green",
        )
    )

    research_plan = build_research_plan(
        task=str(run_task),
        repo_index=artifacts.index,
        repo_root=repo_root,
        repo_map_path=artifacts.repo_map_path,
        repo_map_full_path=artifacts.repo_map_full_path,
        mode=str(config.get("agent", {}).get("research_mode", research_mode_value)),
    )
    research_json_path, research_md_path = save_research_plan(research_plan, repo_root=repo_root)
    console.print(
        build_status_text(
            "Plano de pesquisa pronto",
            f"{research_plan.task_kind} • {research_plan.budgets.get('max_searches', 0)} buscas • {research_plan.budgets.get('max_open_reads', 0)} leituras",
            color="cyan",
        )
    )

    template_vars = getattr(agent, "extra_template_vars", None)
    if not isinstance(template_vars, dict):
        template_vars = {}
        setattr(agent, "extra_template_vars", template_vars)
    if repo_map:
        template_vars["repo_map"] = artifacts.repo_map
        template_vars["repo_map_full"] = artifacts.repo_map_full
        template_vars["repo_map_path"] = str(artifacts.repo_map_path)
        template_vars["repo_map_full_path"] = str(artifacts.repo_map_full_path)
    else:
        template_vars.setdefault("repo_map", "")
        template_vars.setdefault("repo_map_full", "")
    template_vars["repo_research"] = research_plan.to_markdown()
    template_vars["repo_research_path"] = str(research_md_path)
    template_vars["repo_research_full_path"] = str(research_json_path)
    template_vars["research_mode"] = research_plan.mode
    template_vars["research_phase"] = research_plan.phase
    template_vars["implementation_phase"] = "implementation"

    console.print(build_status_text("Executando agente", color="green"))
    agent.run(run_task, research_plan=research_plan.to_dict())
    if (output_path := config.get("agent", {}).get("output_path")):
        console.print(f"Saved trajectory to [bold green]'{output_path}'[/bold green]")
    return agent


if __name__ == "__main__":
    app()
