from __future__ import annotations

import subprocess
from pathlib import Path

from gemmacode.repomap import build_repo_index
from gemmacode.research import build_research_plan, save_research_plan


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)


def _write(repo_root: Path, relative_path: str, content: str) -> None:
    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_build_research_plan_prefers_explicit_file(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    _write(repo_root, ".gitignore", ".gemmacode/\n")
    _write(repo_root, "pyproject.toml", "[project]\nname = 'demo'\nversion = '0.1.0'\n")
    _write(repo_root, "src/auth/service.py", '"""Authentication service."""\n\nclass AuthService:\n    pass\n')
    _write(repo_root, "src/users/repo.py", '"""User repository."""\n\nclass UserRepository:\n    pass\n')
    _write(repo_root, "tests/test_auth.py", "def test_placeholder():\n    assert True\n")

    artifacts = build_repo_index(repo_root, budget_chars=4_000)
    plan = build_research_plan(
        task="Edit src/auth/service.py to improve login",
        repo_index=artifacts.index,
        repo_root=repo_root,
        repo_map_path=artifacts.repo_map_path,
        repo_map_full_path=artifacts.repo_map_full_path,
        mode="balanced",
    )

    assert plan.task_kind == "explicit_file"
    assert plan.allow_early_implementation is True
    assert plan.budgets["min_relevant_searches"] == 0
    assert plan.budgets["min_open_reads"] == 0
    assert plan.shortlist[0].path == "src/auth/service.py"
    assert "src/auth/service.py" in plan.queries

    json_path, md_path = save_research_plan(plan, repo_root=repo_root)
    assert json_path.exists()
    assert md_path.exists()
    assert "RepoMap Research Plan" in md_path.read_text()


def test_build_research_plan_prioritizes_central_files(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    _write(repo_root, ".gitignore", ".gemmacode/\n")
    _write(repo_root, "README.md", "# Demo\n")
    _write(repo_root, "pyproject.toml", "[project]\nname = 'demo'\nversion = '0.1.0'\n")
    _write(repo_root, "src/app.py", '"""Application entrypoint."""\n\nfrom .auth import service\n')
    _write(repo_root, "src/auth/service.py", '"""Authentication service."""\n\nclass AuthService:\n    pass\n')
    _write(repo_root, "src/users/repo.py", '"""User repository."""\n\nclass UserRepository:\n    pass\n')

    artifacts = build_repo_index(repo_root, budget_chars=4_000)
    plan = build_research_plan(
        task="Improve the authentication flow",
        repo_index=artifacts.index,
        repo_root=repo_root,
        repo_map_path=artifacts.repo_map_path,
        repo_map_full_path=artifacts.repo_map_full_path,
        mode="strict",
    )

    assert plan.task_kind in {"narrow", "broad"}
    assert plan.budgets["max_searches"] >= 3
    assert plan.budgets["min_open_reads"] >= 1
    assert plan.shortlist
    assert any(candidate.path in {"README.md", "pyproject.toml", "src/app.py"} for candidate in plan.shortlist)
