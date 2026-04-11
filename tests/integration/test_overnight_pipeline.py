"""Integration tests for the complete overnight pipeline."""

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
from src.gemmacode.run.overnight import app, load_plan


@pytest.fixture
def deterministic_plan():
    """Create a deterministic plan with 3 subtasks."""
    return DecompositionPlan(
        original_task="Implement a simple system",
        subtasks=[
            SubtaskSpec(
                id="setup",
                title="Setup",
                description="Setup infrastructure",
                files_to_read=[],
                files_to_write=["setup.py"],
                context="Create setup script",
                dependencies=[],
                acceptance_tests=[
                    TestCriterion(
                        description="Setup runs",
                        test_command="echo ok",
                    )
                ],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="implement",
                title="Implement",
                description="Implement main logic",
                files_to_read=["setup.py"],
                files_to_write=["main.py"],
                context="Create main module",
                dependencies=["setup"],
                acceptance_tests=[
                    TestCriterion(
                        description="Main module works",
                        test_command="echo ok",
                    )
                ],
                estimated_complexity="medium",
            ),
            SubtaskSpec(
                id="test",
                title="Test",
                description="Add tests",
                files_to_read=["setup.py", "main.py"],
                files_to_write=["test.py"],
                context="Create test suite",
                dependencies=["setup"],
                acceptance_tests=[
                    TestCriterion(
                        description="Tests pass",
                        test_command="echo ok",
                    )
                ],
                estimated_complexity="medium",
            ),
        ],
        global_context="Build a complete system",
        heuristics_applied=[],
    )


class MockOrchestratorAgent:
    """Mock orchestrator that returns a deterministic plan."""

    def __init__(self, model, heuristics_applied=None):
        """Initialize with a model."""
        self.model = model
        self.heuristics_applied = heuristics_applied or []

    def decompose(self, task, repo_map):
        """Return the deterministic plan."""
        # Verify inputs
        assert task is not None
        assert repo_map is not None
        # Return plan without API call
        return DecompositionPlan(
            original_task=task,
            subtasks=[
                SubtaskSpec(
                    id="subtask-a",
                    title="Subtask A",
                    description="No dependencies",
                    files_to_read=[],
                    files_to_write=["a.py"],
                    context="",
                    dependencies=[],
                    acceptance_tests=[
                        TestCriterion(
                            description="A passes",
                            test_command="echo ok",
                        )
                    ],
                    estimated_complexity="low",
                ),
                SubtaskSpec(
                    id="subtask-b",
                    title="Subtask B",
                    description="Depends on A",
                    files_to_read=["a.py"],
                    files_to_write=["b.py"],
                    context="",
                    dependencies=["subtask-a"],
                    acceptance_tests=[
                        TestCriterion(
                            description="B passes",
                            test_command="echo ok",
                        )
                    ],
                    estimated_complexity="low",
                ),
                SubtaskSpec(
                    id="subtask-c",
                    title="Subtask C",
                    description="Depends on A",
                    files_to_read=["a.py"],
                    files_to_write=["c.py"],
                    context="",
                    dependencies=["subtask-a"],
                    acceptance_tests=[
                        TestCriterion(
                            description="C passes",
                            test_command="echo ok",
                        )
                    ],
                    estimated_complexity="low",
                ),
            ],
            global_context="",
            heuristics_applied=[],
        )


class MockSubtaskRunner:
    """Mock runner that tracks execution order."""

    execution_order = []

    def __init__(self, model):
        """Initialize with a model."""
        self.model = model

    def run(self, spec):
        """Track execution and return success."""
        MockSubtaskRunner.execution_order.append(spec.id)
        return SubtaskResult(
            spec=spec,
            status=SubtaskStatus.PASSED,
            error=None,
            test_outputs=[],
        )


