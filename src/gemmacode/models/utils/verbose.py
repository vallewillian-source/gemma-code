"""Verbose diagnostics for model responses and tool call parsing."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from gemmacode.models.utils.content_string import get_content_string
from gemmacode.models.utils.tool_calls import collect_chat_tool_calls
from gemmacode.utils.status import build_status_text

console = Console(highlight=False)


def _truncate(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    return f"{text[:head]}…<truncated {len(text) - limit} chars>…{text[-tail:]}"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    if hasattr(value, "items"):
        try:
            dumped = dict(value)
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    return {"value": _stringify(value)}


def _normalize_tool_call(tool_call: Any) -> dict[str, Any]:
    tool_call = _as_dict(tool_call)
    function = tool_call.get("function", {})
    function = _as_dict(function)
    args_raw = function.get("arguments", tool_call.get("arguments", ""))
    args_text = _stringify(args_raw)
    return {
        "id": _normalize_scalar(tool_call.get("id") or tool_call.get("call_id")),
        "name": _normalize_scalar(function.get("name") or tool_call.get("name")),
        "arguments_preview": _truncate(args_text, 800),
        "arguments_length": len(args_text),
        "keys": sorted(tool_call.keys()),
    }


def _guess_pattern(content_text: str, tool_calls: list[dict[str, Any]], source: str) -> str:
    if source == "function_call":
        return "function_call_legacy"
    if tool_calls:
        names = [call.get("name") for call in tool_calls if call.get("name")]
        if names and all(name == "bash" for name in names):
            return "native_tool_calls"
        if names:
            return f"non_bash_tool_calls({', '.join(sorted(set(names)))})"
        return "tool_calls_without_name"
    stripped = content_text.strip()
    if not stripped:
        return "empty_content"
    lowered = content_text.lower()
    if "```mswea_bash_command" in lowered or "```bash" in lowered:
        return "markdown_code_block"
    if "\"command\"" in content_text or "'command'" in content_text:
        return "json_like_text"
    if "<tool" in lowered or "<bash" in lowered:
        return "tagged_text"
    if stripped.startswith("{") or stripped.startswith("["):
        return "json_text"
    return "plain_text"


def _normalize_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return _stringify(value)


def summarize_chat_response(
    message: Any,
    *,
    response_kind: str,
    finish_reason: str | None = None,
    parse_error: str | None = None,
) -> dict[str, Any]:
    message = _as_dict(message)
    content_text = get_content_string(message)
    raw_tool_calls, tool_calls_source = collect_chat_tool_calls(message)
    tool_calls = [_normalize_tool_call(call) for call in raw_tool_calls]
    summary = {
        "response_kind": response_kind,
        "message_keys": sorted(message.keys()),
        "role": message.get("role"),
        "finish_reason": _normalize_scalar(finish_reason),
        "content_length": len(content_text),
        "content_preview": _truncate(content_text, 1200),
        "tool_calls_source": tool_calls_source,
        "tool_calls_count": len(tool_calls),
        "tool_calls": tool_calls,
        "likely_pattern": _guess_pattern(content_text, tool_calls, tool_calls_source),
    }
    if parse_error:
        summary["parse_error"] = parse_error
    return summary


def emit_verbose_chat_response(
    *,
    verbose: bool,
    model_name: str,
    response_kind: str,
    message: Any,
    finish_reason: str | None = None,
    parse_error: str | None = None,
) -> None:
    if not verbose:
        return
    summary = summarize_chat_response(
        message,
        response_kind=response_kind,
        finish_reason=finish_reason,
        parse_error=parse_error,
    )
    console.print(build_status_text("Diagnóstico do modelo", model_name, color="yellow", symbol="∙"))
    console.print_json(json.dumps(summary, ensure_ascii=False))
