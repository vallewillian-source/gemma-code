"""Selection and scoring helpers for RepoMap generation."""

from __future__ import annotations

from pathlib import Path

from .models import RepoFileRecord, RepoIndex

ROOT_PRIORITY_FILENAMES = {
    "README.md",
    "README.rst",
    "README.txt",
    "pyproject.toml",
    "package.json",
    "mkdocs.yml",
    "mkdocs.yaml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "Makefile",
    "Dockerfile",
}
ENTRYPOINT_FILENAMES = {"__main__.py", "main.py", "app.py", "cli.py", "server.py", "index.py"}
DEPRIORITIZED_PARTS = {
    "tests",
    "test",
    "testing",
    "fixtures",
    "fixture",
    "mocks",
    "mock",
    "generated",
    "generation",
    "migrations",
    "migration",
    "build",
    "dist",
    "node_modules",
    "coverage",
    "__pycache__",
}
CENTRAL_PARTS = {"src", "app", "lib", "pkg", "packages"}


def _score_file(file: RepoFileRecord, incoming_refs: int) -> float:
    path = Path(file.path)
    score = 0.0
    if path.name in ROOT_PRIORITY_FILENAMES:
        score += 250
    if path.name in ENTRYPOINT_FILENAMES:
        score += 220
    if path.parent == Path("."):
        score += 70
    if any(part in CENTRAL_PARTS for part in path.parts):
        score += 120
    if any(part in DEPRIORITIZED_PARTS for part in path.parts):
        score -= 180
    if file.symbol_count:
        score += min(100, file.symbol_count * 8)
    if file.local_dependencies:
        score += min(80, len(file.local_dependencies) * 10)
    if file.imports:
        score += min(60, len(file.imports) * 6)
    if incoming_refs:
        score += min(140, incoming_refs * 12)
    if file.line_count <= 40:
        score += 20
    if file.file_kind != "code":
        score += 15
    return score


def _is_must_include(file: RepoFileRecord) -> bool:
    path = Path(file.path)
    return path.name in ROOT_PRIORITY_FILENAMES or path.name in ENTRYPOINT_FILENAMES


def select_repo_map_files(
    index: RepoIndex,
    *,
    max_files: int = 80,
) -> list[RepoFileRecord]:
    incoming_refs: dict[str, int] = {}
    for file in index.files:
        for dep in file.local_dependencies:
            incoming_refs[dep] = incoming_refs.get(dep, 0) + 1

    scored_files: list[RepoFileRecord] = []
    for file in index.files:
        incoming = incoming_refs.get(file.path, 0)
        file.score = _score_file(file, incoming)
        scored_files.append(file)

    must_include = [file for file in scored_files if _is_must_include(file)]
    must_include_paths = {file.path for file in must_include}
    remaining = [file for file in scored_files if file.path not in must_include_paths]
    remaining.sort(key=lambda item: (item.score, item.symbol_count, len(item.local_dependencies), -len(item.path)), reverse=True)
    must_include.sort(key=lambda item: (item.score, item.symbol_count, len(item.local_dependencies), -len(item.path)), reverse=True)

    selected: list[RepoFileRecord] = []
    for file in must_include + remaining:
        if file.path in {existing.path for existing in selected}:
            continue
        selected.append(file)
        if len(selected) >= max_files:
            break
    return selected