class TestOvernightPipelineIntegration:
    """Integration tests for overnight pipeline."""

    def setup_method(self):
        """Reset execution order before each test."""
        MockSubtaskRunner.execution_order = []

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    @patch("src.gemmacode.run.overnight.SubtaskRunner")
    def test_subtask_execution_order(
        self,
        mock_runner_class,
        mock_orchestrator_class,
        mock_get_model,
        mock_get_config,
        mock_build_repo_map,
    ):
        """Subtask A should execute before B and C."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo"
        mock_get_config.return_value = {}
        mock_get_model.return_value = MagicMock()

        mock_orchestrator_class.side_effect = MockOrchestratorAgent
        mock_runner_class.side_effect = MockSubtaskRunner

        # Run CLI
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--task",
                "Test",
                "--output",
                tempfile.mkdtemp(),
            ],
        )

        assert result.exit_code == 0

        # Verify execution order
        execution = MockSubtaskRunner.execution_order
        assert execution.index("subtask-a") < execution.index("subtask-b")
        assert execution.index("subtask-a") < execution.index("subtask-c")

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    @patch("src.gemmacode.run.overnight.SubtaskRunner")
    def test_dependency_blocking(
        self,
        mock_runner_class,
        mock_orchestrator_class,
        mock_get_model,
        mock_get_config,
        mock_build_repo_map,
    ):
        """Subtask B should only execute after A is passed."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo"
        mock_get_config.return_value = {}
        mock_get_model.return_value = MagicMock()

        mock_orchestrator_class.side_effect = MockOrchestratorAgent
        mock_runner_class.side_effect = MockSubtaskRunner

        # Run CLI
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                [
                    "--task",
                    "Test",
                    "--output",
                    tmpdir,
                ],
            )

            assert result.exit_code == 0

            # Verify A executed before B (dependency satisfied)
            execution = MockSubtaskRunner.execution_order
            assert execution.index("subtask-a") < execution.index("subtask-b")

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    @patch("src.gemmacode.run.overnight.SubtaskRunner")
    def test_summary_generation(
        self,
        mock_runner_class,
        mock_orchestrator_class,
        mock_get_model,
        mock_get_config,
        mock_build_repo_map,
    ):
        """summary.json should have all subtasks with passed status."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo"
        mock_get_config.return_value = {}
        mock_get_model.return_value = MagicMock()

        mock_orchestrator_class.side_effect = MockOrchestratorAgent
        mock_runner_class.side_effect = MockSubtaskRunner

        # Run CLI
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                [
                    "--task",
                    "Test",
                    "--output",
                    tmpdir,
                ],
            )

            assert result.exit_code == 0

            # Verify summary
            summary_file = Path(tmpdir) / "summary.json"
            assert summary_file.exists()

            with open(summary_file) as f:
                summary = json.load(f)

            assert summary["total_subtasks"] == 3
            assert summary["passed"] == 3
            assert summary["failed"] == 0
            assert len(summary["results"]) == 3

            # Check all results are passed
            for result_entry in summary["results"]:
                assert result_entry["status"] == "passed"

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    def test_plan_round_trip(
        self,
        mock_orchestrator_class,
        mock_get_model,
        mock_get_config,
        mock_build_repo_map,
    ):
        """Re-loading plan.json should produce identical plan."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo"
        mock_get_config.return_value = {}
        mock_get_model.return_value = MagicMock()

        mock_orchestrator_class.side_effect = MockOrchestratorAgent

        # Run CLI with dry-run
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                [
                    "--task",
                    "Test",
                    "--output",
                    tmpdir,
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0

            # Load saved plan
            plan_file = Path(tmpdir) / "plan.json"
            assert plan_file.exists()

            original_plan = load_plan(plan_file)

            # Verify plan structure
            assert len(original_plan.subtasks) == 3
            assert original_plan.subtasks[0].id == "subtask-a"
            assert original_plan.subtasks[1].id == "subtask-b"
            assert original_plan.subtasks[2].id == "subtask-c"

            # Re-serialize and verify equivalence
            with open(plan_file) as f:
                original_data = json.load(f)

            reloaded_plan = load_plan(plan_file)
            reloaded_data = json.loads(reloaded_plan.model_dump_json())

            assert original_data == reloaded_data

    @patch("src.gemmacode.run.overnight.build_repo_map")
    @patch("src.gemmacode.run.overnight.get_config_from_spec")
    @patch("src.gemmacode.run.overnight.get_model")
    @patch("src.gemmacode.run.overnight.OrchestratorAgent")
    @patch("src.gemmacode.run.overnight.SubtaskRunner")
    def test_partial_failure_nonblocking(
        self,
        mock_runner_class,
        mock_orchestrator_class,
        mock_get_model,
        mock_get_config,
        mock_build_repo_map,
    ):
        """Pipeline should continue if one subtask fails (independent subtasks)."""
        # Setup mocks
        mock_build_repo_map.return_value = "repo"
        mock_get_config.return_value = {}
        mock_get_model.return_value = MagicMock()

        mock_orchestrator_class.side_effect = MockOrchestratorAgent

        # Make B fail but A and C pass
        def run_with_failure(spec):
            MockSubtaskRunner.execution_order.append(spec.id)
            if spec.id == "subtask-b":
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

        mock_runner_class.return_value.run = run_with_failure

        # Run CLI
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                [
                    "--task",
                    "Test",
                    "--output",
                    tmpdir,
                ],
            )

            assert result.exit_code == 0

            # Verify all subtasks were attempted
            execution = MockSubtaskRunner.execution_order
            assert len(execution) == 3
            assert "subtask-a" in execution
            assert "subtask-b" in execution
            assert "subtask-c" in execution

            # Verify summary shows failure
            summary_file = Path(tmpdir) / "summary.json"
            with open(summary_file) as f:
                summary = json.load(f)

            assert summary["total_subtasks"] == 3
            assert summary["passed"] == 2
            assert summary["failed"] == 1
