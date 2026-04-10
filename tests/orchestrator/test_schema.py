"""Tests for orchestrator schema models."""

import json

import pytest
from pydantic import ValidationError

from gemmacode.orchestrator import (
    DecompositionPlan,
    SubtaskResult,
    SubtaskSpec,
    SubtaskStatus,
    TestCriterion,
)


class TestTestCriterion:
    """Tests for TestCriterion model."""

    def test_creation_with_required_fields(self):
        criterion = TestCriterion(
            description="should return 404 when user not found",
            test_command="pytest tests/test_users.py::test_get_missing",
        )
        assert criterion.description == "should return 404 when user not found"
        assert criterion.test_command == "pytest tests/test_users.py::test_get_missing"

    def test_missing_required_field_raises_error(self):
        with pytest.raises(ValidationError):
            TestCriterion(description="test description")

    def test_serialization(self):
        criterion = TestCriterion(
            description="test",
            test_command="pytest test.py",
        )
        data = criterion.model_dump()
        assert data["description"] == "test"
        assert data["test_command"] == "pytest test.py"

    def test_json_round_trip(self):
        original = TestCriterion(
            description="should pass",
            test_command="pytest tests/test.py",
        )
        json_str = original.model_dump_json()
        restored = TestCriterion.model_validate_json(json_str)
        assert restored.description == original.description
        assert restored.test_command == original.test_command


class TestSubtaskSpec:
    """Tests for SubtaskSpec model."""

    def test_minimal_creation(self):
        spec = SubtaskSpec(
            id="subtask-01",
            title="Test Task",
            description="Test description",
        )
        assert spec.id == "subtask-01"
        assert spec.title == "Test Task"
        assert spec.description == "Test description"
        assert spec.files_to_read == []
        assert spec.files_to_write == []
        assert spec.context == ""
        assert spec.dependencies == []
        assert spec.acceptance_tests == []
        assert spec.estimated_complexity == "medium"

    def test_full_creation(self):
        criterion = TestCriterion(
            description="should work",
            test_command="pytest test.py",
        )
        spec = SubtaskSpec(
            id="subtask-01",
            title="Test Task",
            description="Test description",
            files_to_read=["src/foo.py"],
            files_to_write=["src/bar.py"],
            context="Important context",
            dependencies=["subtask-00"],
            acceptance_tests=[criterion],
            estimated_complexity="high",
        )
        assert spec.id == "subtask-01"
        assert spec.files_to_read == ["src/foo.py"]
        assert spec.files_to_write == ["src/bar.py"]
        assert spec.context == "Important context"
        assert spec.dependencies == ["subtask-00"]
        assert len(spec.acceptance_tests) == 1
        assert spec.estimated_complexity == "high"

    def test_invalid_complexity_raises_error(self):
        with pytest.raises(ValidationError):
            SubtaskSpec(
                id="subtask-01",
                title="Test",
                description="Test",
                estimated_complexity="invalid",  # type: ignore
            )

    def test_valid_complexity_values(self):
        for complexity in ["low", "medium", "high"]:
            spec = SubtaskSpec(
                id="subtask-01",
                title="Test",
                description="Test",
                estimated_complexity=complexity,  # type: ignore
            )
            assert spec.estimated_complexity == complexity

    def test_serialization_with_nested_criteria(self):
        spec = SubtaskSpec(
            id="subtask-01",
            title="Test",
            description="Test",
            acceptance_tests=[
                TestCriterion(description="test1", test_command="pytest t1.py"),
                TestCriterion(description="test2", test_command="pytest t2.py"),
            ],
        )
        data = spec.model_dump()
        assert len(data["acceptance_tests"]) == 2
        assert data["acceptance_tests"][0]["description"] == "test1"

    def test_json_round_trip(self):
        original = SubtaskSpec(
            id="subtask-01",
            title="Test Task",
            description="Test description",
            files_to_read=["a.py", "b.py"],
            files_to_write=["c.py"],
            context="Context info",
            dependencies=["subtask-00"],
            acceptance_tests=[
                TestCriterion(description="test", test_command="pytest"),
            ],
            estimated_complexity="high",
        )
        json_str = original.model_dump_json()
        restored = SubtaskSpec.model_validate_json(json_str)
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.files_to_read == original.files_to_read
        assert restored.dependencies == original.dependencies
        assert len(restored.acceptance_tests) == 1


