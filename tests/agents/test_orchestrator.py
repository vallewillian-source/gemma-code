"""Tests for the OrchestratorAgent."""

import json

import pytest

from src.gemmacode.agents.orchestrator import OrchestratorAgent, OrchestratorError
from src.gemmacode.orchestrator import DecompositionPlan, SubtaskSpec, TestCriterion


class DeterministicModel:
    """Mock model that returns predefined responses for testing."""

    def __init__(self, responses: list[str] | str):
        """Initialize with response(s).

        Args:
            responses: Single response or list of responses for sequential calls.
        """
        if isinstance(responses, str):
            self.responses = [responses]
        else:
            self.responses = responses
        self.call_count = 0
        self.last_messages = None
        self.config = {}

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict:
        """Return next response and track messages."""
        self.last_messages = messages
        if self.call_count >= len(self.responses):
            raise ValueError(f"DeterministicModel: expected {len(self.responses)} calls, got {self.call_count + 1}")
        response = self.responses[self.call_count]
        self.call_count += 1
        return {"content": response, "role": "assistant"}

    def format_message(self, role: str, content: str, **kwargs) -> dict:
        """Format a message."""
        return {"role": role, "content": content}

    def get_template_vars(self, **kwargs) -> dict:
        """Return template variables."""
        return {}


@pytest.fixture
def valid_plan_json():
    """A valid DecompositionPlan as JSON."""
    plan = {
        "original_task": "Implement user authentication",
        "subtasks": [
            {
                "id": "create-user-model",
                "title": "Create User Model",
                "description": "Create the User model with password hashing",
                "files_to_read": [],
                "files_to_write": ["src/models/user.py"],
                "context": "Use Pydantic v2 with strict mode",
                "dependencies": [],
                "acceptance_tests": [
                    {
                        "description": "User model validates password",
                        "test_command": "pytest tests/models/test_user.py::test_password_validation -v",
                    }
                ],
                "estimated_complexity": "low",
            }
        ],
        "global_context": "Use pathlib for all file operations",
        "heuristics_applied": ["python_project"],
    }
    return json.dumps(plan)


@pytest.fixture
def orchestrator_with_mock(valid_plan_json):
    """Create an OrchestratorAgent with a deterministic model."""
    model = DeterministicModel(valid_plan_json)
    return OrchestratorAgent(model, heuristics_applied=["python_project"])


class TestOrchestratorAgentBasic:
    """Basic tests for OrchestratorAgent."""

    def test_decompose_with_valid_json(self, orchestrator_with_mock, valid_plan_json):
        """Should successfully decompose when model returns valid JSON."""
        plan = orchestrator_with_mock.decompose(
            task="Implement user authentication",
            repo_map="src/\n  models/\n  tests/",
        )
        assert isinstance(plan, DecompositionPlan)
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].id == "create-user-model"

    def test_decompose_preserves_task_description(self, orchestrator_with_mock):
        """The returned plan should contain the original task."""
        task = "Implement user authentication"
        plan = orchestrator_with_mock.decompose(task=task, repo_map="src/")
        assert plan.original_task == "Implement user authentication"

    def test_prompt_includes_task(self, orchestrator_with_mock):
        """The prompt sent to the model should include the task description."""
        task = "Implement user authentication"
        orchestrator_with_mock.decompose(task=task, repo_map="src/")

        model = orchestrator_with_mock.model
        messages = model.last_messages
        user_messages = [m for m in messages if m.get("role") == "user"]
        assert len(user_messages) > 0
        assert task in user_messages[-1]["content"]

    def test_prompt_includes_heuristics(self, orchestrator_with_mock):
        """The prompt sent to the model should include heuristics."""
        orchestrator_with_mock.decompose(
            task="Implement user authentication",
            repo_map="src/",
        )

        model = orchestrator_with_mock.model
        messages = model.last_messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        assert len(system_messages) > 0
        # Check for a known heuristic rule ID
        system_content = system_messages[0]["content"]
        assert "test-location" in system_content or "Python Project" in system_content

    def test_prompt_includes_repo_map(self, orchestrator_with_mock):
        """The prompt sent to the model should include the repository map."""
        repo_map = "src/\n  models/\n  utils/"
        orchestrator_with_mock.decompose(
            task="Implement user authentication",
            repo_map=repo_map,
        )

        model = orchestrator_with_mock.model
        messages = model.last_messages
        user_messages = [m for m in messages if m.get("role") == "user"]
        assert len(user_messages) > 0
        assert repo_map in user_messages[-1]["content"]


class TestOrchestratorAgentJsonHandling:
    """Tests for JSON extraction and parsing."""

    def test_extract_json_from_plain_json(self, orchestrator_with_mock):
        """Should extract JSON from plain JSON response."""
        agent = orchestrator_with_mock
        plan_dict = {
            "original_task": "Test",
            "subtasks": [],
            "global_context": "",
            "heuristics_applied": [],
        }
        extracted = agent._extract_json(json.dumps(plan_dict))
        assert extracted == plan_dict

    def test_extract_json_from_markdown_block(self, orchestrator_with_mock):
        """Should extract JSON from markdown code block."""
        agent = orchestrator_with_mock
        plan_dict = {
            "original_task": "Test",
            "subtasks": [],
            "global_context": "",
            "heuristics_applied": [],
        }
        content = f"Here's the plan:\n\n```json\n{json.dumps(plan_dict)}\n```\n\nDone!"
        extracted = agent._extract_json(content)
        assert extracted == plan_dict

    def test_extract_json_with_surrounding_text(self, orchestrator_with_mock):
        """Should extract JSON even with surrounding text."""
        agent = orchestrator_with_mock
        plan_dict = {
            "original_task": "Test",
            "subtasks": [],
            "global_context": "",
            "heuristics_applied": [],
        }
        content = f"Thinking...{json.dumps(plan_dict)}...done"
        extracted = agent._extract_json(content)
        assert extracted == plan_dict

    def test_extract_json_invalid_raises_error(self, orchestrator_with_mock):
        """Should raise JSONDecodeError if no valid JSON found."""
        agent = orchestrator_with_mock
        with pytest.raises(json.JSONDecodeError):
            agent._extract_json("This is not JSON at all")


