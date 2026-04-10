"""Data models for task decomposition and orchestration."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SubtaskStatus(str, Enum):
    """Status of a subtask execution."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TestCriterion(BaseModel):
    """A test criterion for acceptance of a subtask."""

    description: str = Field(..., description="Natural language description of what the test checks")
    test_command: str = Field(..., description="Command to run the test (e.g., 'pytest tests/test_foo.py::test_bar')")

    model_config = {"json_schema_extra": {"example": {"description": "should return 404 when user not found", "test_command": "pytest tests/test_users.py::test_get_missing -v"}}}


class SubtaskSpec(BaseModel):
    """Specification for a single subtask to be executed by a smaller model."""

    id: str = Field(..., description="Unique identifier for this subtask (e.g., 'subtask-01')")
    title: str = Field(..., description="Short title of the subtask")
    description: str = Field(..., description="What to implement, in clear natural language")
    files_to_read: list[str] = Field(default_factory=list, description="Files the model can read for context")
    files_to_write: list[str] = Field(default_factory=list, description="Files the model should create/modify")
    context: str = Field(default="", description="Specific context pre-compiled by the orchestrator")
    dependencies: list[str] = Field(default_factory=list, description="IDs of subtasks that must complete first")
    acceptance_tests: list[TestCriterion] = Field(default_factory=list, description="Tests that must pass for completion")
    estimated_complexity: Literal["low", "medium", "high"] = Field(
        default="medium", description="Estimated complexity for step limit allocation"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "subtask-01",
                "title": "Create user model",
                "description": "Create a User dataclass with email and password fields",
                "files_to_read": ["src/models/__init__.py"],
                "files_to_write": ["src/models/user.py"],
                "context": "Users are stored in a PostgreSQL database via SQLAlchemy",
                "dependencies": [],
                "acceptance_tests": [{"description": "User can be instantiated with email and password", "test_command": "pytest tests/test_user.py::test_user_creation"}],
                "estimated_complexity": "low",
            }
        }
    }


class DecompositionPlan(BaseModel):
    """A complete decomposition plan for a task into subtasks."""

    original_task: str = Field(..., description="The original task received")
    subtasks: list[SubtaskSpec] = Field(..., description="List of subtasks to execute")
    global_context: str = Field(default="", description="Context that applies to all subtasks")
    heuristics_applied: list[str] = Field(default_factory=list, description="Traceability: which heuristics were used")

    model_config = {
        "json_schema_extra": {
            "example": {
                "original_task": "Build a REST API for a todo application",
                "global_context": "Use FastAPI with Pydantic models. Store data in SQLite.",
                "subtasks": [
                    {
                        "id": "subtask-01",
                        "title": "Create Todo model",
                        "description": "...",
                        "files_to_read": [],
                        "files_to_write": ["src/models.py"],
                        "context": "",
                        "dependencies": [],
                        "acceptance_tests": [],
                        "estimated_complexity": "low",
                    }
                ],
                "heuristics_applied": ["single_responsibility", "testing_patterns"],
            }
        }
    }


class SubtaskResult(BaseModel):
    """Result of executing a subtask."""

    spec: SubtaskSpec = Field(..., description="The original subtask specification")
    status: SubtaskStatus = Field(..., description="Current execution status")
    error: str | None = Field(default=None, description="Error message if status is 'failed' or 'timeout'")
    test_outputs: list[str] = Field(default_factory=list, description="Output from running acceptance tests")

    model_config = {
        "json_schema_extra": {
            "example": {
                "spec": {
                    "id": "subtask-01",
                    "title": "Create user model",
                    "description": "Create a User dataclass",
                    "files_to_read": [],
                    "files_to_write": ["src/models/user.py"],
                    "context": "",
                    "dependencies": [],
                    "acceptance_tests": [],
                    "estimated_complexity": "low",
                },
                "status": "passed",
                "error": None,
                "test_outputs": ["test_user_creation PASSED"],
            }
        }
    }
