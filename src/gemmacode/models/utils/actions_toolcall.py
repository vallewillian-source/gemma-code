"""Parse actions & format observations with toolcalls"""

import json
import time
from typing import Any

from jinja2 import StrictUndefined, Template

from gemmacode.exceptions import FormatError
from gemmacode.models.utils.openai_multimodal import expand_multimodal_content

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute a bash command",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                }
            },
            "required": ["command"],
        },
    },
}


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


def _extract_tool_call_fields(tool_call: Any) -> tuple[Any, Any, Any]:
    if isinstance(tool_call, dict):
        function = _as_dict(tool_call.get("function"))
        if function:
            name = function.get("name")
            arguments = function.get("arguments")
        else:
            name = tool_call.get("name")
            arguments = tool_call.get("arguments")
        call_id = tool_call.get("id") or tool_call.get("call_id")
        return name, arguments, call_id

    attrs = getattr(tool_call, "__dict__", {})
    if isinstance(attrs, dict) and attrs:
        function = attrs.get("function")
        if function is not None:
            function_attrs = getattr(function, "__dict__", {})
            if isinstance(function_attrs, dict) and function_attrs:
                name = function_attrs.get("name")
                arguments = function_attrs.get("arguments")
            else:
                name = getattr(function, "name", None)
                arguments = getattr(function, "arguments", None)
        else:
            name = attrs.get("name")
            arguments = attrs.get("arguments")
        call_id = attrs.get("id") or attrs.get("call_id")
        if name is not None or arguments is not None or call_id is not None:
            return name, arguments, call_id

    function = getattr(tool_call, "function", None)
    if function is not None:
        name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", None)
    else:
        name = getattr(tool_call, "name", None)
        arguments = getattr(tool_call, "arguments", None)
    call_id = getattr(tool_call, "id", None) or getattr(tool_call, "call_id", None)
    return name, arguments, call_id


def parse_toolcall_actions(tool_calls: list, *, format_error_template: str) -> list[dict]:
    """Parse tool calls from the response. Raises FormatError if unknown tool or invalid args."""
    if not tool_calls:
        raise FormatError(
            {
                "role": "user",
                "content": Template(format_error_template, undefined=StrictUndefined).render(
                    error="No tool calls found in the response. Every response MUST include at least one tool call.",
                    actions=[],
                ),
                "extra": {"interrupt_type": "FormatError"},
            }
        )
    actions = []
    for tool_call in tool_calls:
        error_msg = ""
        args = {}
        name, arguments, call_id = _extract_tool_call_fields(tool_call)
        try:
            args = json.loads(arguments)
        except Exception as e:
            error_msg = f"Error parsing tool call arguments: {e}."
        if name != "bash":
            error_msg += f"Unknown tool '{name}'."
        if not isinstance(args, dict) or "command" not in args:
            error_msg += "Missing 'command' argument in bash tool call."
        if error_msg:
            raise FormatError(
                {
                    "role": "user",
                    "content": Template(format_error_template, undefined=StrictUndefined).render(
                        actions=[], error=error_msg.strip()
                    ),
                    "extra": {"interrupt_type": "FormatError"},
                }
            )
        actions.append({"command": args["command"], "tool_call_id": call_id})
    return actions


def format_toolcall_observation_messages(
    *,
    actions: list[dict],
    outputs: list[dict],
    observation_template: str,
    template_vars: dict | None = None,
    multimodal_regex: str = "",
) -> list[dict]:
    """Format execution outputs into tool result messages."""
    not_executed = {"output": "", "returncode": -1, "exception_info": "action was not executed"}
    padded_outputs = outputs + [not_executed] * (len(actions) - len(outputs))
    results = []
    for action, output in zip(actions, padded_outputs):
        content = Template(observation_template, undefined=StrictUndefined).render(
            output=output, **(template_vars or {})
        )
        msg = {
            "content": content,
            "extra": {
                "raw_output": output.get("output", ""),
                "returncode": output.get("returncode"),
                "timestamp": time.time(),
                "exception_info": output.get("exception_info"),
                **output.get("extra", {}),
            },
        }
        if "tool_call_id" in action:
            msg["tool_call_id"] = action["tool_call_id"]
            msg["role"] = "tool"
        else:
            msg["role"] = "user"  # human issued commands
        if multimodal_regex:
            msg = expand_multimodal_content(msg, pattern=multimodal_regex)
        results.append(msg)
    return results