class TestOrchestratorAgentRetry:
    """Tests for retry logic on validation errors."""

    def test_retry_on_invalid_json_first_call(self, valid_plan_json):
        """Should retry when first response is invalid JSON."""
        invalid_response = "This is not JSON"
        model = DeterministicModel([invalid_response, valid_plan_json])
        agent = OrchestratorAgent(model, max_retries=3)

        plan = agent.decompose(
            task="Implement user authentication",
            repo_map="src/",
        )
        assert isinstance(plan, DecompositionPlan)
        assert model.call_count == 2  # Called twice: once invalid, once valid

    def test_retry_on_invalid_schema(self, valid_plan_json):
        """Should retry when JSON is valid but doesn't match schema."""
        invalid_schema = json.dumps({
            "original_task": "Test",
            # Missing required fields
        })
        model = DeterministicModel([invalid_schema, valid_plan_json])
        agent = OrchestratorAgent(model, max_retries=3)

        plan = agent.decompose(
            task="Implement user authentication",
            repo_map="src/",
        )
        assert isinstance(plan, DecompositionPlan)
        assert model.call_count == 2

    def test_exhaust_retries_raises_error(self):
        """Should raise OrchestratorError when retries are exhausted."""
        invalid_response = "Invalid"
        model = DeterministicModel([invalid_response] * 5)
        agent = OrchestratorAgent(model, max_retries=3)

        with pytest.raises(OrchestratorError):
            agent.decompose(
                task="Implement user authentication",
                repo_map="src/",
            )
        assert model.call_count == 3  # Tried 3 times


class TestOrchestratorAgentRetryMessages:
    """Tests for message history during retries."""

    def test_error_message_added_on_retry(self, valid_plan_json):
        """Error message should be added to conversation on retry."""
        invalid_response = "This is not JSON"
        model = DeterministicModel([invalid_response, valid_plan_json])
        agent = OrchestratorAgent(model, max_retries=3)

        agent.decompose(
            task="Implement user authentication",
            repo_map="src/",
        )

        messages = model.last_messages
        # Should have: system, user, assistant (invalid), user (error message)
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert "error" in messages[3]["content"].lower() or "fix it" in messages[3]["content"].lower()


class TestOrchestratorAgentWithoutHeuristics:
    """Tests when heuristics are not specified."""

    def test_decompose_without_heuristics(self, valid_plan_json):
        """Should work without specifying heuristics (uses all)."""
        model = DeterministicModel(valid_plan_json)
        agent = OrchestratorAgent(model, heuristics_applied=None)

        plan = agent.decompose(
            task="Implement user authentication",
            repo_map="src/",
        )
        assert isinstance(plan, DecompositionPlan)
        # Heuristics should be loaded (but we can't guarantee specific ones without inspecting prompt)
        messages = model.last_messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        # Should include heuristics from all files
        assert len(system_messages[0]["content"]) > 1000  # Substantial system prompt


class TestOrchestratorAgentComplexPlans:
    """Tests with more complex decomposition plans."""

    def test_multiple_subtasks_with_dependencies(self):
        """Should handle plans with multiple subtasks and dependencies."""
        plan = {
            "original_task": "Implement user authentication system",
            "subtasks": [
                {
                    "id": "create-user-model",
                    "title": "Create User Model",
                    "description": "Create the User model",
                    "files_to_read": [],
                    "files_to_write": ["src/models/user.py"],
                    "context": "Use Pydantic v2",
                    "dependencies": [],
                    "acceptance_tests": [
                        {
                            "description": "User model works",
                            "test_command": "pytest tests/models/test_user.py -v",
                        }
                    ],
                    "estimated_complexity": "low",
                },
                {
                    "id": "create-auth-service",
                    "title": "Create Authentication Service",
                    "description": "Create auth service",
                    "files_to_read": ["src/models/user.py"],
                    "files_to_write": ["src/services/auth.py"],
                    "context": "Use the User model",
                    "dependencies": ["create-user-model"],
                    "acceptance_tests": [
                        {
                            "description": "Auth service works",
                            "test_command": "pytest tests/services/test_auth.py -v",
                        }
                    ],
                    "estimated_complexity": "medium",
                },
            ],
            "global_context": "User auth system",
            "heuristics_applied": ["python_project"],
        }
        model = DeterministicModel(json.dumps(plan))
        agent = OrchestratorAgent(model)

        result = agent.decompose(task="Implement auth", repo_map="src/")
        assert len(result.subtasks) == 2
        assert result.subtasks[0].id == "create-user-model"
        assert result.subtasks[1].id == "create-auth-service"
        assert result.subtasks[1].dependencies == ["create-user-model"]

    def test_preserves_heuristics_applied_field(self):
        """Should preserve the heuristics_applied field from the plan."""
        plan = {
            "original_task": "Test task",
            "subtasks": [],
            "global_context": "",
            "heuristics_applied": ["python_project", "testing_patterns"],
        }
        model = DeterministicModel(json.dumps(plan))
        agent = OrchestratorAgent(model)

        result = agent.decompose(task="Test", repo_map="src/")
        assert result.heuristics_applied == ["python_project", "testing_patterns"]
