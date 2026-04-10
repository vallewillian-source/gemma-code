"""Retry helpers for responses that fail tool-call parsing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy

from gemmacode.exceptions import FormatError
from gemmacode.models import GLOBAL_MODEL_STATS


def query_with_toolcall_format_retry(
    *,
    messages: list[dict],
    query_once: Callable[[list[dict]], object],
    parse_actions: Callable[[object], list[dict]],
    calculate_cost: Callable[[object], dict[str, float]],
    logger: logging.Logger,
    max_attempts: int = 3,
) -> tuple[object, list[dict], dict[str, float]]:
    """Query a model, retrying when the response does not contain valid tool calls."""
    current_messages = deepcopy(messages)
    total_cost = 0.0
    last_error: FormatError | None = None

    for attempt in range(1, max_attempts + 1):
        response = query_once(current_messages)
        cost_output = calculate_cost(response)
        attempt_cost = float(cost_output.get("cost", 0.0))
        total_cost += attempt_cost
        GLOBAL_MODEL_STATS.add(attempt_cost)

        try:
            actions = parse_actions(response)
        except FormatError as error:
            last_error = error
            if attempt >= max_attempts:
                raise
            logger.warning(
                "Model response did not include valid tool calls. Retrying format validation (%s/%s).",
                attempt,
                max_attempts,
            )
            current_messages.extend(error.messages)
            continue

        return response, actions, {**cost_output, "cost": total_cost}

    if last_error is not None:
        raise last_error
    raise RuntimeError("Tool-call retry helper exhausted without producing a valid response.")
