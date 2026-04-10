"""Tree-sitter parsing helpers for RepoMap generation."""

from __future__ import annotations

import ast
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml
from tree_sitter_language_pack import get_parser

from .discovery import CODE_EXTENSIONS
from .models import RepoFileRecord, RepoSymbol

TREE_SITTER_LANGUAGES = {"python", "javascript", "typescript"}
TEXT_SUMMARY_LIMIT = 140


def get_language_for_path(path: Path) -> str:
    name = path.name
    suffix = path.suffix.lower()
    if name == "Dockerfile":
        return "dockerfile"
    if name == "Makefile":
        return "makefile"
    if suffix == ".py":
        return "python"
    if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
        return "javascript"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    if suffix in {".md", ".rst"}:
        return "markdown"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    if suffix == ".toml":
        return "toml"
    if suffix in {".ini", ".cfg", ".txt"}:
        return "text"
    return "text"


@lru_cache(maxsize=None)
def _get_parser(language: str):
    try:
        return get_parser(language)
    except Exception:
        return None


def _node_text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _identifier_text(source: bytes, node) -> str:
    for child in node.children:
        if child.type == "identifier":
            return _node_text(source, child).strip()
    return ""


def _parameters_text(source: bytes, node) -> str:
    for child in node.children:
        if child.type == "parameters":
            text = _node_text(source, child).strip()
            return text
    return "()"


def _collect_python_imports(node, source: bytes) -> list[str]:
    text = _node_text(source, node).strip()
    if node.type == "import_from_statement":
        match = re.match(r"from\s+(.+?)\s+import\s+", text)
        if match:
            return [match.group(1).strip()]
        return []
    if node.type == "import_statement":
        match = re.match(r"import\s+(.+)$", text)
        if not match:
            return []
        imports: list[str] = []
        for part in match.group(1).split(","):
            module = part.strip().split(" as ", 1)[0].strip()
            if module:
                imports.append(module)
        return imports
    return []