class TestDecompositionPlan:
    """Tests for DecompositionPlan model."""

    def test_minimal_creation(self):
        spec = SubtaskSpec(id="task-1", title="Task 1", description="Description 1")
        plan = DecompositionPlan(
            original_task="Do something",
            subtasks=[spec],
        )
        assert plan.original_task == "Do something"
        assert len(plan.subtasks) == 1
        assert plan.global_context == ""
        assert plan.heuristics_applied == []

    def test_full_creation(self):
        spec1 = SubtaskSpec(id="task-1", title="Task 1", description="Desc 1")
        spec2 = SubtaskSpec(id="task-2", title="Task 2", description="Desc 2", dependencies=["task-1"])
        plan = DecompositionPlan(
            original_task="Build API",
            subtasks=[spec1, spec2],
            global_context="Use FastAPI",
            heuristics_applied=["python_project", "testing_patterns"],
        )
        assert plan.original_task == "Build API"
        assert len(plan.subtasks) == 2
        assert plan.global_context == "Use FastAPI"
        assert plan.heuristics_applied == ["python_project", "testing_patterns"]

    def test_empty_subtasks_list(self):
        plan = DecompositionPlan(
            original_task="Task",
            subtasks=[],
        )
        assert len(plan.subtasks) == 0

    def test_subtasks_with_dependencies(self):
        spec1 = SubtaskSpec(id="a", title="A", description="A")
        spec2 = SubtaskSpec(id="b", title="B", description="B", dependencies=["a"])
        spec3 = SubtaskSpec(id="c", title="C", description="C", dependencies=["a", "b"])
        plan = DecompositionPlan(
            original_task="Task",
            subtasks=[spec1, spec2, spec3],
        )
        assert plan.subtasks[1].dependencies == ["a"]
        assert plan.subtasks[2].dependencies == ["a", "b"]

    def test_json_round_trip_with_nested_structure(self):
        spec = SubtaskSpec(
            id="task-1",
            title="Task 1",
            description="Description 1",
            files_to_write=["src/main.py"],
            acceptance_tests=[
                TestCriterion(description="should work", test_command="pytest"),
            ],
        )
        plan = DecompositionPlan(
            original_task="Build system",
            subtasks=[spec],
            global_context="Global info",
            heuristics_applied=["test"],
        )
        json_str = plan.model_dump_json()
        restored = DecompositionPlan.model_validate_json(json_str)
        assert restored.original_task == plan.original_task
        assert len(restored.subtasks) == 1
        assert restored.subtasks[0].id == "task-1"
        assert restored.global_context == "Global info"

    def test_validate_from_dict(self):
        data = {
            "original_task": "Task",
            "subtasks": [
                {
                    "id": "t1",
                    "title": "Title",
                    "description": "Desc",
                    "files_to_read": [],
                    "files_to_write": [],
                    "context": "",
                    "dependencies": [],
                    "acceptance_tests": [],
                    "estimated_complexity": "low",
                }
            ],
            "global_context": "",
            "heuristics_applied": [],
        }
        plan = DecompositionPlan.model_validate(data)
        assert plan.original_task == "Task"
        assert plan.subtasks[0].id == "t1"


class TestSubtaskStatus:
    """Tests for SubtaskStatus enum."""

    def test_all_status_values_exist(self):
        assert SubtaskStatus.PENDING == "pending"
        assert SubtaskStatus.RUNNING == "running"
        assert SubtaskStatus.PASSED == "passed"
        assert SubtaskStatus.FAILED == "failed"
        assert SubtaskStatus.TIMEOUT == "timeout"

    def test_status_is_string_enum(self):
        status = SubtaskStatus.PASSED
        assert isinstance(status, str)
        assert status == "passed"


