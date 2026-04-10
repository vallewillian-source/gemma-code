"""Helpers to normalize model tool-call payloads."""

from __future__ import annotations

from typing import Any


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
    return {}


def _get_field(message: Any, field: str) -> Any:
    if isinstance(message, dict):
        if field in message:
            return message.get(field)
        provider_specific_fields = message.get("provider_specific_fields")
        if isinstance(provider_specific_fields, dict) and field in provider_specific_fields:
            return provider_specific_fields.get(field)
        return None
    return getattr(message, field, None)


class ToolCallFunctionAdapter:
    """Minimal tool-call function object compatible with the agent parser."""

    def __init__(self, *, name: Any, arguments: Any):
        self.name = name
        self.arguments = arguments

    def model_dump(self) -> dict[str, Any]:
        return {"name": self.name, "arguments": self.arguments}


class ToolCallAdapter:
    """Minimal tool-call object compatible with the agent parser."""

    def __init__(self, *, call_id: Any, name: Any, arguments: Any):
        self.id = call_id
        self.function = ToolCallFunctionAdapter(name=name, arguments=arguments)

    @classmethod
    def from_function_call(cls, function_call: Any, *, call_id: Any = None) -> "ToolCallAdapter":
        data = _as_dict(function_call)
        if not data and function_call is not None:
            data = {
                "name": getattr(function_call, "name", None),
                "arguments": getattr(function_call, "arguments", None),
                "id": getattr(function_call, "id", None),
                "call_id": getattr(function_call, "call_id", None),
            }
        nested_function = _as_dict(data.get("function"))
        name = data.get("name") if data.get("name") is not None else nested_function.get("name")
        arguments = data.get("arguments") if data.get("arguments") is not None else nested_function.get("arguments")
        resolved_call_id = call_id or data.get("id") or data.get("call_id")
        return cls(call_id=resolved_call_id, name=name, arguments=arguments)

    def model_dump(self) -> dict[str, Any]:
        return {"id": self.id, "function": self.function.model_dump()}


def collect_chat_tool_calls(message: Any) -> tuple[list[Any], str]:
    """Collect tool calls from chat-completions style message payloads.

    Returns a tuple of (tool_calls, source), where source is one of:
    - "tool_calls"
    - "function_call"
    - "none"
    """
    tool_calls = _get_field(message, "tool_calls") or []
    if tool_calls:
        return list(tool_calls), "tool_calls"
    function_call = _get_field(message, "function_call")
    if function_call:
        call_id = _get_field(function_call, "id") or _get_field(function_call, "call_id")
        return [ToolCallAdapter.from_function_call(function_call, call_id=call_id)], "function_call"
    return [], "none"
