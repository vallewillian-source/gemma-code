"""High-level RepoMap build and loading helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .discovery import (
    REPO_MAP_FILE,
    REPO_MAP_FULL_FILE,
    REPO_MAP_INDEX_FILE,
    REPOMAP_DIR_NAME,
    calculate_fingerprint,
    discover_repo_files,
    find_repo_root,
)
from .formatting import format_repo_map
from .models import RepoFileRecord, RepoIndex, RepoMapArtifacts, RepoSymbol
from .parsing import parse_repo_file

DEFAULT_REPOMAP_BUDGET_CHARS = int(os.getenv("GEMMACODE_REPOMAP_MAX_CHARS", "14000"))
DEFAULT_REPOMAP_FULL_BUDGET_CHARS = int(os.getenv("GEMMACODE_REPOMAP_FULL_MAX_CHARS", "40000"))
DEFAULT_REPOMAP_MAX_FILES = int(os.getenv("GEMMACODE_REPOMAP_MAX_FILES", "80"))
DEFAULT_REPOMAP_MAX_SYMBOLS = int(os.getenv("GEMMACODE_REPOMAP_MAX_SYMBOLS", "5"))
DEFAULT_REPOMAP_FULL_MAX_SYMBOLS = int(os.getenv("GEMMACODE_REPOMAP_FULL_MAX_SYMBOLS", "12"))


def _resolve_imports(files: list[RepoFileRecord]) -> None:
    module_lookup: dict[str, str] = {}
    path_module_lookup: dict[str, str] = {}
    for file in files:
        rel = Path(file.path)
        module_name = rel.with_suffix("").as_posix().replace("/", ".")
        module_lookup[module_name] = file.path
        path_module_lookup[file.path] = module_name
        if rel.name == "__init__.py":
            package_name = rel.parent.as_posix().replace("/", ".")
            if package_name and package_name != ".":
                module_lookup[package_name] = file.path
                path_module_lookup[file.path] = package_name
        if rel.as_posix().startswith("src/"):
            src_module = rel.as_posix()[4:].removesuffix(".py").replace("/", ".")
            module_lookup[src_module] = file.path
            path_module_lookup[file.path] = src_module
            if rel.name == "__init__.py":
                package_name = rel.parent.as_posix()[4:].replace("/", ".")
                if package_name:
                    module_lookup[package_name] = file.path
                    path_module_lookup[file.path] = package_name

    def resolve_python_import(current_path: str, imported: str) -> str | None:
        imported = imported.strip()
        if not imported:
            return None
        if imported.startswith("."):
            current_module = path_module_lookup.get(current_path, Path(current_path).with_suffix("").as_posix().replace("/", "."))
            current_package = current_module.rsplit(".", 1)[0] if "." in current_module else current_module
            dots = len(imported) - len(imported.lstrip("."))
            remainder = imported.lstrip(".")
            base = current_package.split(".")[:-dots] if dots > 0 else current_package.split(".")
            base_module = ".".join(base) if base else ""
            candidate = ".".join(part for part in [base_module, remainder] if part)
            if candidate in module_lookup:
                return module_lookup[candidate]
            if base_module and base_module in module_lookup:
                return module_lookup[base_module]
            return None
        for candidate in (imported, imported.split(".", 1)[0]):
            if candidate in module_lookup:
                return module_lookup[candidate]
        return None

    for file in files:
        if file.language != "python":
            continue
        resolved: list[str] = []
        for imported in file.imports:
            dep = resolve_python_import(file.path, imported)
            if dep and dep != file.path:
                resolved.append(dep)
        file.local_dependencies = sorted(set(resolved))

    # Best-effort JS/TS relative import resolution
    for file in files:
        if file.language not in {"javascript", "typescript"}:
            continue
        resolved: list[str] = []
        for imported in file.imports:
            if not imported.startswith("."):
                continue
            candidate_paths = []
            base = Path(file.path).parent / imported
            if base.suffix:
                candidate_paths.append(base.as_posix())
            else:
                candidate_paths.extend(
                    [
                        f"{base.as_posix()}.js",
                        f"{base.as_posix()}.jsx",
                        f"{base.as_posix()}.ts",
                        f"{base.as_posix()}.tsx",
                        f"{base.as_posix()}/index.js",
                        f"{base.as_posix()}/index.ts",
                    ]
                )
            for candidate in candidate_paths:
                if any(candidate == other.path for other in files):
                    resolved.append(candidate)
                    break
        file.local_dependencies = sorted(set(resolved))


def _serialize_index(index: RepoIndex) -> dict[str, Any]:
    return index.to_dict()


def build_repo_index(
    repo_root: Path | None = None,
    *,
    index_path: Path | None = None,
    repo_map_path: Path | None = None,
    repo_map_full_path: Path | None = None,
    budget_chars: int = DEFAULT_REPOMAP_BUDGET_CHARS,
    full_budget_chars: int = DEFAULT_REPOMAP_FULL_BUDGET_CHARS,
    max_files: int = DEFAULT_REPOMAP_MAX_FILES,
    symbol_limit: int = DEFAULT_REPOMAP_MAX_SYMBOLS,
    full_symbol_limit: int = DEFAULT_REPOMAP_FULL_MAX_SYMBOLS,
) -> RepoMapArtifacts:
    repo_root = find_repo_root(repo_root)
    repomap_dir = repo_root / REPOMAP_DIR_NAME
    index_path = index_path or repomap_dir / REPO_MAP_INDEX_FILE
    repo_map_path = repo_map_path or repomap_dir / REPO_MAP_FILE
    repo_map_full_path = repo_map_full_path or repomap_dir / REPO_MAP_FULL_FILE
    repomap_dir.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    repo_map_path.parent.mkdir(parents=True, exist_ok=True)
    repo_map_full_path.parent.mkdir(parents=True, exist_ok=True)
    discovered_files = discover_repo_files(repo_root)
    fingerprint = calculate_fingerprint(repo_root, discovered_files)

    records = [parse_repo_file(repo_root, path) for path in discovered_files]
    _resolve_imports(records)
    index = RepoIndex(repo_root=str(repo_root), fingerprint=fingerprint, files=records)
    index_payload = _serialize_index(index)
    index_path.write_text(json.dumps(index_payload, indent=2, ensure_ascii=False))

    repo_map = format_repo_map(
        index,
        budget_chars=budget_chars,
        max_files=max_files,
        symbol_limit=symbol_limit,
        dependency_limit=5,
        include_all_files=False,
        title="Repo Map",
    )
    repo_map_path.write_text(repo_map)

    repo_map_full = format_repo_map(
        index,
        budget_chars=full_budget_chars,
        max_files=len(index.files),
        symbol_limit=full_symbol_limit,
        dependency_limit=8,
        include_all_files=True,
        title="Repo Map Full",
    )
    repo_map_full_path.write_text(repo_map_full)

    return RepoMapArtifacts(
        repo_root=repo_root,
        index=index,
        index_path=index_path,
        repo_map_path=repo_map_path,
        repo_map_full_path=repo_map_full_path,
        repo_map=repo_map,
        repo_map_full=repo_map_full,
    )


def build_repo_map(
    repo_root: Path | None = None,
    *,
    index_path: Path | None = None,
    repo_map_path: Path | None = None,
    repo_map_full_path: Path | None = None,
    budget_chars: int = DEFAULT_REPOMAP_BUDGET_CHARS,
    full_budget_chars: int = DEFAULT_REPOMAP_FULL_BUDGET_CHARS,
    max_files: int = DEFAULT_REPOMAP_MAX_FILES,
    symbol_limit: int = DEFAULT_REPOMAP_MAX_SYMBOLS,
    full_symbol_limit: int = DEFAULT_REPOMAP_FULL_MAX_SYMBOLS,
) -> RepoMapArtifacts:
    return build_repo_index(
        repo_root,
        index_path=index_path,
        repo_map_path=repo_map_path,
        repo_map_full_path=repo_map_full_path,
        budget_chars=budget_chars,
        full_budget_chars=full_budget_chars,
        max_files=max_files,
        symbol_limit=symbol_limit,
        full_symbol_limit=full_symbol_limit,
    )


def load_repo_index(index_path: Path) -> RepoIndex:
    payload = json.loads(index_path.read_text())
    metadata = payload.get("metadata", {})
    files = [
        RepoFileRecord(
            path=item.get("path", ""),
            language=item.get("language", "text"),
            summary=item.get("summary", ""),
            symbols=[RepoSymbol(**symbol) for symbol in item.get("symbols", [])],
            imports=list(item.get("imports", [])),
            local_dependencies=list(item.get("local_dependencies", [])),
            size=int(item.get("size", 0)),
            line_count=int(item.get("line_count", 0)),
            score=float(item.get("score", 0.0)),
            is_entrypoint=bool(item.get("is_entrypoint", False)),
            is_root_file=bool(item.get("is_root_file", False)),
            file_kind=item.get("file_kind", "code"),
        )
        for item in payload.get("files", [])
    ]
    return RepoIndex(
        repo_root=str(metadata.get("repo_root", index_path.parent)),
        fingerprint=str(metadata.get("fingerprint", "")),
        files=files,
        generated_at=str(metadata.get("generated_at", "")),
        version=str(metadata.get("version", "1")),
    )


def load_repo_map(
    repo_map_path: Path | None = None,
    *,
    repo_root: Path | None = None,
    force_rebuild: bool = False,
) -> RepoMapArtifacts:
    repo_root = find_repo_root(repo_root or (repo_map_path.parent if repo_map_path else Path.cwd()))
    repomap_dir = repo_root / REPOMAP_DIR_NAME
    index_path = repomap_dir / REPO_MAP_INDEX_FILE
    repo_map_path = repo_map_path or repomap_dir / REPO_MAP_FILE
    if repo_map_path.parent != repomap_dir:
        repo_map_path = repomap_dir / repo_map_path.name
    repo_map_full_path = repomap_dir / REPO_MAP_FULL_FILE
    if force_rebuild or should_rebuild(repo_root, index_path=index_path):
        return build_repo_index(repo_root, index_path=index_path, repo_map_path=repo_map_path, repo_map_full_path=repo_map_full_path)
    index = load_repo_index(index_path)
    repo_map = repo_map_path.read_text() if repo_map_path.exists() else format_repo_map(index)
    repo_map_full = repo_map_full_path.read_text() if repo_map_full_path.exists() else format_repo_map(index, include_all_files=True, budget_chars=DEFAULT_REPOMAP_FULL_BUDGET_CHARS, max_files=len(index.files), symbol_limit=DEFAULT_REPOMAP_FULL_MAX_SYMBOLS, dependency_limit=8, title="Repo Map Full")
    return RepoMapArtifacts(
        repo_root=repo_root,
        index=index,
        index_path=index_path,
        repo_map_path=repo_map_path,
        repo_map_full_path=repo_map_full_path,
        repo_map=repo_map,
        repo_map_full=repo_map_full,
        reused=True,
    )


def should_rebuild(repo_root: Path, *, index_path: Path | None = None) -> bool:
    index_path = index_path or repo_root / REPO_MAP_INDEX_FILE
    if not index_path.exists():
        return True
    try:
        index = load_repo_index(index_path)
    except Exception:
        return True
    discovered_files = discover_repo_files(repo_root)
    fingerprint = calculate_fingerprint(repo_root, discovered_files)
    return fingerprint != index.fingerprint
