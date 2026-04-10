"""This is the simplest possible example of how to use gemma-code with python bindings.
For a more complete example, see mini.py
"""

import logging
from pathlib import Path

import typer
import yaml

from gemmacode import package_dir
from gemmacode.agents.default import DefaultAgent
from gemmacode.environments.local import LocalEnvironment
from gemmacode.models import get_model

app = typer.Typer()


@app.command()
def main(
    task: str = typer.Option(..., "-t", "--task", help="Task/problem statement", show_default=False, prompt=True),
) -> DefaultAgent:
    logging.basicConfig(level=logging.DEBUG)
    agent = DefaultAgent(
        get_model(),
        LocalEnvironment(),
        **yaml.safe_load(Path(package_dir / "config" / "default.yaml").read_text())["agent"],
    )
    agent.run(task)
    return agent


if __name__ == "__main__":
    app()
