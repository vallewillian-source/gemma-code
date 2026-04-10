"""RepoMap-first task planner."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from gemmacode.repomap import RepoFileRecord, RepoIndex

from .models import (
    ResearchCandidate,
    ResearchPlan,
    extract_explicit_paths,
    tokenize_text,
)


def _join_path_tokens(path: str) -> set[str]:
    tokens = set(tokenize_text(path))
    tokens.update(part.lower() for part in Path(path).parts if part not in {".", ".."})
    tokens.add(Path(path).name.lower())
    tokens.add(Path(path).stem.lower())
    return {token for token in tokens if token}


def _is_deprioritized(file: RepoFileRecord) -> bool:
    parts = {part.lower() for part in Path(file.path).parts}
    return any(part in {"tests", "test", "fixtures", "fixture", "migrations", "migration", "generated", "build", "dist"} for part in parts)


def _score_candidate(
    file: RepoFileRecord,
    *,
    task_text: str,
    task_tokens: set[str],
    explicit_paths: set[str],
    explicit_basenames: set[str],
    token_frequency: Counter[str],
) -> tuple[float, list[str], list[str]]:
    reason_parts: list[str] = []
    matched_terms: list[str] = []
    score = float(file.score)

    path_lower = file.path.lower()
    name_lower = Path(file.path).name.lower()
    stem_lower = Path(file.path).stem.lower()

    if file.path in explicit_paths or path_lower in explicit_paths:
        score += 1000
        reason_parts.append("explicit path mentioned in task")
    elif name_lower in explicit_basenames or stem_lower in explicit_basenames:
        score += 400
        reason_parts.append("filename mentioned in task")

    for token in sorted(task_tokens):
        if token in {path_lower, name_lower, stem_lower} or token in path_lower:
            score += 95
            matched_terms.append(token)
        elif token in " ".join(file.symbols[i].name for i in range(len(file.symbols))).lower():
            score += 70
            matched_terms.append(token)
        elif token in file.summary.lower():
            score += 35
            matched_terms.append(token)
        elif token in " ".join(file.imports).lower():
            score += 20
            matched_terms.append(token)
        elif token in " ".join(file.local_dependencies).lower():
            score += 25
            matched_terms.append(token)

    for symbol in file.symbols[:5]:
        symbol_tokens = tokenize_text(symbol.name)
        overlap = sum(token_frequency[token] for token in symbol_tokens if token in token_frequency)
        if overlap:
            score += min(100, overlap * 18)
            matched_terms.extend(token for token in symbol_tokens if token in token_frequency)

    if file.is_entrypoint:
        score += 120
        reason_parts.append("entrypoint")
    if file.is_root_file:
        score += 80
        reason_parts.append("root file")
    if file.file_kind != "code":
        score -= 40
    if _is_deprioritized(file) and not explicit_paths and not explicit_basenames:
        score -= 120
        reason_parts.append("deprioritized area")
    if file.local_dependencies:
        score += min(70, len(file.local_dependencies) * 10)
    if file.symbol_count:
        score += min(100, file.symbol_count * 8)

    if not reason_parts:
        if file.local_dependencies:
            reason_parts.append("connected to other indexed files")
        elif file.symbol_count:
            reason_parts.append("contains top-level symbols")
        else:
            reason_parts.append("low-signal fallback")

    return score, reason_parts, list(dict.fromkeys(matched_terms))


def _task_kind(
    *,
    task_text: str,
    explicit_paths: list[str],
    shortlist: list[ResearchCandidate],
) -> tuple[str, float, bool]:
    if explicit_paths:
        return "explicit_file", 0.95, True
    if shortlist and shortlist[0].score >= 260:
        return "narrow", 0.65, False
    if any(token in task_text.lower() for token in ["edite", "edit", "fix", "bug", "erro", "error", "refactor"]):
        return "narrow", 0.55, False
    return "broad", 0.35, False


def _budgets_for(task_kind: str, mode: str) -> dict[str, int]:
    if task_kind == "explicit_file":
        return {"min_relevant_searches": 0, "min_open_reads": 0, "max_searches": 1, "max_open_reads": 2}
    if task_kind == "narrow":
        if mode == "strict":
            return {"min_relevant_searches": 1, "min_open_reads": 2, "max_searches": 3, "max_open_reads": 3}
        return {"min_relevant_searches": 1, "min_open_reads": 1, "max_searches": 3, "max_open_reads": 3}
    if mode == "strict":
        return {"min_relevant_searches": 2, "min_open_reads": 2, "max_searches": 4, "max_open_reads": 4}
    return {"min_relevant_searches": 1, "min_open_reads": 1, "max_searches": 4, "max_open_reads": 4}


def _build_queries(
    *,
    task_tokens: list[str],
    shortlist: list[ResearchCandidate],
    explicit_paths: list[str],
) -> list[str]:
    queries: list[str] = []
    for path in explicit_paths:
        queries.append(path)
        queries.append(Path(path).name)
        queries.append(Path(path).stem)

    for candidate in shortlist[:4]:
        if candidate.path not in queries:
            queries.append(candidate.path)
        for symbol in candidate.symbols[:3]:
            if symbol not in queries:
                queries.append(symbol)
        for token in tokenize_text(candidate.path):
            if token not in queries and len(token) > 2:
                queries.append(token)

    for token in task_tokens[:8]:
        if token not in queries:
            queries.append(token)

    deduped: list[str] = []
    for query in queries:
        cleaned = query.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped[:8]


def build_research_plan(
    *,
    task: str,
    repo_index: RepoIndex,
    repo_root: Path,
    repo_map_path: Path,
    repo_map_full_path: Path,
    mode: str = "balanced",
    max_candidates: int = 6,
) -> ResearchPlan:
    mode = mode if mode in {"strict", "balanced", "off"} else "balanced"
    task_text = task.strip()
    task_tokens = [token for token in tokenize_text(task_text) if token not in {"solve", "issue", "task"}]
    token_frequency = Counter(task_tokens)
    explicit_paths = extract_explicit_paths(task_text)
    explicit_basenames = {Path(path).name.lower() for path in explicit_paths}
    explicit_paths_set = {path.lower() for path in explicit_paths}

    # Score every file once so the planner can build its shortlist without relying on the prompt.
    for file in repo_index.files:
        file.score = float(file.score)

    scored_candidates: list[ResearchCandidate] = []
    for file in repo_index.files:
        score, reasons, matched_terms = _score_candidate(
            file,
            task_text=task_text,
            task_tokens=set(task_tokens),
            explicit_paths=explicit_paths_set,
            explicit_basenames=explicit_basenames,
            token_frequency=token_frequency,
        )
        if score <= 0 and not explicit_paths:
            continue
        symbols = [symbol.name if not symbol.signature else symbol.signature for symbol in file.symbols[:6]]
        candidate = ResearchCandidate(
            path=file.path,
            score=score,
            reason=", ".join(reasons),
            symbols=symbols,
            local_dependencies=file.local_dependencies[:6],
            summary=file.summary,
            file_kind=file.file_kind,
            queries=matched_terms,
        )
        scored_candidates.append(candidate)

    scored_candidates.sort(key=lambda item: (item.score, len(item.symbols), len(item.local_dependencies), -len(item.path)), reverse=True)
    shortlist = scored_candidates[:max_candidates]
    task_kind, confidence, allow_early_implementation = _task_kind(
        task_text=task_text,
        explicit_paths=explicit_paths,
        shortlist=shortlist,
    )
    budgets = _budgets_for(task_kind, mode)
    queries = _build_queries(task_tokens=task_tokens, shortlist=shortlist, explicit_paths=explicit_paths)

    search_terms = list(dict.fromkeys([*queries, *task_tokens, *[Path(path).name for path in explicit_paths], *[Path(path).stem for path in explicit_paths]]))
    notes: list[str] = []
    if explicit_paths:
        notes.append("Task mentions an explicit file path, so the gate may transition early.")
    if not shortlist:
        notes.append("No high-signal files were identified yet; use task keywords and entrypoints.")
    if mode == "strict":
        notes.append("Strict mode raises the research minimum before implementation can start.")

    source_fingerprint = repo_index.fingerprint

    return ResearchPlan(
        task=task_text,
        repo_root=str(repo_root),
        repo_index_path=str(repo_root / ".gemmacode" / "repo_index.json"),
        repo_map_path=str(repo_map_path),
        repo_map_full_path=str(repo_map_full_path),
        mode=mode,  # type: ignore[arg-type]
        phase="research",
        task_kind=task_kind,
        confidence=confidence,
        allow_early_implementation=allow_early_implementation,
        budgets=budgets,
        exact_paths=explicit_paths,
        shortlist=shortlist,
        queries=queries,
        search_terms=search_terms,
        notes=notes,
        source_fingerprint=source_fingerprint,
    )


def save_research_plan(plan: ResearchPlan, *, repo_root: Path) -> tuple[Path, Path]:
    research_dir = repo_root / ".gemmacode"
    research_dir.mkdir(parents=True, exist_ok=True)
    json_path = research_dir / "research_plan.json"
    md_path = research_dir / "research_plan.md"
    json_path.write_text(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
    md_path.write_text(plan.to_markdown())
    return json_path, md_path
