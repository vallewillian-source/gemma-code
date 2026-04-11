"""Tests for overnight orchestration pipeline."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.gemmacode.orchestrator import (
    DecompositionPlan,
    SubtaskResult,
    SubtaskSpec,
    SubtaskStatus,
    TestCriterion,
)
from src.gemmacode.run.overnight import app, load_plan, save_result


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_plan():
    """Create a sample decomposition plan for testing."""
    return DecompositionPlan(
        original_task="Implement a simple REST API",
        subtasks=[
            SubtaskSpec(
                id="setup-models",
                title="Setup data models",
                description="Create Pydantic models for API data",
                files_to_read=[],
                files_to_write=["src/models.py"],
                context="Use Pydantic v2",
                dependencies=[],
                acceptance_tests=[
                    TestCriterion(
                        description="Models can be imported",
                        test_command="python -c 'from models import *'",
                    )
                ],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="setup-routes",
                title="Setup API routes",
                description="Create FastAPI routes",
                files_to_read=["src/models.py"],
                files_to_write=["src/routes.py"],
                context="Use FastAPI",
                dependencies=["setup-models"],
                acceptance_tests=[
                    TestCriterion(
                        description="Routes can be imported",
                        test_command="python -c 'from routes import *'",
                    )
                ],
                estimated_complexity="medium",
            ),
            SubtaskSpec(
                id="add-tests",
                title="Add API tests",
                description="Create test suite for API",
                files_to_read=["src/models.py", "src/routes.py"],
                files_to_write=["tests/test_api.py"],
                context="Use pytest",
                dependencies=["setup-routes"],
                acceptance_tests=[
                    TestCriterion(
                        description="Tests pass",
                        test_command="pytest tests/test_api.py -v",
                    )
                ],
                estimated_complexity="medium",
            ),
        ],
        global_context="Build a simple REST API",
        heuristics_applied=["python_project", "testing_patterns"],
    )


@pytest.fixture
def deterministic_model():
    """Create a mock model that returns valid responses."""
    model = MagicMock()
    model.query.return_value = {
        "content": '{"result": "success"}',
        "role": "assistant",
    }
    model.serialize.return_value = {"type": "mock"}
    return model


@pytest.fixture
def runner_cli():
    """Create a CLI test runner."""
    return CliRunner()


class TestLoadPlan:
    """Tests for load_plan function."""

    def test_load_plan_round_trip(self, sample_plan, temp_output_dir):
        """load_plan should round-trip with plan.json."""
        plan_path = temp_output_dir / "plan.json"

        # Save plan
        with open(plan_path, "w") as f:
            json.dump(sample_plan.model_dump(), f)

        # Load plan
        loaded = load_plan(plan_path)

        # Verify round-trip
        assert loaded.original_task == sample_plan.original_task
        assert len(loaded.subtasks) == len(sample_plan.subtasks)
        assert loaded.subtasks[0].id == sample_plan.subtasks[0].id

    def test_load_plan_nonexistent_file(self):
        """load_plan should raise error for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            load_plan(Path("/nonexistent/plan.json"))

    def test_load_plan_invalid_json(self, temp_output_dir):
        """load_plan should raise error for invalid JSON."""
        plan_path = temp_output_dir / "plan.json"
        with open(plan_path, "w") as f:
            f.write("invalid json")

        with pytest.raises(json.JSONDecodeError):
            load_plan(plan_path)


class TestSaveResult:
    """Tests for save_result function."""

    def test_save_result_creates_file(self, temp_output_dir):
        """save_result should create a result file."""
        spec = SubtaskSpec(
            id="test-task",
            title="Test",
            description="",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        )
        result = SubtaskResult(
            spec=spec,
            status=SubtaskStatus.PASSED,
            error=None,
            test_outputs=["test output"],
        )

        save_result(result, temp_output_dir)

        result_file = temp_output_dir / "result_test-task.json"
        assert result_file.exists()

        # Verify content
        with open(result_file) as f:
            data = json.load(f)
        assert data["spec"]["id"] == "test-task"
        assert data["status"] == "passed"

    def test_save_result_preserves_error(self, temp_output_dir):
        """save_result should preserve error messages."""
        spec = SubtaskSpec(
            id="failed-task",
            title="Failed",
            description="",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        )
        result = SubtaskResult(
            spec=spec,
            status=SubtaskStatus.FAILED,
            error="Tests failed",
            test_outputs=[],
        )

        save_result(result, temp_output_dir)

        result_file = temp_output_dir / "result_failed-task.json"
        with open(result_file) as f:
            data = json.load(f)
        assert data["error"] == "Tests failed"


