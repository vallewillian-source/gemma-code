"""Tests for topological sorting of SubtaskSpec."""

import pytest

from src.gemmacode.orchestrator import (
    CyclicDependencyError,
    SubtaskSpec,
    TestCriterion,
    topological_sort,
)


@pytest.fixture
def no_deps_subtasks():
    """Create subtasks with no dependencies."""
    return [
        SubtaskSpec(
            id="task-1",
            title="Task 1",
            description="First task",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
        SubtaskSpec(
            id="task-2",
            title="Task 2",
            description="Second task",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
        SubtaskSpec(
            id="task-3",
            title="Task 3",
            description="Third task",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
    ]


@pytest.fixture
def chain_subtasks():
    """Create subtasks with chain dependencies: A <- B <- C."""
    return [
        SubtaskSpec(
            id="task-a",
            title="Task A",
            description="Independent task",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
        SubtaskSpec(
            id="task-b",
            title="Task B",
            description="Depends on A",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["task-a"],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
        SubtaskSpec(
            id="task-c",
            title="Task C",
            description="Depends on B",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["task-b"],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
    ]


@pytest.fixture
def diamond_subtasks():
    """Create subtasks with diamond dependencies: A <- B, A <- C, B <- D, C <- D."""
    return [
        SubtaskSpec(
            id="task-a",
            title="Task A",
            description="Independent",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
        SubtaskSpec(
            id="task-b",
            title="Task B",
            description="Depends on A",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["task-a"],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
        SubtaskSpec(
            id="task-c",
            title="Task C",
            description="Depends on A",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["task-a"],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
        SubtaskSpec(
            id="task-d",
            title="Task D",
            description="Depends on B and C",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["task-b", "task-c"],
            acceptance_tests=[],
            estimated_complexity="low",
        ),
    ]


class TestTopologicalSortBasic:
    """Basic topological sort tests."""

    def test_no_dependencies_preserves_order(self, no_deps_subtasks):
        """List without dependencies should return same order."""
        result = topological_sort(no_deps_subtasks)

        assert len(result) == 3
        assert result[0].id == "task-1"
        assert result[1].id == "task-2"
        assert result[2].id == "task-3"

    def test_empty_list_returns_empty(self):
        """Empty list should return empty list."""
        result = topological_sort([])
        assert result == []

    def test_single_subtask(self):
        """Single subtask should be returned as-is."""
        subtask = SubtaskSpec(
            id="single",
            title="Single",
            description="One task",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=[],
            acceptance_tests=[],
            estimated_complexity="low",
        )
        result = topological_sort([subtask])
        assert len(result) == 1
        assert result[0].id == "single"


class TestTopologicalSortChain:
    """Tests for chain dependencies."""

    def test_simple_chain(self, chain_subtasks):
        """A <- B <- C should return [A, B, C]."""
        # Shuffle order to test sorting
        shuffled = [chain_subtasks[2], chain_subtasks[0], chain_subtasks[1]]

        result = topological_sort(shuffled)

        assert len(result) == 3
        assert result[0].id == "task-a"
        assert result[1].id == "task-b"
        assert result[2].id == "task-c"

    def test_chain_with_independent(self):
        """Chain plus independent task."""
        subtasks = [
            SubtaskSpec(
                id="independent",
                title="Independent",
                description="No deps",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=[],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="a",
                title="A",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=[],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="b",
                title="B",
                description="Depends on A",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["a"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
        ]

        result = topological_sort(subtasks)

        # Independent and A should come before B
        ids = [s.id for s in result]
        assert ids.index("a") < ids.index("b")
        assert ids.index("independent") < ids.index("b")


class TestTopologicalSortDiamond:
    """Tests for diamond-shaped dependencies."""

    def test_diamond_dependency(self, diamond_subtasks):
        """Diamond shape: A <- [B, C] <- D."""
        result = topological_sort(diamond_subtasks)
        ids = [s.id for s in result]

        # A must come before B and C
        assert ids.index("task-a") < ids.index("task-b")
        assert ids.index("task-a") < ids.index("task-c")

        # B and C must come before D
        assert ids.index("task-b") < ids.index("task-d")
        assert ids.index("task-c") < ids.index("task-d")


class TestTopologicalSortCycles:
    """Tests for cycle detection."""

    def test_self_cycle(self):
        """A depends on itself should raise CyclicDependencyError."""
        subtask = SubtaskSpec(
            id="cyclic",
            title="Cyclic",
            description="Self-dependent",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["cyclic"],
            acceptance_tests=[],
            estimated_complexity="low",
        )

        with pytest.raises(CyclicDependencyError):
            topological_sort([subtask])

    def test_simple_cycle(self):
        """A -> B -> A should raise CyclicDependencyError."""
        subtasks = [
            SubtaskSpec(
                id="a",
                title="A",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["b"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="b",
                title="B",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["a"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
        ]

        with pytest.raises(CyclicDependencyError):
            topological_sort(subtasks)

    def test_three_node_cycle(self):
        """A -> B -> C -> A should raise CyclicDependencyError."""
        subtasks = [
            SubtaskSpec(
                id="a",
                title="A",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["c"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="b",
                title="B",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["a"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="c",
                title="C",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["b"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
        ]

        with pytest.raises(CyclicDependencyError):
            topological_sort(subtasks)


class TestTopologicalSortValidation:
    """Tests for error validation."""

    def test_nonexistent_dependency(self):
        """Dependency on non-existent id should raise ValueError."""
        subtask = SubtaskSpec(
            id="task-1",
            title="Task 1",
            description="",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["nonexistent"],
            acceptance_tests=[],
            estimated_complexity="low",
        )

        with pytest.raises(ValueError, match="nonexistent"):
            topological_sort([subtask])

    def test_multiple_nonexistent_dependencies(self):
        """Should catch nonexistent dependencies."""
        subtask = SubtaskSpec(
            id="task-1",
            title="Task 1",
            description="",
            files_to_read=[],
            files_to_write=[],
            context="",
            dependencies=["bad-dep-1", "bad-dep-2"],
            acceptance_tests=[],
            estimated_complexity="low",
        )

        with pytest.raises(ValueError):
            topological_sort([subtask])


class TestTopologicalSortComplex:
    """Complex scenarios with many subtasks."""

    def test_10_task_chain(self):
        """10 tasks in a chain should be sorted correctly."""
        subtasks = []
        for i in range(10):
            task_id = f"task-{i}"
            deps = [f"task-{i-1}"] if i > 0 else []
            subtasks.append(
                SubtaskSpec(
                    id=task_id,
                    title=f"Task {i}",
                    description="",
                    files_to_read=[],
                    files_to_write=[],
                    context="",
                    dependencies=deps,
                    acceptance_tests=[],
                    estimated_complexity="low",
                )
            )

        # Reverse the list to test reordering
        shuffled = list(reversed(subtasks))
        result = topological_sort(shuffled)

        # Verify order is correct
        result_ids = [s.id for s in result]
        expected = [f"task-{i}" for i in range(10)]
        assert result_ids == expected

    def test_complex_mixed_dependencies(self):
        """Complex graph with multiple independent branches and merges."""
        subtasks = [
            # Branch 1: A <- B
            SubtaskSpec(
                id="a",
                title="A",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=[],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="b",
                title="B",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["a"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            # Branch 2: C <- D
            SubtaskSpec(
                id="c",
                title="C",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=[],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="d",
                title="D",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["c"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            # Merge: E depends on B and D
            SubtaskSpec(
                id="e",
                title="E",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=["b", "d"],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
        ]

        result = topological_sort(subtasks)
        ids = [s.id for s in result]

        # Verify constraints
        assert ids.index("a") < ids.index("b")
        assert ids.index("c") < ids.index("d")
        assert ids.index("b") < ids.index("e")
        assert ids.index("d") < ids.index("e")


class TestTopologicalSortOrdering:
    """Tests for ordering guarantees within sorted result."""

    def test_preserves_relative_order_for_independent_tasks(self):
        """Independent tasks should maintain relative order from input."""
        subtasks = [
            SubtaskSpec(
                id="task-1",
                title="Task 1",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=[],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="task-2",
                title="Task 2",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=[],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
            SubtaskSpec(
                id="task-3",
                title="Task 3",
                description="",
                files_to_read=[],
                files_to_write=[],
                context="",
                dependencies=[],
                acceptance_tests=[],
                estimated_complexity="low",
            ),
        ]

        result = topological_sort(subtasks)
        result_ids = [s.id for s in result]

        # Order should be preserved for independent tasks
        assert result_ids == ["task-1", "task-2", "task-3"]