class TestSubtaskResult:
    """Tests for SubtaskResult model."""

    def test_result_with_passed_status(self):
        spec = SubtaskSpec(id="task-1", title="Task", description="Desc")
        result = SubtaskResult(
            spec=spec,
            status=SubtaskStatus.PASSED,
            error=None,
        )
        assert result.status == SubtaskStatus.PASSED
        assert result.error is None
        assert result.test_outputs == []

    def test_result_with_failed_status(self):
        spec = SubtaskSpec(id="task-1", title="Task", description="Desc")
        result = SubtaskResult(
            spec=spec,
            status=SubtaskStatus.FAILED,
            error="Test assertion failed",
            test_outputs=["FAILED test_foo: assert 1 == 2"],
        )
        assert result.status == SubtaskStatus.FAILED
        assert result.error == "Test assertion failed"
        assert len(result.test_outputs) == 1

    def test_result_with_all_fields(self):
        spec = SubtaskSpec(
            id="task-1",
            title="Task",
            description="Desc",
            acceptance_tests=[
                TestCriterion(description="test1", test_command="pytest test1.py"),
            ],
        )
        result = SubtaskResult(
            spec=spec,
            status=SubtaskStatus.PASSED,
            error=None,
            test_outputs=["test_foo PASSED", "test_bar PASSED"],
        )
        assert result.spec.id == "task-1"
        assert result.status == SubtaskStatus.PASSED
        assert len(result.test_outputs) == 2

    def test_serialization(self):
        spec = SubtaskSpec(id="task-1", title="Task", description="Desc")
        result = SubtaskResult(
            spec=spec,
            status=SubtaskStatus.PASSED,
        )
        data = result.model_dump()
        assert data["status"] == "passed"
        assert data["spec"]["id"] == "task-1"

    def test_json_round_trip(self):
        spec = SubtaskSpec(
            id="task-1",
            title="Task",
            description="Desc",
            files_to_write=["src/main.py"],
        )
        result = SubtaskResult(
            spec=spec,
            status=SubtaskStatus.PASSED,
            error=None,
            test_outputs=["test PASSED"],
        )
        json_str = result.model_dump_json()
        restored = SubtaskResult.model_validate_json(json_str)
        assert restored.spec.id == "task-1"
        assert restored.status == SubtaskStatus.PASSED
        assert restored.test_outputs == ["test PASSED"]

    def test_invalid_status_raises_error(self):
        spec = SubtaskSpec(id="task-1", title="Task", description="Desc")
        with pytest.raises(ValidationError):
            SubtaskResult(
                spec=spec,
                status="invalid_status",  # type: ignore
            )


class TestIntegration:
    """Integration tests combining multiple models."""

    def test_full_pipeline_serialization(self):
        spec1 = SubtaskSpec(
            id="subtask-01",
            title="Create models",
            description="Create user and post models",
            files_to_write=["src/models.py"],
            acceptance_tests=[
                TestCriterion(description="models importable", test_command="python -c 'from src.models import User'"),
            ],
            estimated_complexity="low",
        )
        spec2 = SubtaskSpec(
            id="subtask-02",
            title="Create API endpoints",
            description="Create CRUD endpoints for users and posts",
            files_to_read=["src/models.py"],
            files_to_write=["src/routes.py"],
            dependencies=["subtask-01"],
            acceptance_tests=[
                TestCriterion(description="GET /users works", test_command="pytest tests/test_routes.py::test_get_users"),
            ],
            estimated_complexity="medium",
        )

        plan = DecompositionPlan(
            original_task="Build a REST API for a blog",
            subtasks=[spec1, spec2],
            global_context="Use FastAPI with SQLite database",
            heuristics_applied=["python_project", "testing_patterns"],
        )

        # Serialize to JSON
        json_str = plan.model_dump_json(indent=2)
        assert "subtask-01" in json_str
        assert "subtask-02" in json_str
        assert "FastAPI" in json_str

        # Deserialize from JSON
        restored = DecompositionPlan.model_validate_json(json_str)
        assert restored.original_task == plan.original_task
        assert len(restored.subtasks) == 2
        assert restored.subtasks[1].dependencies == ["subtask-01"]

        # Create results
        result1 = SubtaskResult(spec=restored.subtasks[0], status=SubtaskStatus.PASSED, test_outputs=["test PASSED"])
        result2 = SubtaskResult(spec=restored.subtasks[1], status=SubtaskStatus.PASSED, test_outputs=["test PASSED"])

        # Verify results are valid
        assert result1.status == SubtaskStatus.PASSED
        assert result2.status == SubtaskStatus.PASSED
        assert result1.spec.id == "subtask-01"
        assert result2.spec.dependencies == ["subtask-01"]

    def test_plan_with_complex_dependencies(self):
        # Create a diamond dependency: A -> B,C -> D
        spec_a = SubtaskSpec(id="a", title="A", description="A")
        spec_b = SubtaskSpec(id="b", title="B", description="B", dependencies=["a"])
        spec_c = SubtaskSpec(id="c", title="C", description="C", dependencies=["a"])
        spec_d = SubtaskSpec(id="d", title="D", description="D", dependencies=["b", "c"])

        plan = DecompositionPlan(
            original_task="Complex task",
            subtasks=[spec_a, spec_b, spec_c, spec_d],
        )

        # Verify structure
        assert plan.subtasks[0].dependencies == []
        assert plan.subtasks[1].dependencies == ["a"]
        assert plan.subtasks[2].dependencies == ["a"]
        assert plan.subtasks[3].dependencies == ["b", "c"]

        # Serialize and deserialize
        restored = DecompositionPlan.model_validate_json(plan.model_dump_json())
        assert len(restored.subtasks) == 4
        assert restored.subtasks[3].dependencies == ["b", "c"]
