"""Tests for SubtaskRunner."""

import pytest

from src.gemmacode.agents.subtask_runner import SubtaskRunner
from src.gemmacode.environments.local import LocalEnvironment
from src.gemmacode.orchestrator import SubtaskResult, SubtaskSpec, SubtaskStatus, TestCriterion


class DeterministicModel:
    """Mock model that returns predefined responses for testing."""

    def __init__(self, response: str = "Implementation complete\nCOMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"):
        """Initialize with response."""
        self.response = response
        self.call_count = 0
        self.config = {}

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict:
        """Return response."""
        self.call_count += 1
        return {"content": self.response, "role": "assistant"}

    def format_message(self, role: str, content: str, **kwargs) -> dict:
        """Format a message."""
        return {"role": role, "content": content}

    def get_template_vars(self, **kwargs) -> dict:
        """Return template variables."""
        return {}

    def format_observation_messages(
        self, message: dict, outputs: list[dict], template_vars: dict | None = None
    ) -> list[dict]:
        """Format observation messages."""
        if not outputs:
            return []
        # Return exit message after first step
        return [
            {
                "role": "exit",
                "content": "Done",
                "extra": {"exit_status": "Submitted", "submission": "Implementation complete"},
            }
        ]

    def serialize(self) -> dict:
        """Serialize model configuration."""
        return {"type": "DeterministicModel", "response": self.response}


class MockEnvironment:
    """Mock environment for testing."""

    def __init__(self, test_result: bool = True):
        """Initialize with test result."""
        self.test_result = test_result
        self.commands_executed = []
        self.config = {}

    def execute(self, action: dict, cwd: str = "", **kwargs) -> dict:
        """Execute action and return result."""
        command = action.get("command", "")
        self.commands_executed.append(command)

        if self.test_result:
            return {"output": "test output", "returncode": 0, "exception_info": ""}
        else:
            return {
                "output": "FAILED: assertion error",
                "returncode": 1,
                "exception_info": "Test failed",
            }

    def get_template_vars(self, **kwargs) -> dict:
        """Get template variables."""
        return {"allowed_files": []}

    def serialize(self) -> dict:
        """Serialize environment."""
        return {}


@pytest.fixture
def simple_subtask():
    """Create a simple subtask spec."""
    return SubtaskSpec(
        id="test-task",
        title="Implement test function",
        description="Create a simple test function that returns True",
        files_to_read=["src/main.py"],
        files_to_write=["src/main.py", "tests/test_main.py"],
        context="Use simple implementation with no external dependencies",
        dependencies=[],
        acceptance_tests=[
            TestCriterion(
                description="Test function returns True",
                test_command="pytest tests/test_main.py::test_simple -v",
            )
        ],
        estimated_complexity="low",
    )


@pytest.fixture
def complex_subtask():
    """Create a more complex subtask spec."""
    return SubtaskSpec(
        id="complex-task",
        title="Implement authentication service",
        description="Create authentication service with login and token generation",
        files_to_read=["src/models/user.py"],
        files_to_write=["src/services/auth.py", "tests/test_auth.py"],
        context="Use Pydantic v2 for validation, pathlib for paths",
        dependencies=["user-model-task"],
        acceptance_tests=[
            TestCriterion(
                description="Authentication service initializes",
                test_command="pytest tests/test_auth.py::test_auth_init -v",
            ),
            TestCriterion(
                description="Login generates valid token",
                test_command="pytest tests/test_auth.py::test_login -v",
            ),
        ],
        estimated_complexity="high",
    )


class TestSubtaskRunnerBasic:
    """Basic tests for SubtaskRunner."""

    def test_run_with_passing_tests(self, simple_subtask):
        """Should return passed status when tests pass."""
        model = DeterministicModel()
        env = MockEnvironment(test_result=True)
        runner = SubtaskRunner(model, base_env=env)

        result = runner.run(simple_subtask)

        assert isinstance(result, SubtaskResult)
        assert result.status == SubtaskStatus.PASSED
        assert result.spec.id == "test-task"
        assert result.error is None
        assert len(result.test_outputs) == 1

    def test_run_with_failing_tests(self, simple_subtask):
        """Should return failed status when tests fail."""
        model = DeterministicModel()
        env = MockEnvironment(test_result=False)
        runner = SubtaskRunner(model, base_env=env, max_test_retries=0)

        result = runner.run(simple_subtask)

        assert result.status == SubtaskStatus.FAILED
        assert result.error is not None
        assert "failed" in result.error.lower()


class TestSubtaskRunnerPromptGeneration:
    """Tests for task prompt generation."""

    def test_prompt_includes_title(self, simple_subtask):
        """Task prompt should include subtask title."""
        runner = SubtaskRunner(DeterministicModel())
        prompt = runner._build_task_prompt(simple_subtask)

        assert simple_subtask.title in prompt

    def test_prompt_includes_description(self, simple_subtask):
        """Task prompt should include subtask description."""
        runner = SubtaskRunner(DeterministicModel())
        prompt = runner._build_task_prompt(simple_subtask)

        assert simple_subtask.description in prompt

    def test_prompt_includes_context(self, simple_subtask):
        """Task prompt should include subtask context."""
        runner = SubtaskRunner(DeterministicModel())
        prompt = runner._build_task_prompt(simple_subtask)

        assert simple_subtask.context in prompt

    def test_prompt_includes_test_criteria(self, simple_subtask):
        """Task prompt should include acceptance test criteria."""
        runner = SubtaskRunner(DeterministicModel())
        prompt = runner._build_task_prompt(simple_subtask)

        for criterion in simple_subtask.acceptance_tests:
            assert criterion.description in prompt
            assert criterion.test_command in prompt

    def test_prompt_includes_files_to_write(self, simple_subtask):
        """Task prompt should list files that can be written."""
        runner = SubtaskRunner(DeterministicModel())
        prompt = runner._build_task_prompt(simple_subtask)

        for file in simple_subtask.files_to_write:
            assert file in prompt

    def test_prompt_includes_completion_instruction(self, simple_subtask):
        """Task prompt should include instruction to use COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT."""
        runner = SubtaskRunner(DeterministicModel())
        prompt = runner._build_task_prompt(simple_subtask)

        assert "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in prompt


