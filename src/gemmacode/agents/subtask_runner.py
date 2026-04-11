"""SubtaskRunner for executing individual subtasks with test verification."""

import logging
from typing import Any

from gemmacode import Model
from gemmacode.agents.default import DefaultAgent
from gemmacode.environments.local import LocalEnvironment
from gemmacode.environments.restricted import RestrictedEnvironment
from gemmacode.orchestrator import SubtaskResult, SubtaskSpec, SubtaskStatus


logger = logging.getLogger("subtask_runner")


class SubtaskRunner:
    """Executor for SubtaskSpec with test verification loop.

    Runs a subtask using DefaultAgent with file restrictions, then verifies
    test acceptance criteria. Retries with test output feedback if tests fail.
    """

    def __init__(
        self,
        local_model: Model,
        base_env: LocalEnvironment | None = None,
        max_test_retries: int = 2,
    ):
        """Initialize the subtask runner.

        Args:
            local_model: Model to use for task execution (typically local/small).
            base_env: Base environment for execution (defaults to LocalEnvironment).
            max_test_retries: Maximum retry attempts when tests fail.
        """
        self.local_model = local_model
        self.base_env = base_env or LocalEnvironment()
        self.max_test_retries = max_test_retries

    def run(self, spec: SubtaskSpec) -> SubtaskResult:
        """Execute a subtask and verify with tests.

        Args:
            spec: SubtaskSpec describing the task.

        Returns:
            SubtaskResult with final status (passed, failed, timeout, etc.).
        """
        logger.info(f"Starting subtask: {spec.id} - {spec.title}")

        # Create restricted environment for this subtask
        allowed_files = list(set(spec.files_to_read + spec.files_to_write))
        restricted_env = RestrictedEnvironment(allowed_files, self.base_env)

        # Determine step limit based on complexity
        step_limit = self._get_step_limit_for_complexity(spec.estimated_complexity)

        # Build the task prompt
        task_prompt = self._build_task_prompt(spec)

        # Try to execute and pass tests
        for attempt in range(self.max_test_retries + 1):
            logger.info(f"Subtask {spec.id}: execution attempt {attempt + 1}/{self.max_test_retries + 1}")

            try:
                # Create agent for this attempt
                agent = DefaultAgent(
                    self.local_model,
                    restricted_env,
                    system_template="",  # Will be set manually
                    instance_template="",  # Will be set manually
                    step_limit=step_limit,
                )

                # Run the agent
                result = agent.run(task_prompt)
                submission = result.get("submission", "")
                logger.debug(f"Agent submission: {submission[:200]}...")

            except Exception as e:
                logger.error(f"Agent execution failed: {e}")
                return SubtaskResult(
                    spec=spec,
                    status=SubtaskStatus.FAILED,
                    error=f"Agent execution error: {str(e)}",
                    test_outputs=[],
                )

            # Run tests using base_env (unrestricted, for pytest to work)
            all_passed, test_outputs = self._run_tests(spec)

            if all_passed:
                logger.info(f"Subtask {spec.id} PASSED")
                return SubtaskResult(
                    spec=spec,
                    status=SubtaskStatus.PASSED,
                    error=None,
                    test_outputs=test_outputs,
                )

            # Tests failed, prepare for retry if attempts remain
            if attempt < self.max_test_retries:
                logger.warning(f"Subtask {spec.id}: tests failed, retrying with feedback")
                # Add test output to agent for next attempt
                test_feedback = self._format_test_feedback(test_outputs)
                task_prompt += f"\n\n## Test Output Feedback\n\nYour implementation's tests failed:\n{test_feedback}\n\nPlease fix the code and try again."
            else:
                logger.error(f"Subtask {spec.id} FAILED after {self.max_test_retries + 1} attempts")
                return SubtaskResult(
                    spec=spec,
                    status=SubtaskStatus.FAILED,
                    error=f"Tests failed after {self.max_test_retries + 1} attempts",
                    test_outputs=test_outputs,
                )

        # Should not reach here
        return SubtaskResult(
            spec=spec,
            status=SubtaskStatus.FAILED,
            error="Unexpected: loop ended without result",
            test_outputs=[],
        )

    def _build_task_prompt(self, spec: SubtaskSpec) -> str:
        """Build the task prompt from SubtaskSpec.

        Args:
            spec: The subtask specification.

        Returns:
            Complete task prompt string.
        """
        # Build acceptance tests description
        test_descriptions = "\n".join(
            f"- {criterion.description}\n  Command: {criterion.test_command}"
            for criterion in spec.acceptance_tests
        )

        # Build allowed files list
        files_list = "\n".join(f"- {f}" for f in (spec.files_to_read + spec.files_to_write))

        prompt = f"""# Task: {spec.title}

## Description

{spec.description}

## Context

{spec.context}

## Authorized Files

You can read/write the following files:

{files_list}

## Acceptance Criteria

Your implementation is complete when ALL of the following tests pass:

{test_descriptions}

## Instructions

1. Implement the required changes to make all acceptance tests pass
2. Run the acceptance tests locally before submitting
3. When ALL tests pass successfully, finalize with: COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT

Do NOT submit until all tests pass."""

        return prompt

    def _run_tests(self, spec: SubtaskSpec) -> tuple[bool, list[str]]:
        """Run acceptance tests for the subtask.

        Args:
            spec: The subtask specification.

        Returns:
            Tuple of (all_passed, test_outputs).
        """
        test_outputs = []

        for criterion in spec.acceptance_tests:
            logger.debug(f"Running test: {criterion.test_command}")
            result = self.base_env.execute({"command": criterion.test_command})
            output = result.get("output", "")
            returncode = result.get("returncode", -1)

            test_outputs.append(output)

            if returncode != 0:
                logger.warning(f"Test failed: {criterion.description}")
                return False, test_outputs

        logger.info("All tests passed")
        return True, test_outputs

    def _format_test_feedback(self, test_outputs: list[str]) -> str:
        """Format test outputs for agent feedback.

        Args:
            test_outputs: List of test command outputs.

        Returns:
            Formatted feedback string.
        """
        feedback_lines = []
        for i, output in enumerate(test_outputs, 1):
            # Only include first 500 chars of output to keep feedback concise
            truncated = output[:500] + ("..." if len(output) > 500 else "")
            feedback_lines.append(f"Test {i} output:\n{truncated}")

        return "\n\n".join(feedback_lines)

    def _get_step_limit_for_complexity(self, complexity: str) -> int:
        """Get step limit based on task complexity.

        Args:
            complexity: "low", "medium", or "high".

        Returns:
            Step limit for DefaultAgent.
        """
        limits = {
            "low": 20,
            "medium": 40,
            "high": 60,
        }
        return limits.get(complexity, 40)
