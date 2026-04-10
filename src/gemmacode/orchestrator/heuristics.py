"""Heuristics loader and prompt builder for orchestrator guidance."""

from pathlib import Path

import yaml


HEURISTICS_DIR = Path(__file__).parent / "heuristics"


def load_all_heuristics() -> dict[str, dict]:
    """Load all heuristics YAML files from the heuristics directory.

    Returns a mapping of {filename_base: {name, description, rules}}.
    """
    heuristics = {}
    for yaml_file in sorted(HEURISTICS_DIR.glob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        heuristics[yaml_file.stem] = data
    return heuristics


def build_heuristics_prompt(heuristics_applied: list[str] | None = None) -> str:
    """Build a formatted prompt from heuristics rules.

    Args:
        heuristics_applied: List of heuristics file names to include (e.g., ['python_project', 'testing_patterns']).
                          If None, include all heuristics.

    Returns:
        A formatted string containing all applicable heuristics rules, suitable for injection into agent prompts.
    """
    all_heuristics = load_all_heuristics()

    # Determine which heuristics to include
    if heuristics_applied is None:
        heuristics_to_use = all_heuristics
    else:
        heuristics_to_use = {k: all_heuristics[k] for k in heuristics_applied if k in all_heuristics}

    # Build the prompt
    sections = []
    for heuristic_name in sorted(heuristics_to_use.keys()):
        heuristic = heuristics_to_use[heuristic_name]
        section = _format_heuristic_section(heuristic_name, heuristic)
        sections.append(section)

    return "\n".join(sections)


def _format_heuristic_section(name: str, heuristic: dict) -> str:
    """Format a single heuristic into a readable section.

    Args:
        name: The heuristic file name (e.g., 'python_project')
        heuristic: The loaded YAML data dict with 'name', 'description', 'rules'

    Returns:
        A formatted string section for this heuristic.
    """
    title = heuristic["name"]
    description = heuristic["description"]
    rules = heuristic["rules"]

    # Format title: replace underscores with spaces and titlecase
    formatted_title = title.replace("_", " ").title()

    lines = [
        f"## {formatted_title}",
        f"_{description}_",
        "",
    ]

    for rule in rules:
        rule_id = rule["id"]
        rule_desc = rule["description"]
        lines.append(f"### {rule_id}")
        lines.append(rule_desc)
        if "example" in rule:
            lines.append(f"_Example: {rule['example']}_")
        lines.append("")

    return "\n".join(lines)
