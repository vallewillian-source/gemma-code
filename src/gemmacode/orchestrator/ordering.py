"""Topological sorting for SubtaskSpec dependency ordering."""

from gemmacode.orchestrator.schema import SubtaskSpec


class CyclicDependencyError(Exception):
    """Raised when a cyclic dependency is detected."""

    pass


def topological_sort(subtasks: list[SubtaskSpec]) -> list[SubtaskSpec]:
    """Sort subtasks by dependencies using Kahn's algorithm.

    Args:
        subtasks: List of subtasks to sort.

    Returns:
        Sorted list of subtasks respecting dependencies.

    Raises:
        CyclicDependencyError: If a cyclic dependency is detected.
        ValueError: If a dependency references a non-existent subtask id.
    """
    # Build a map of id -> subtask
    subtask_map = {s.id: s for s in subtasks}

    # Validate all dependencies exist
    for subtask in subtasks:
        for dep_id in subtask.dependencies:
            if dep_id not in subtask_map:
                msg = f"Subtask '{subtask.id}' depends on nonexistent '{dep_id}'"
                raise ValueError(msg)

    # Build in-degree and adjacency list
    in_degree = {s.id: 0 for s in subtasks}
    adjacency = {s.id: [] for s in subtasks}

    for subtask in subtasks:
        for dep_id in subtask.dependencies:
            adjacency[dep_id].append(subtask.id)
            in_degree[subtask.id] += 1

    # Kahn's algorithm
    queue = [s.id for s in subtasks if in_degree[s.id] == 0]
    sorted_ids = []

    while queue:
        # Process in original order to preserve relative ordering within same level
        current_id = queue.pop(0)
        sorted_ids.append(current_id)

        for dependent_id in adjacency[current_id]:
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                queue.append(dependent_id)

    # Check for cycles
    if len(sorted_ids) != len(subtasks):
        msg = "Cyclic dependency detected in subtasks"
        raise CyclicDependencyError(msg)

    # Return sorted subtasks
    return [subtask_map[sid] for sid in sorted_ids]
