"""Orchestrator agent for task decomposition using a large language model."""

import json
import logging
from typing import Any

from pydantic import ValidationError

from gemmacode import Model
from gemmacode.orchestrator import (
    DecompositionPlan,
    build_heuristics_prompt,
)


logger = logging.getLogger("orchestrator")


class OrchestratorError(Exception):
    """Error raised when orchestrator decomposition fails."""

    pass


class OrchestratorAgent:
    """Agent that decomposes a task into subtasks using a large language model.

    The orchestrator makes a single-shot call to a model (typically DeepSeek),
    providing the full task description, repository context, and heuristics.
    The model returns a structured JSON decomposition plan.
    """

    def __init__(
        self,
        model: Model,
        heuristics_applied: list[str] | None = None,
        max_retries: int = 3,
    ):
        """Initialize the orchestrator agent.

        Args:
            model: A Model instance (typically large, like DeepSeek).
            heuristics_applied: List of heuristics categories to apply.
                                If None, all heuristics are applied.
            max_retries: Maximum retry attempts if JSON parsing fails.
        """
        self.model = model
        self.heuristics_applied = heuristics_applied
        self.max_retries = max_retries

    def decompose(self, task: str, repo_map: str) -> DecompositionPlan:
        """Decompose a task into structured subtasks.

        Args:
            task: The high-level task description.
            repo_map: Repository structure/context from RepoMap.

        Returns:
            A DecompositionPlan with validated subtasks.

        Raises:
            OrchestratorError: If decomposition fails after max_retries.
        """
        heuristics_prompt = build_heuristics_prompt(self.heuristics_applied)

        system_prompt = self._build_system_prompt(heuristics_prompt)
        user_message = self._build_user_message(task, repo_map)

        messages = [
            self.model.format_message(role="system", content=system_prompt),
            self.model.format_message(role="user", content=user_message),
        ]

        for attempt in range(self.max_retries):
            try:
                response = self.model.query(messages)
                content = response.get("content", "")

                # Extract JSON from response
                plan_dict = self._extract_json(content)
                plan = DecompositionPlan.model_validate(plan_dict)
                logger.info(f"Decomposition successful: {len(plan.subtasks)} subtasks")
                return plan

            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                error_msg = str(e)
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {error_msg}")

                if attempt < self.max_retries - 1:
                    # Add error to conversation and retry
                    messages.append(self.model.format_message(role="assistant", content=response.get("content", "")))
                    error_instruction = (
                        f"The JSON you provided has an error:\n{error_msg}\n\n"
                        "Please fix it and provide a valid JSON response that conforms to the DecompositionPlan schema."
                    )
                    messages.append(self.model.format_message(role="user", content=error_instruction))
                else:
                    raise OrchestratorError(
                        f"Failed to decompose task after {self.max_retries} retries. Last error: {error_msg}"
                    ) from e

        raise OrchestratorError("Orchestrator decomposition failed (should not reach here)")

    def _build_system_prompt(self, heuristics_prompt: str) -> str:
        """Build the system prompt for the orchestrator.

        Args:
            heuristics_prompt: Formatted heuristics rules.

        Returns:
            System prompt string.
        """
        schema_example = '''{
  "original_task": "string: the full original task description",
  "subtasks": [
    {
      "id": "unique-identifier-slug",
      "title": "Short descriptive title",
      "description": "Detailed description of what this subtask accomplishes",
      "files_to_read": ["path/to/file.py"],
      "files_to_write": ["path/to/file.py"],
      "context": "Additional context specific to this subtask",
      "dependencies": ["id-of-subtask-this-depends-on"],
      "acceptance_tests": [
        {
          "description": "What the test verifies",
          "test_command": "pytest tests/test_file.py::test_function -v"
        }
      ],
      "estimated_complexity": "low|medium|high"
    }
  ],
  "global_context": "Shared context for all subtasks (repo patterns, coding standards, etc.)",
  "heuristics_applied": ["heuristics-category-names"]
}'''

        return f"""You are an expert software engineering orchestrator. Your role is to decompose complex software engineering tasks into smaller, manageable subtasks that can be executed independently or with explicit dependencies.

## Core Responsibilities

1. Analyze the provided task and repository context
2. Apply the following heuristics strictly when decomposing
3. Return a structured JSON plan following the DecompositionPlan schema
4. Ensure subtasks are concrete, testable, and independently executable

## Heuristics to Apply

{heuristics_prompt}

## DecompositionPlan Schema (respond with valid JSON matching this schema)

```json
{schema_example}
```

## Instructions

- Each subtask must be independently testable
- Dependencies must form a valid DAG (no cycles)
- Acceptance tests must be runnable pytest commands
- Provide realistic file paths based on the repository structure shown
- Estimate complexity conservatively
- Apply the heuristics consistently across all subtasks"""

    def _build_user_message(self, task: str, repo_map: str) -> str:
        """Build the user message with task and context.

        Args:
            task: The task description.
            repo_map: Repository context.

        Returns:
            User message string.
        """
        return f"""Decompose this task into subtasks:

## Task

{task}

## Repository Structure

{repo_map}

## Your Response

Provide ONLY a valid JSON response matching the DecompositionPlan schema. Do not include any text outside the JSON block."""

    def _extract_json(self, content: str) -> dict[str, Any]:
        """Extract JSON from the response content.

        Args:
            content: Response content that may contain markdown code blocks.

        Returns:
            Parsed JSON dict.

        Raises:
            json.JSONDecodeError: If no valid JSON is found.
        """
        # Try to parse as-is first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract from markdown code block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()
                return json.loads(json_str)

        # Try to extract any JSON object
        if "{" in content:
            start = content.find("{")
            # Find the last closing brace
            end = content.rfind("}") + 1
            if end > start:
                json_str = content[start:end]
                return json.loads(json_str)

        raise json.JSONDecodeError("No valid JSON found in response", content, 0)