def _collect_js_imports(node, source: bytes) -> list[str]:
    text = _node_text(source, node).strip()
    imports: list[str] = []
    module_matches = re.findall(r"from\s+['\"]([^'\"]+)['\"]", text)
    imports.extend(module_matches)
    require_matches = re.findall(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", text)
    imports.extend(require_matches)
    bare_matches = re.findall(r"import\s+['\"]([^'\"]+)['\"]", text)
    imports.extend(bare_matches)
    return imports


def _strip_quotes(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _leading_comment_summary(source_text: str) -> str:
    lines = source_text.splitlines()
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith(("#", "//", "/*", "*")):
            cleaned = stripped.lstrip("#/ *").strip()
            cleaned = cleaned.rstrip("*/").strip()
            if cleaned:
                collected.append(cleaned)
            continue
        break
    return " ".join(collected).strip()


def _first_heading_summary(source_text: str) -> str:
    for line in source_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("# ").strip()
        if stripped:
            return stripped
    return ""


def _json_summary(source_text: str) -> str:
    try:
        data = json.loads(source_text)
    except Exception:
        return ""
    if isinstance(data, dict):
        keys = list(data.keys())[:5]
        if keys:
            return f"JSON config/data with keys: {', '.join(str(key) for key in keys)}"
    return ""


def _yaml_summary(source_text: str) -> str:
    try:
        data = yaml.safe_load(source_text)
    except Exception:
        return ""
    if isinstance(data, dict):
        keys = list(data.keys())[:5]
        if keys:
            return f"YAML config with keys: {', '.join(str(key) for key in keys)}"
    return ""


def _text_summary(path: Path, source_text: str) -> str:
    if path.name == "pyproject.toml":
        return "Python project configuration"
    if path.name == "package.json":
        try:
            data = json.loads(source_text)
        except Exception:
            return "Node package configuration"
        if isinstance(data, dict):
            pieces = []
            if data.get("scripts"):
                pieces.append("scripts")
            if data.get("dependencies") or data.get("devDependencies"):
                pieces.append("dependencies")
            if pieces:
                return f"Node package configuration ({', '.join(pieces)})"
        return "Node package configuration"
    suffix = path.suffix.lower()
    if suffix in {".md", ".rst"}:
        return _first_heading_summary(source_text)
    if suffix in {".yaml", ".yml"}:
        return _yaml_summary(source_text)
    if suffix == ".json":
        return _json_summary(source_text)
    if suffix == ".toml":
        return "TOML configuration"
    return _leading_comment_summary(source_text)


def _shorten_summary(summary: str, *, limit: int = TEXT_SUMMARY_LIMIT) -> str:
    summary = " ".join(summary.split())
    if len(summary) <= limit:
        return summary
    return summary[: limit - 1].rstrip() + "…"


def _fallback_summary(path: Path, symbols: Iterable[RepoSymbol]) -> str:
    symbol_names = [symbol.name for symbol in symbols][:3]
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    if symbol_names:
        return f"{stem} module with {', '.join(symbol_names)}"
    return stem


def _extract_python_symbols(source: bytes, tree) -> tuple[list[RepoSymbol], list[str]]:
    root = tree.root_node
    symbols: list[RepoSymbol] = []
    imports: list[str] = []
    for child in root.children:
        if child.type in {"import_statement", "import_from_statement"}:
            imports.extend(_collect_python_imports(child, source))
            continue
        if child.type == "class_definition":
            class_name = _identifier_text(source, child)
            if class_name:
                symbols.append(RepoSymbol(name=class_name, type="class"))
            block = next((item for item in child.children if item.type == "block"), None)
            if block is None:
                continue
            for member in block.children:
                if member.type != "function_definition":
                    continue
                method_name = _identifier_text(source, member)
                if not method_name:
                    continue
                params = _parameters_text(source, member)
                signature = f"{method_name}{params}"
                symbols.append(RepoSymbol(name=f"{class_name}.{method_name}" if class_name else method_name, type="method", signature=signature, parent=class_name or None))
            continue
        if child.type == "function_definition":
            function_name = _identifier_text(source, child)
            if function_name:
                params = _parameters_text(source, child)
                symbols.append(RepoSymbol(name=function_name, type="function", signature=f"{function_name}{params}"))
    return symbols, imports


def _extract_js_symbols(source: bytes, tree) -> tuple[list[RepoSymbol], list[str]]:
    root = tree.root_node
    symbols: list[RepoSymbol] = []
    imports: list[str] = []

    def visit(node, parent_class: str | None = None) -> None:
        nonlocal symbols, imports
        for child in node.children:
            if child.type in {"import_statement", "export_statement"}:
                imports.extend(_collect_js_imports(child, source))
            if child.type in {"class_declaration", "function_declaration"}:
                name = _identifier_text(source, child)
                if child.type == "class_declaration":
                    if name:
                        symbols.append(RepoSymbol(name=name, type="class"))
                    block = next((item for item in child.children if item.type == "class_body"), None)
                    if block is not None:
                        visit(block, parent_class=name or parent_class)
                elif name:
                    params = next((item for item in child.children if item.type == "formal_parameters"), None)
                    params_text = _node_text(source, params) if params is not None else "()"
                    symbols.append(
                        RepoSymbol(name=name, type="function", signature=f"{name}{params_text}")
                    )
            elif child.type == "method_definition":
                name = _identifier_text(source, child)
                if name:
                    params = next((item for item in child.children if item.type == "formal_parameters"), None)
                    params_text = _node_text(source, params) if params is not None else "()"
                    display_name = f"{parent_class}.{name}" if parent_class else name
                    symbols.append(
                        RepoSymbol(name=display_name, type="method", signature=f"{name}{params_text}", parent=parent_class)
                    )
            else:
                visit(child, parent_class=parent_class)

    visit(root)
    return symbols, imports


def parse_repo_file(repo_root: Path, path: Path) -> RepoFileRecord:
    rel_path = path.relative_to(repo_root).as_posix()
    source_bytes = path.read_bytes()
    source_text = source_bytes.decode("utf-8", errors="ignore")
    language = get_language_for_path(path)
    summary = ""
    symbols: list[RepoSymbol] = []
    imports: list[str] = []
    file_kind = "code" if path.suffix.lower() in CODE_EXTENSIONS else "text"

    if language in TREE_SITTER_LANGUAGES:
        parser = _get_parser(language)
        if parser is not None:
            tree = parser.parse(source_bytes)
            if language == "python":
                symbols, imports = _extract_python_symbols(source_bytes, tree)
                module_doc = ""
                root = tree.root_node
                first_child = root.children[0] if root.children else None
                if first_child is not None and first_child.type == "expression_statement":
                    first_child = first_child.children[0] if first_child.children else first_child
                if first_child is not None and first_child.type == "string":
                    try:
                        module_doc = ast.literal_eval(_node_text(source_bytes, first_child))
                    except Exception:
                        module_doc = _strip_quotes(_node_text(source_bytes, first_child))
                summary = module_doc or _leading_comment_summary(source_text)
            else:
                symbols, imports = _extract_js_symbols(source_bytes, tree)
                summary = _leading_comment_summary(source_text)

    if not summary:
        summary = _text_summary(path, source_text)
    if not summary:
        summary = _fallback_summary(path, symbols)

    summary = _shorten_summary(summary)
    imports = [item.strip() for item in imports if item.strip()]
    return RepoFileRecord(
        path=rel_path,
        language=language,
        summary=summary,
        symbols=symbols,
        imports=imports,
        size=len(source_bytes),
        line_count=source_text.count("\n") + (0 if not source_text else 1),
        file_kind=file_kind,
    )
