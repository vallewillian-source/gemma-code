"""Dataclasses and heuristics for the RepoMap-first research loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Literal


STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "build",
    "can",
    "crie",
    "de",
    "da",
    "das",
    "do",
    "dos",
    "edite",
    "em",
    "for",
    "from",
    "generate",
    "get",
    "git",
    "have",
    "in",
    "into",
    "is",
    "it",
    "make",
    "no",
    "not",
    "of",
    "on",
    "or",
    "para",
    "por",
    "put",
    "que",
    "re",
    "repo",
    "solve",
    "task",
    "the",
    "to",
    "uma",
    "um",
    "use",
    "with",
}

READ_ONLY_PREFIXES = (
    "cat ",
    "find ",
    "git diff",
    "git grep",
    "git log",
    "git status",
    "head ",
    "ls",
    "nl -ba",
    "pwd",
    "rg ",
    "sed -n",
    "tail ",
    "tree ",
    "wc ",
)

WRITE_PATTERNS = (
    r"\bapply_patch\b",
    r"\bcp\b",
    r"\bmkdir\b",
    r"\bmv\b",
    r"\brm\b",
    r"\btee\b",
    r"\bperl\b.*\s-i\b",
    r"\bsed\b.*\s-i\b",
    r">\s*[^|]",
    r">>\s*[^|]",
)

EXPLICIT_PATH_PATTERN = re.compile(
    r"(?<!\w)(?:[\w./-]+/)?[\w.-]+\.(?:py|js|jsx|ts|tsx|md|markdown|yaml|yml|toml|json|txt|sh|rb|go|rs|java|c|cc|cpp|h|hpp)(?!\w)",
    re.IGNORECASE,
)


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int) -> str:
    text = _collapse_whitespace(text)
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


def tokenize_text(text: str) -> list[str]:
    tokens = []
    for raw in re.findall(r"[A-Za-z0-9_./-]+", text.lower()):
        if len(raw) < 2 or raw in STOPWORDS:
            continue
        tokens.append(raw.strip("./-"))
    return [token for token in tokens if token]


def extract_explicit_paths(task: str) -> list[str]:
    paths = []
    for match in EXPLICIT_PATH_PATTERN.findall(task):
        cleaned = match.strip().strip("`'\"")
        if cleaned:
            paths.append(cleaned)
    return list(dict.fromkeys(paths))


def looks_like_read_only_command(command: str) -> bool:
    normalized = command.strip().lower()
    return any(normalized.startswith(prefix) for prefix in READ_ONLY_PREFIXES)


def looks_like_write_command(command: str) -> bool:
    normalized = _collapse_whitespace(command.lower())
    return any(re.search(pattern, normalized) for pattern in WRITE_PATTERNS)


@dataclass(slots=True)
class ResearchCandidate:
    path: str
    score: float
    reason: str
    symbols: list[str] = field(default_factory=list)
    local_dependencies: list[str] = field(default_factory=list)
    summary: str = ""
    file_kind: str = "code"
    queries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "score": self.score,
            "reason": self.reason,
            "symbols": list(self.symbols),
            "local_dependencies": list(self.local_dependencies),
            "summary": self.summary,
            "file_kind": self.file_kind,
            "queries": list(self.queries),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchCandidate":
        return cls(
            path=str(payload.get("path", "")),
            score=float(payload.get("score", 0.0)),
            reason=str(payload.get("reason", "")),
            symbols=list(payload.get("symbols", [])),
            local_dependencies=list(payload.get("local_dependencies", [])),
            summary=str(payload.get("summary", "")),
            file_kind=str(payload.get("file_kind", "code")),
            queries=list(payload.get("queries", [])),
        )


@dataclass(slots=True)
class ResearchPlan:
    task: str
    repo_root: str
    repo_index_path: str
    repo_map_path: str
    repo_map_full_path: str
    mode: Literal["strict", "balanced", "off"]
    phase: Literal["research", "implementation"]
    task_kind: str
    confidence: float
    allow_early_implementation: bool
    budgets: dict[str, int]
    exact_paths: list[str]
    shortlist: list[ResearchCandidate]
    queries: list[str]
    search_terms: list[str]
    notes: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "generated_at": self.generated_at,
                "repo_root": self.repo_root,
                "repo_index_path": self.repo_index_path,
                "repo_map_path": self.repo_map_path,
                "repo_map_full_path": self.repo_map_full_path,
                "source_fingerprint": self.source_fingerprint,
            },
            "task": self.task,
            "mode": self.mode,
            "phase": self.phase,
            "task_kind": self.task_kind,
            "confidence": self.confidence,
            "allow_early_implementation": self.allow_early_implementation,
            "budgets": dict(self.budgets),
            "exact_paths": list(self.exact_paths),
            "shortlist": [candidate.to_dict() for candidate in self.shortlist],
            "queries": list(self.queries),
            "search_terms": list(self.search_terms),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchPlan":
        metadata = payload.get("metadata", {})
        return cls(
            task=str(payload.get("task", "")),
            repo_root=str(metadata.get("repo_root", "")),
            repo_index_path=str(metadata.get("repo_index_path", "")),
            repo_map_path=str(metadata.get("repo_map_path", "")),
            repo_map_full_path=str(metadata.get("repo_map_full_path", "")),
            mode=payload.get("mode", "balanced"),
            phase=payload.get("phase", "research"),
            task_kind=str(payload.get("task_kind", "broad")),
            confidence=float(payload.get("confidence", 0.0)),
            allow_early_implementation=bool(payload.get("allow_early_implementation", False)),
            budgets={str(k): int(v) for k, v in dict(payload.get("budgets", {})).items()},
            exact_paths=[str(item) for item in payload.get("exact_paths", [])],
            shortlist=[ResearchCandidate.from_dict(item) for item in payload.get("shortlist", [])],
            queries=[str(item) for item in payload.get("queries", [])],
            search_terms=[str(item) for item in payload.get("search_terms", [])],
            notes=[str(item) for item in payload.get("notes", [])],
            generated_at=str(metadata.get("generated_at", "")) or datetime.now(timezone.utc).isoformat(),
            source_fingerprint=str(metadata.get("source_fingerprint", "")),
        )

    def to_markdown(self, *, max_candidates: int = 6, max_queries: int = 5) -> str:
        lines = [
            "# RepoMap Research Plan",
            "",
            f"- Task: `{_collapse_whitespace(self.task)}`",
            f"- Phase: `{self.phase}`",
            f"- Mode: `{self.mode}`",
            f"- Task kind: `{self.task_kind}`",
            f"- Confidence: `{self.confidence:.2f}`",
            f"- Allow early implementation: `{self.allow_early_implementation}`",
            f"- Budgets: searches={self.budgets.get('max_searches', 0)}, reads={self.budgets.get('max_open_reads', 0)}, minimums={self.budgets.get('min_relevant_searches', 0)}/{self.budgets.get('min_open_reads', 0)}",
            "",
            "## Shortlist",
        ]
        for candidate in self.shortlist[:max_candidates]:
            symbols = ", ".join(candidate.symbols[:4]) if candidate.symbols else ""
            if len(candidate.symbols) > 4:
                symbols += f" … +{len(candidate.symbols) - 4}"
            deps = ", ".join(candidate.local_dependencies[:4]) if candidate.local_dependencies else ""
            if len(candidate.local_dependencies) > 4:
                deps += f" … +{len(candidate.local_dependencies) - 4}"
            lines.extend(
                [
                    f"### {candidate.path}",
                    f"- Score: `{candidate.score:.1f}`",
                    f"- Why: {_truncate(candidate.reason, 180)}",
                ]
            )
            if candidate.summary:
                lines.append(f"- Summary: {_truncate(candidate.summary, 120)}")
            if symbols:
                lines.append(f"- Symbols: {symbols}")
            if deps:
                lines.append(f"- Depends on: {deps}")
        if not self.shortlist:
            lines.append("- No strong candidate files identified yet.")
        lines.extend(["", "## Suggested rg queries"])
        for query in self.queries[:max_queries]:
            lines.append(f"- `{query}`")
        if not self.queries:
            lines.append("- Use the RepoMap shortlist plus task keywords.")
        lines.extend(
            [
                "",
                "## Runtime rules",
                "- Read the RepoMap first.",
                "- Run `rg` using the shortlist or task-derived terms.",
                "- Open only a few files.",
                "- Do not edit until the research threshold is satisfied, unless the task names an exact file.",
            ]
        )
        if self.notes:
            lines.extend(["", "## Notes"])
            for note in self.notes:
                lines.append(f"- {note}")
        return "\n".join(lines).rstrip() + "\n"


@dataclass(slots=True)
class ResearchDecision:
    allowed: bool
    reason: str
    command_kind: str
    should_transition: bool = False