class TestOvernightCLI:
    """Tests for overnight CLI."""

    def test_help_option(self, runner_cli):
        """--help should show help text."""
        result = runner_cli.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "overnight" in result.stdout.lower()

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    def test_dry_run_mode(
        self,
        mock_orchestrator_agent,
        mock_get_model,
        mock_get_config_from_spec,
        mock_build_repo_map,
        sample_plan,
        temp_output_dir,
        runner_cli,
    ):
        """--dry-run should decompose but not execute subtasks."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo map content"
        mock_get_config_from_spec.return_value = {}
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model

        orchestrator_instance = MagicMock()
        orchestrator_instance.decompose.return_value = sample_plan
        mock_orchestrator_agent.return_value = orchestrator_instance

        # Run with dry-run
        result = runner_cli.invoke(
            app,
            [
                "--task",
                "Test task",
                "--output",
                str(temp_output_dir),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "dry-run" in result.stdout.lower() or "decomposition" in result.stdout.lower()

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    @patch("src.gemmacode.run.overnight.SubtaskRunner")
    def test_pipeline_execution_order(
        self,
        mock_runner_class,
        mock_orchestrator_agent,
        mock_get_model,
        mock_get_config_from_spec,
        mock_build_repo_map,
        sample_plan,
        temp_output_dir,
        runner_cli,
    ):
        """Pipeline should execute subtasks in topologically sorted order."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo map"
        mock_get_config_from_spec.return_value = {}
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model

        orchestrator_instance = MagicMock()
        orchestrator_instance.decompose.return_value = sample_plan
        mock_orchestrator_agent.return_value = orchestrator_instance

        # Track execution order
        execution_order = []

        def track_execution(spec):
            execution_order.append(spec.id)
            return SubtaskResult(
                spec=spec,
                status=SubtaskStatus.PASSED,
                error=None,
                test_outputs=[],
            )

        runner_instance = MagicMock()
        runner_instance.run.side_effect = track_execution
        mock_runner_class.return_value = runner_instance

        # Run pipeline
        result = runner_cli.invoke(
            app,
            [
                "--task",
                "Test task",
                "--output",
                str(temp_output_dir),
            ],
        )

        # Verify execution order respects dependencies
        assert result.exit_code == 0
        assert execution_order.index("setup-models") < execution_order.index("setup-routes")
        assert execution_order.index("setup-routes") < execution_order.index("add-tests")

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    @patch("src.gemmacode.run.overnight.SubtaskRunner")
    def test_pipeline_continues_on_failure(
        self,
        mock_runner_class,
        mock_orchestrator_agent,
        mock_get_model,
        mock_get_config_from_spec,
        mock_build_repo_map,
        sample_plan,
        temp_output_dir,
        runner_cli,
    ):
        """Pipeline should continue with other subtasks if one fails."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo map"
        mock_get_config_from_spec.return_value = {}
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model

        orchestrator_instance = MagicMock()
        orchestrator_instance.decompose.return_value = sample_plan
        mock_orchestrator_agent.return_value = orchestrator_instance

        # Make one subtask fail
        def return_result(spec):
            if spec.id == "setup-routes":
                return SubtaskResult(
                    spec=spec,
                    status=SubtaskStatus.FAILED,
                    error="Test failed",
                    test_outputs=[],
                )
            else:
                return SubtaskResult(
                    spec=spec,
                    status=SubtaskStatus.PASSED,
                    error=None,
                    test_outputs=[],
                )

        runner_instance = MagicMock()
        runner_instance.run.side_effect = return_result
        mock_runner_class.return_value = runner_instance

        # Run pipeline
        result = runner_cli.invoke(
            app,
            [
                "--task",
                "Test task",
                "--output",
                str(temp_output_dir),
            ],
        )

        # Pipeline should complete (not exit with error)
        assert result.exit_code == 0

        # Summary should include all subtasks
        summary_file = temp_output_dir / "summary.json"
        assert summary_file.exists()

        with open(summary_file) as f:
            summary = json.load(f)
        assert summary["total_subtasks"] == 3
        assert summary["failed"] == 1
        assert summary["passed"] == 2

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    @patch("src.gemmacode.run.overnight.SubtaskRunner")
    def test_summary_generation(
        self,
        mock_runner_class,
        mock_orchestrator_agent,
        mock_get_model,
        mock_get_config_from_spec,
        mock_build_repo_map,
        sample_plan,
        temp_output_dir,
        runner_cli,
    ):
        """Pipeline should generate complete summary.json."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo map"
        mock_get_config_from_spec.return_value = {}
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model

        orchestrator_instance = MagicMock()
        orchestrator_instance.decompose.return_value = sample_plan
        mock_orchestrator_agent.return_value = orchestrator_instance

        runner_instance = MagicMock()
        runner_instance.run.side_effect = lambda spec: SubtaskResult(
            spec=spec,
            status=SubtaskStatus.PASSED,
            error=None,
            test_outputs=[],
        )
        mock_runner_class.return_value = runner_instance

        # Run pipeline
        result = runner_cli.invoke(
            app,
            [
                "--task",
                "Test task",
                "--output",
                str(temp_output_dir),
            ],
        )

        # Verify summary
        assert result.exit_code == 0

        summary_file = temp_output_dir / "summary.json"
        assert summary_file.exists()

        with open(summary_file) as f:
            summary = json.load(f)

        assert summary["task"] == "Test task"
        assert summary["total_subtasks"] == 3
        assert summary["passed"] == 3
        assert summary["failed"] == 0
        assert len(summary["results"]) == 3

        # Verify each result has required fields
        for result_entry in summary["results"]:
            assert "id" in result_entry
            assert "title" in result_entry
            assert "status" in result_entry

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    def test_plan_saved_to_file(
        self,
        mock_orchestrator_agent,
        mock_get_model,
        mock_get_config_from_spec,
        mock_build_repo_map,
        sample_plan,
        temp_output_dir,
        runner_cli,
    ):
        """Pipeline should save decomposition plan to plan.json."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo map"
        mock_get_config_from_spec.return_value = {}
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model

        orchestrator_instance = MagicMock()
        orchestrator_instance.decompose.return_value = sample_plan
        mock_orchestrator_agent.return_value = orchestrator_instance

        # Run with dry-run to just decompose
        result = runner_cli.invoke(
            app,
            [
                "--task",
                "Test task",
                "--output",
                str(temp_output_dir),
                "--dry-run",
            ],
        )

        # Verify plan.json was saved
        assert result.exit_code == 0

        plan_file = temp_output_dir / "plan.json"
        assert plan_file.exists()

        loaded_plan = load_plan(plan_file)
        assert loaded_plan.original_task == sample_plan.original_task
        assert len(loaded_plan.subtasks) == len(sample_plan.subtasks)
