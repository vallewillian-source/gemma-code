"""Data models used by the RepoMap indexer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RepoSymbol:
    name: str
    type: str
    signature: str | None = None
    parent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "type": self.type}
        if self.signature:
            data["signature"] = self.signature
        if self.parent:
            data["parent"] = self.parent
        return data


@dataclass(slots=True)
class RepoFileRecord:
    path: str
    language: str
    summary: str = ""
    symbols: list[RepoSymbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    local_dependencies: list[str] = field(default_factory=list)
    size: int = 0
    line_count: int = 0
    score: float = 0.0
    is_entrypoint: bool = False
    is_root_file: bool = False
    file_kind: str = "code"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "summary": self.summary,
            "symbols": [symbol.to_dict() for symbol in self.symbols],
            "imports": list(self.imports),
            "local_dependencies": list(self.local_dependencies),
            "size": self.size,
            "line_count": self.line_count,
            "score": self.score,
            "is_entrypoint": self.is_entrypoint,
            "is_root_file": self.is_root_file,
            "file_kind": self.file_kind,
        }

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)


@dataclass(slots=True)
class RepoIndex:
    repo_root: str
    fingerprint: str
    files: list[RepoFileRecord]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "repo_root": self.repo_root,
                "fingerprint": self.fingerprint,
                "generated_at": self.generated_at,
                "version": self.version,
                "file_count": len(self.files),
            },
            "files": [file.to_dict() for file in self.files],
        }


@dataclass(slots=True)
class RepoMapArtifacts:
    repo_root: Path
    index: RepoIndex
    index_path: Path
    repo_map_path: Path
    repo_map_full_path: Path
    repo_map: str
    repo_map_full: str
    reused: bool = False

