"""Discovery and fingerprint helpers for RepoMap generation."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

REPO_MAP_INDEX_FILE = "repo_index.json"
REPO_MAP_FILE = "repo_map.md"
REPO_MAP_FULL_FILE = "repo_map_full.md"
REPOMAP_DIR_NAME = ".gemmacode"

CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
TEXT_EXTENSIONS = {".md", ".rst", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
IMPORTANT_FILENAMES = {
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
IGNORED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    REPOMAP_DIR_NAME,
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "coverage",
    "site",
    ".tox",
    ".nox",
    ".pytest_cache",
}
IGNORED_SUFFIXES = (".pyc", ".pyo", ".pyd", ".so", ".o", ".obj", ".class", ".png", ".jpg", ".jpeg", ".gif", ".pdf")


def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip()).resolve()
    except Exception:
        return start


def _is_ignored_part(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts)


def is_relevant_file(path: Path) -> bool:
    if _is_ignored_part(path):
        return False
    if path.suffix.lower().endswith(IGNORED_SUFFIXES):
        return False
    if path.name in IMPORTANT_FILENAMES:
        return True
    if path.suffix in CODE_EXTENSIONS or path.suffix in TEXT_EXTENSIONS:
        return True
    if path.name.startswith("Dockerfile"):
        return True
    return False


def discover_repo_files(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [repo_root / line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [path for path in files if path.exists() and path.is_file() and is_relevant_file(path.relative_to(repo_root))]
    except Exception:
        discovered: list[Path] = []
        for root, _dirs, filenames in os.walk(repo_root):
            root_path = Path(root)
            for filename in filenames:
                path = root_path / filename
                if is_relevant_file(path.relative_to(repo_root)):
                    discovered.append(path)
        return discovered


def calculate_fingerprint(repo_root: Path, files: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(repo_root).as_posix()):
        rel_path = path.relative_to(repo_root).as_posix()
        stat_result = path.stat()
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(stat_result.st_size).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(int(stat_result.st_mtime_ns)).encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()