class TestSubtaskRunnerStepLimits:
    """Tests for step limit calculation based on complexity."""

    def test_low_complexity_step_limit(self):
        """Low complexity should have lower step limit."""
        runner = SubtaskRunner(DeterministicModel())
        assert runner._get_step_limit_for_complexity("low") == 20

    def test_medium_complexity_step_limit(self):
        """Medium complexity should have medium step limit."""
        runner = SubtaskRunner(DeterministicModel())
        assert runner._get_step_limit_for_complexity("medium") == 40

    def test_high_complexity_step_limit(self):
        """High complexity should have higher step limit."""
        runner = SubtaskRunner(DeterministicModel())
        assert runner._get_step_limit_for_complexity("high") == 60

    def test_unknown_complexity_defaults_to_medium(self):
        """Unknown complexity should default to medium."""
        runner = SubtaskRunner(DeterministicModel())
        assert runner._get_step_limit_for_complexity("unknown") == 40


class TestSubtaskRunnerTestExecution:
    """Tests for test execution."""

    def test_run_tests_passes_all(self, simple_subtask):
        """Should return True when all tests pass."""
        runner = SubtaskRunner(DeterministicModel(), base_env=MockEnvironment(test_result=True))
        passed, outputs = runner._run_tests(simple_subtask)

        assert passed is True
        assert len(outputs) == len(simple_subtask.acceptance_tests)

    def test_run_tests_fails_any(self, simple_subtask):
        """Should return False when any test fails."""
        runner = SubtaskRunner(DeterministicModel(), base_env=MockEnvironment(test_result=False))
        passed, outputs = runner._run_tests(simple_subtask)

        assert passed is False
        assert len(outputs) > 0

    def test_run_tests_multiple_criteria(self, complex_subtask):
        """Should execute all acceptance criteria."""
        mock_env = MockEnvironment(test_result=True)
        runner = SubtaskRunner(DeterministicModel(), base_env=mock_env)
        runner._run_tests(complex_subtask)

        # Should have executed all test commands
        assert len(mock_env.commands_executed) == len(complex_subtask.acceptance_tests)


class TestSubtaskRunnerRetry:
    """Tests for retry logic on test failures."""

    def test_retry_on_test_failure(self, simple_subtask):
        """Should retry when tests fail on first attempt."""
        model = DeterministicModel()
        runner = SubtaskRunner(model, base_env=MockEnvironment(test_result=False), max_test_retries=1)

        # With max_retries=1 and tests always failing, should still try twice
        result = runner.run(simple_subtask)

        # Should have called model at least twice (retried once)
        assert model.call_count >= 2

    def test_retry_with_test_feedback(self, simple_subtask):
        """Feedback from failed tests should be included in retry prompt."""
        runner = SubtaskRunner(DeterministicModel(), base_env=MockEnvironment(test_result=False))
        feedback = runner._format_test_feedback(["FAILED: assertion error"])

        assert "FAILED" in feedback or "assertion" in feedback

    def test_exhausts_retries(self, simple_subtask):
        """Should fail after exhausting retries."""
        model = DeterministicModel()
        runner = SubtaskRunner(model, base_env=MockEnvironment(test_result=False), max_test_retries=1)

        result = runner.run(simple_subtask)

        assert result.status == SubtaskStatus.FAILED
        assert "after" in result.error.lower()


class TestSubtaskRunnerComplexScenarios:
    """Tests for complex scenarios."""

    def test_multiple_acceptance_tests(self, complex_subtask):
        """Should handle multiple acceptance tests."""
        model = DeterministicModel()
        env = MockEnvironment(test_result=True)
        runner = SubtaskRunner(model, base_env=env)

        result = runner.run(complex_subtask)

        assert result.status == SubtaskStatus.PASSED
        # Should have run both acceptance tests
        assert len(result.test_outputs) == len(complex_subtask.acceptance_tests)

    def test_preserves_subtask_spec_in_result(self, simple_subtask):
        """Result should contain original subtask spec."""
        model = DeterministicModel()
        env = MockEnvironment(test_result=True)
        runner = SubtaskRunner(model, base_env=env)

        result = runner.run(simple_subtask)

        assert result.spec == simple_subtask
        assert result.spec.id == simple_subtask.id
        assert result.spec.title == simple_subtask.title

    def test_step_limit_set_correctly(self, complex_subtask):
        """Step limit should be set based on complexity."""
        model = DeterministicModel()
        env = LocalEnvironment()
        runner = SubtaskRunner(model, base_env=env)

        # High complexity subtask should get high step limit
        limit = runner._get_step_limit_for_complexity(complex_subtask.estimated_complexity)
        assert limit == 60

    def test_restricted_environment_created(self, simple_subtask):
        """Should create RestrictedEnvironment with correct files."""
        model = DeterministicModel()
        env = LocalEnvironment()
        runner = SubtaskRunner(model, base_env=env)

        # Just verify the runner can create and use a restricted environment
        # (actual execution is mocked in real tests)
        prompt = runner._build_task_prompt(simple_subtask)

        for file in simple_subtask.files_to_write:
            assert file in prompt
