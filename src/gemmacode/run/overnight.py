"""Overnight orchestration pipeline for autonomous task decomposition and execution."""

import json
import logging
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from gemmacode.config import get_config_from_spec
from gemmacode.models import get_model
from gemmacode.agents.orchestrator import OrchestratorAgent
from gemmacode.agents.subtask_runner import SubtaskRunner
from gemmacode.orchestrator import (
    DecompositionPlan,
    SubtaskResult,
    SubtaskStatus,
    topological_sort,
)
from gemmacode.repomap import build_repo_map

logger = logging.getLogger("overnight")
console = Console()

app = typer.Typer(help="Autonomous overnight task orchestration pipeline")


def load_plan(path: Path) -> DecompositionPlan:
    """Load a saved DecompositionPlan from JSON.

    Args:
        path: Path to the plan.json file.

    Returns:
        Loaded DecompositionPlan.
    """
    with open(path) as f:
        data = json.load(f)
    return DecompositionPlan.model_validate(data)


def save_result(result: SubtaskResult, output_dir: Path) -> None:
    """Save a subtask result to JSON.

    Args:
        result: The subtask result to save.
        output_dir: Directory to save the result in.
    """
    filename = f"result_{result.spec.id}.json"
    filepath = output_dir / filename
    with open(filepath, "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    logger.info(f"Saved result for {result.spec.id} to {filepath}")


@app.command()
def main(
    task: str = typer.Option(..., "--task", "-t", help="Main task description"),
    output_dir: Path = typer.Option(
        Path.home() / ".config" / "gemma-code" / "overnight",
        "--output",
        "-o",
        help="Directory for output files",
    ),
    heuristics: list[str] = typer.Option(
        None,
        "--heuristics",
        "-H",
        help="Heuristic categories to apply (can be repeated)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only decompose task, don't execute subtasks",
    ),
) -> None:
    """Execute overnight orchestration pipeline.

    This command orchestrates autonomous task decomposition and execution:
    1. Decomposes the task into subtasks using a large model (DeepSeek)
    2. Executes each subtask with a smaller model (Gemma/Qwen)
    3. Tracks results and generates a summary
    """
    # Setup
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    console.print("[bold blue]🌙 Overnight Orchestration Pipeline[/bold blue]")
    console.print(f"Task: {task}")
    console.print(f"Output: {output_dir}")

    # Step 1: Build repo map
    console.print("\n[bold]Step 1: Building repository map...[/bold]")
    repo_root = Path.cwd()
    repo_map_artifacts = build_repo_map(repo_root)
    repo_map = repo_map_artifacts.repo_map_full
    console.print(f"✓ Repository map built ({len(repo_map)} chars)")

    # Step 2: Decompose task
    console.print("\n[bold]Step 2: Decomposing task...[/bold]")
    try:
        orchestrator_config = get_config_from_spec("overnight.yaml")
        orchestrator_model = get_model(
            orchestrator_config.get("model", {}).get("model_name", "deepseek/deepseek-chat")
        )
        orchestrator = OrchestratorAgent(
            orchestrator_model,
            heuristics_applied=heuristics,
        )
        plan = orchestrator.decompose(task, repo_map)
        console.print(f"✓ Decomposed into {len(plan.subtasks)} subtasks")

        # Save plan
        plan_path = output_dir / "plan.json"
        with open(plan_path, "w") as f:
            json.dump(plan.model_dump(), f, indent=2)
        console.print(f"✓ Plan saved to {plan_path}")

    except Exception as e:
        console.print(f"[red]✗ Decomposition failed: {e}[/red]")
        raise typer.Exit(1)

    # Step 3: Handle dry-run
    if dry_run:
        console.print("\n[bold yellow]Dry-run mode: stopping after decomposition[/bold yellow]")
        console.print("\n[bold]Decomposition Plan:[/bold]")
        for i, subtask in enumerate(plan.subtasks, 1):
            console.print(f"{i}. {subtask.title} ({subtask.estimated_complexity})")
            if subtask.dependencies:
                console.print(f"   Dependencies: {', '.join(subtask.dependencies)}")
        return

    # Step 4: Sort subtasks
    console.print("\n[bold]Step 3: Sorting subtasks by dependencies...[/bold]")
    try:
        sorted_subtasks = topological_sort(plan.subtasks)
        console.print(f"✓ Topologically sorted {len(sorted_subtasks)} subtasks")
    except Exception as e:
        console.print(f"[red]✗ Topological sort failed: {e}[/red]")
        raise typer.Exit(1)

    # Step 5: Execute subtasks
    console.print("\n[bold]Step 4: Executing subtasks...[/bold]")
    results = []
    executor_config = get_config_from_spec("overnight.yaml")

    for i, subtask in enumerate(sorted_subtasks, 1):
        console.print(f"\n[cyan][{i}/{len(sorted_subtasks)}] {subtask.title}[/cyan]")
        try:
            executor_model = get_model(
                executor_config.get("model", {}).get("model_name", "ollama/gemma:7b")
            )
            runner = SubtaskRunner(executor_model)
            result = runner.run(subtask)
            results.append(result)

            # Save individual result
            save_result(result, output_dir)

            # Print result
            status_symbol = "✓" if result.status == SubtaskStatus.PASSED else "✗"
            status_color = "green" if result.status == SubtaskStatus.PASSED else "red"
            console.print(f"{status_symbol} [bold {status_color}]{result.status.value}[/bold {status_color}]")

            if result.error:
                console.print(f"[red]Error: {result.error}[/red]")

        except Exception as e:
            console.print(f"[red]✗ Execution failed: {e}[/red]")
            result = SubtaskResult(
                spec=subtask,
                status=SubtaskStatus.FAILED,
                error=f"Execution error: {str(e)}",
                test_outputs=[],
            )
            results.append(result)

    # Step 6: Generate summary
    console.print("\n[bold]Step 5: Generating summary...[/bold]")
    summary = {
        "task": task,
        "timestamp": datetime.now().isoformat(),
        "total_subtasks": len(results),
        "passed": sum(1 for r in results if r.status == SubtaskStatus.PASSED),
        "failed": sum(1 for r in results if r.status == SubtaskStatus.FAILED),
        "results": [
            {
                "id": r.spec.id,
                "title": r.spec.title,
                "status": r.status.value,
                "error": r.error,
            }
            for r in results
        ],
    }

    # Print summary table
    table = Table(title="Overnight Execution Summary")
    table.add_column("Task ID", style="cyan")
    table.add_column("Title", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Error", style="red")

    for result in results:
        status_color = "green" if result.status == SubtaskStatus.PASSED else "red"
        table.add_row(
            result.spec.id,
            result.spec.title,
            f"[bold {status_color}]{result.status.value}[/bold {status_color}]",
            result.error or "-",
        )

    console.print(table)

    # Save summary
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    console.print(f"\n✓ Summary saved to {summary_path}")

    # Final status
    if summary["failed"] == 0:
        console.print("\n[bold green]🎉 All subtasks passed![/bold green]")
    else:
        console.print(
            f"\n[bold yellow]⚠️  {summary['failed']}/{summary['total_subtasks']} subtasks failed[/bold yellow]"
        )


if __name__ == "__main__":
    app()
