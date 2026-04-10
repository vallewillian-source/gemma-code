"""RepoMap generation utilities for gemma-code."""

from .build import (
    DEFAULT_REPOMAP_BUDGET_CHARS,
    DEFAULT_REPOMAP_FULL_BUDGET_CHARS,
    DEFAULT_REPOMAP_FULL_MAX_SYMBOLS,
    DEFAULT_REPOMAP_MAX_FILES,
    DEFAULT_REPOMAP_MAX_SYMBOLS,
    build_repo_index,
    build_repo_map,
    load_repo_index,
    load_repo_map,
    should_rebuild,
)
from .discovery import REPO_MAP_FILE, REPO_MAP_FULL_FILE, REPO_MAP_INDEX_FILE, find_repo_root
from .models import RepoFileRecord, RepoIndex, RepoMapArtifacts, RepoSymbol
from .parsing import parse_repo_file
from .selection import select_repo_map_files
from .formatting import format_repo_map

__all__ = [
    "DEFAULT_REPOMAP_BUDGET_CHARS",
    "DEFAULT_REPOMAP_FULL_BUDGET_CHARS",
    "DEFAULT_REPOMAP_FULL_MAX_SYMBOLS",
    "DEFAULT_REPOMAP_MAX_FILES",
    "DEFAULT_REPOMAP_MAX_SYMBOLS",
    "REPO_MAP_FILE",
    "REPO_MAP_FULL_FILE",
    "REPO_MAP_INDEX_FILE",
    "RepoFileRecord",
    "RepoIndex",
    "RepoMapArtifacts",
    "RepoSymbol",
    "build_repo_index",
    "build_repo_map",
    "find_repo_root",
    "format_repo_map",
    "load_repo_index",
    "load_repo_map",
    "parse_repo_file",
    "select_repo_map_files",
    "should_rebuild",
]
