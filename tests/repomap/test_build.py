from __future__ import annotations

import subprocess
from pathlib import Path

from gemmacode.repomap import build_repo_index, load_repo_index, should_rebuild


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)


def _write(repo_root: Path, relative_path: str, content: str) -> None:
    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_build_repo_index_generates_repo_map_and_parses_symbols(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    _write(
        repo_root,
        ".gitignore",
        "\n".join(
            [
                "build/",
                ".gemmacode/",
            ]
        ),
    )
    _write(
        repo_root,
        "pyproject.toml",
        """[project]\nname = \"demo\"\nversion = \"0.1.0\"\n""",
    )
    _write(
        repo_root,
        "src/helper.py",
        '''"""Helper utilities."""\n\n\ndef util(value):\n    return value\n''',
    )
    _write(
        repo_root,
        "src/app.py",
        '''"""Application service layer."""\n\nfrom .helper import util\n\nclass AuthService:\n    def login(self, user, password):\n        return util(user)\n\n    def refresh_token(self, token):\n        return token\n\ndef build_app(name, config=None):\n    return name\n''',
    )
    _write(
        repo_root,
        "tests/test_app.py",
        """def test_placeholder():\n    assert True\n""",
    )
    _write(
        repo_root,
        "build/generated.py",
        """print('skip me')\n""",
    )

    artifacts = build_repo_index(repo_root, max_files=2, budget_chars=4_000)

    assert artifacts.index_path.exists()
    assert artifacts.repo_map_path.exists()
    assert artifacts.repo_map_full_path.exists()
    assert artifacts.index_path.parent.name == ".gemmacode"
    assert artifacts.repo_map_path.parent.name == ".gemmacode"
    assert artifacts.repo_map_full_path.parent.name == ".gemmacode"

    index = load_repo_index(artifacts.index_path)
    app_record = next(file for file in index.files if file.path == "src/app.py")
    assert app_record.summary == "Application service layer."
    assert any(symbol.name == "AuthService" for symbol in app_record.symbols)
    assert any(symbol.signature == "login(self, user, password)" for symbol in app_record.symbols)
    assert "src/helper.py" in app_record.local_dependencies

    repo_map = artifacts.repo_map
    assert "pyproject.toml" in repo_map
    assert "src/app.py" in repo_map
    assert "tests/test_app.py" not in repo_map
    assert "build/generated.py" not in repo_map


def test_should_rebuild_uses_fingerprint(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    _write(repo_root, ".gitignore", ".gemmacode/\n")
    _write(repo_root, "src/app.py", "def run():\n    return 1\n")

    artifacts = build_repo_index(repo_root)
    assert not should_rebuild(repo_root, index_path=artifacts.index_path)

    _write(repo_root, "src/app.py", "def run():\n    return 2\n")
    assert should_rebuild(repo_root, index_path=artifacts.index_path)
