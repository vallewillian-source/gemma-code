"""RepoMap markdown formatting helpers."""

from __future__ import annotations

from .models import RepoFileRecord, RepoIndex
from .selection import select_repo_map_files


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


def _format_symbols(file: RepoFileRecord, *, symbol_limit: int) -> list[str]:
    lines: list[str] = []
    for symbol in file.symbols[:symbol_limit]:
        if symbol.signature:
            lines.append(f"  - {symbol.signature}")
        else:
            lines.append(f"  - {symbol.name}")
    if len(file.symbols) > symbol_limit:
        lines.append(f"  - … {len(file.symbols) - symbol_limit} more")
    return lines


def _format_dependencies(file: RepoFileRecord, *, dependency_limit: int) -> str:
    dependencies = file.local_dependencies[:dependency_limit]
    if not dependencies:
        return ""
    suffix = ""
    if len(file.local_dependencies) > dependency_limit:
        suffix = f" … +{len(file.local_dependencies) - dependency_limit}"
    return ", ".join(dependencies) + suffix


def format_repo_map(
    index: RepoIndex,
    *,
    budget_chars: int = 14_000,
    max_files: int = 80,
    symbol_limit: int = 5,
    dependency_limit: int = 5,
    include_all_files: bool = False,
    title: str = "Repo Map",
) -> str:
    files = select_repo_map_files(index, max_files=max_files if max_files > 0 else len(index.files))
    lines: list[str] = [f"# {title}", ""]
    lines.append(f"> repo_root: `{index.repo_root}`")
    lines.append(f"> fingerprint: `{index.fingerprint}`")
    lines.append(f"> files: {len(files)}/{len(index.files)}")
    lines.append("")

    used = len("\n".join(lines))
    rendered_count = 0
    for file in files:
        block_lines = [f"## {file.path}"]
        if file.summary:
            block_lines.append(f"- Purpose: {_truncate(file.summary, 160)}")
        else:
            block_lines.append("- Purpose: ")
        if file.local_dependencies:
            deps = _format_dependencies(file, dependency_limit=dependency_limit)
            block_lines.append(f"- Depends on: {deps}")
        if file.imports and include_all_files:
            imports = ", ".join(file.imports[:dependency_limit])
            if len(file.imports) > dependency_limit:
                imports += f" … +{len(file.imports) - dependency_limit}"
            block_lines.append(f"- Imports: {imports}")
        if file.symbols:
            block_lines.append("- Symbols:")
            block_lines.extend(_format_symbols(file, symbol_limit=symbol_limit))
        elif include_all_files:
            block_lines.append("- Symbols: none")
        block_lines.append("")
        block = "\n".join(block_lines)
        if used + len(block) > budget_chars and rendered_count > 0:
            break
        lines.extend(block_lines)
        used += len(block)
        rendered_count += 1

    omitted = len(index.files) - rendered_count
    if len(lines) > 4:
        lines[4] = f"> files: {rendered_count}/{len(index.files)}"
    if omitted > 0 and not include_all_files:
        lines.extend(
            [
                "",
                f"> omitted {omitted} file(s) to stay within the budget of {budget_chars} characters.",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
