"""Tests for heuristics YAML files."""

from pathlib import Path

import pytest
import yaml


HEURISTICS_DIR = Path(__file__).parent.parent.parent / "src/gemmacode/orchestrator/heuristics"


@pytest.fixture
def heuristics_files():
    """Get all heuristics YAML files."""
    return sorted(HEURISTICS_DIR.glob("*.yaml"))


@pytest.fixture(params=[
    "python_project.yaml",
    "testing_patterns.yaml",
    "file_structure.yaml",
    "gemmacode_project.yaml",
])
def heuristic_file(request):
    """Parametrize over each heuristics file."""
    return HEURISTICS_DIR / request.param


class TestHeuristicsYAMLStructure:
    """Tests for YAML file structure and validity."""

    def test_heuristics_directory_exists(self):
        """Heuristics directory should exist."""
        assert HEURISTICS_DIR.exists()
        assert HEURISTICS_DIR.is_dir()

    def test_expected_files_exist(self):
        """All expected heuristics files should exist."""
        expected_files = {
            "python_project.yaml",
            "testing_patterns.yaml",
            "file_structure.yaml",
        }
        actual_files = {f.name for f in HEURISTICS_DIR.glob("*.yaml")}
        assert expected_files.issubset(actual_files), f"Missing files: {expected_files - actual_files}"

    def test_yaml_loads_without_error(self, heuristic_file):
        """Each YAML file should load without error."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)
        assert data is not None

    def test_yaml_has_required_top_level_fields(self, heuristic_file):
        """Each YAML must have: name, description, rules."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)

        assert "name" in data, f"{heuristic_file.name} missing 'name' field"
        assert "description" in data, f"{heuristic_file.name} missing 'description' field"
        assert "rules" in data, f"{heuristic_file.name} missing 'rules' field"

    def test_name_is_string(self, heuristic_file):
        """Name field must be a string."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)
        assert isinstance(data["name"], str), f"{heuristic_file.name} 'name' must be string"
        assert len(data["name"]) > 0, f"{heuristic_file.name} 'name' cannot be empty"

    def test_description_is_string(self, heuristic_file):
        """Description field must be a string."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)
        assert isinstance(data["description"], str), f"{heuristic_file.name} 'description' must be string"
        assert len(data["description"]) > 0, f"{heuristic_file.name} 'description' cannot be empty"

    def test_rules_is_list(self, heuristic_file):
        """Rules field must be a list."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)
        assert isinstance(data["rules"], list), f"{heuristic_file.name} 'rules' must be list"
        assert len(data["rules"]) > 0, f"{heuristic_file.name} must have at least one rule"

    def test_each_rule_has_required_fields(self, heuristic_file):
        """Each rule must have: id, description."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)

        for idx, rule in enumerate(data["rules"]):
            assert "id" in rule, f"{heuristic_file.name} rule[{idx}] missing 'id'"
            assert "description" in rule, f"{heuristic_file.name} rule[{idx}] missing 'description'"

    def test_rule_id_is_valid(self, heuristic_file):
        """Each rule ID must be non-empty string (slug format preferred)."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)

        for idx, rule in enumerate(data["rules"]):
            assert isinstance(rule["id"], str), f"{heuristic_file.name} rule[{idx}].id must be string"
            assert len(rule["id"]) > 0, f"{heuristic_file.name} rule[{idx}].id cannot be empty"
            # Check slug format: lowercase, hyphens, no spaces
            assert rule["id"].islower() or "-" in rule["id"] or "_" in rule["id"], \
                f"{heuristic_file.name} rule[{idx}].id '{rule['id']}' should be lowercase slug"

    def test_rule_description_is_valid(self, heuristic_file):
        """Each rule description must be non-empty string."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)

        for idx, rule in enumerate(data["rules"]):
            assert isinstance(rule["description"], str), \
                f"{heuristic_file.name} rule[{idx}].description must be string"
            assert len(rule["description"]) > 0, \
                f"{heuristic_file.name} rule[{idx}].description cannot be empty"
            assert len(rule["description"]) >= 20, \
                f"{heuristic_file.name} rule[{idx}].description too short (must be ≥20 chars)"

    def test_no_duplicate_ids_within_file(self, heuristic_file):
        """No duplicate IDs within the same file."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)

        ids = [rule["id"] for rule in data["rules"]]
        duplicates = [rule_id for rule_id in ids if ids.count(rule_id) > 1]
        assert not duplicates, f"{heuristic_file.name} has duplicate IDs: {duplicates}"

    def test_example_field_is_optional_string(self, heuristic_file):
        """If example field exists, it must be a string."""
        with open(heuristic_file) as f:
            data = yaml.safe_load(f)

        for idx, rule in enumerate(data["rules"]):
            if "example" in rule:
                assert isinstance(rule["example"], str), \
                    f"{heuristic_file.name} rule[{idx}].example must be string if present"


class TestPythonProjectHeuristics:
    """Specific tests for python_project.yaml."""

    def test_has_minimum_rules(self):
        """python_project.yaml must have at least 5 rules."""
        with open(HEURISTICS_DIR / "python_project.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data["rules"]) >= 5

    def test_covers_expected_topics(self):
        """Should cover testing, fixtures, imports, mocking, structure."""
        with open(HEURISTICS_DIR / "python_project.yaml") as f:
            data = yaml.safe_load(f)

        rule_ids = {rule["id"] for rule in data["rules"]}
        expected_topics = {
            "test-location",      # testing structure
            "fixture-reuse",      # fixture patterns
            "no-unnecessary-mocks",  # mocking practices
            "type-annotations-required",  # typing
        }
        assert expected_topics.issubset(rule_ids), \
            f"Missing expected rules: {expected_topics - rule_ids}"


class TestTestingPatternsHeuristics:
    """Specific tests for testing_patterns.yaml."""

    def test_has_minimum_rules(self):
        """testing_patterns.yaml must have at least 5 rules."""
        with open(HEURISTICS_DIR / "testing_patterns.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data["rules"]) >= 5

    def test_covers_expected_topics(self):
        """Should cover pytest, TDD, parametrize, assertions, test structure."""
        with open(HEURISTICS_DIR / "testing_patterns.yaml") as f:
            data = yaml.safe_load(f)

        rule_ids = {rule["id"] for rule in data["rules"]}
        expected_topics = {
            "acceptance-via-pytest",
            "test-before-implement",
            "parametrize-edge-cases",
            "assert-inline",
        }
        assert expected_topics.issubset(rule_ids), \
            f"Missing expected rules: {expected_topics - rule_ids}"


class TestFileStructureHeuristics:
    """Specific tests for file_structure.yaml."""

    def test_has_minimum_rules(self):
        """file_structure.yaml must have at least 4 rules."""
        with open(HEURISTICS_DIR / "file_structure.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data["rules"]) >= 4

    def test_covers_expected_topics(self):
        """Should cover single responsibility, no god modules, imports, etc."""
        with open(HEURISTICS_DIR / "file_structure.yaml") as f:
            data = yaml.safe_load(f)

        rule_ids = {rule["id"] for rule in data["rules"]}
        expected_topics = {
            "single-responsibility",
            "no-god-modules",
            "explicit-public-api",
        }
        assert expected_topics.issubset(rule_ids), \
            f"Missing expected rules: {expected_topics - rule_ids}"


class TestGemmacodeProjectHeuristics:
    """Specific tests for gemmacode_project.yaml (dogfooding heuristics)."""

    def test_file_exists(self):
        """gemmacode_project.yaml should exist."""
        yaml_file = HEURISTICS_DIR / "gemmacode_project.yaml"
        assert yaml_file.exists(), "gemmacode_project.yaml is missing"

    def test_has_minimum_rules(self):
        """gemmacode_project.yaml must have at least 15 rules (rich project)."""
        with open(HEURISTICS_DIR / "gemmacode_project.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data["rules"]) >= 15, "Should have comprehensive dogfooding rules"

    def test_covers_expected_architectural_topics(self):
        """Should cover protocol-based design, minimal core, subprocess isolation, etc."""
        with open(HEURISTICS_DIR / "gemmacode_project.yaml") as f:
            data = yaml.safe_load(f)

        rule_ids = {rule["id"] for rule in data["rules"]}
        expected_topics = {
            "protocol-based-design",
            "minimal-core-philosophy",
            "no-stateful-shell",
            "linear-history-principle",
        }
        assert expected_topics.issubset(rule_ids), \
            f"Missing architectural rules: {expected_topics - rule_ids}"

    def test_covers_expected_testing_topics(self):
        """Should cover pytest patterns, integration tests, no mocking internals."""
        with open(HEURISTICS_DIR / "gemmacode_project.yaml") as f:
            data = yaml.safe_load(f)

        rule_ids = {rule["id"] for rule in data["rules"]}
        expected_topics = {
            "pytest-parametrize-over-loops",
            "no-mocking-internal-code",
            "integration-tests-preferred",
        }
        assert expected_topics.issubset(rule_ids), \
            f"Missing testing rules: {expected_topics - rule_ids}"

    def test_covers_expected_development_topics(self):
        """Should cover config patterns, development tools, global settings."""
        with open(HEURISTICS_DIR / "gemmacode_project.yaml") as f:
            data = yaml.safe_load(f)

        rule_ids = {rule["id"] for rule in data["rules"]}
        expected_topics = {
            "config-yaml-composability",
            "ruff-config-from-pyproject",
            "global-config-dir-pattern",
        }
        assert expected_topics.issubset(rule_ids), \
            f"Missing development rules: {expected_topics - rule_ids}"

    def test_covers_implementation_topics(self):
        """Should cover specific implementation patterns for this codebase."""
        with open(HEURISTICS_DIR / "gemmacode_project.yaml") as f:
            data = yaml.safe_load(f)

        rule_ids = {rule["id"] for rule in data["rules"]}
        expected_topics = {
            "pydantic-v2-strict-mode",
            "pathlib-everywhere",
            "rich-console-for-output",
        }
        assert expected_topics.issubset(rule_ids), \
            f"Missing implementation rules: {expected_topics - rule_ids}"


class TestCrossFileConsistency:
    """Tests checking consistency across all heuristics files."""

    def test_all_files_have_same_structure(self, heuristics_files):
        """All heuristics files should follow the same structure."""
        loaded_files = {}
        for yaml_file in heuristics_files:
            with open(yaml_file) as f:
                loaded_files[yaml_file.name] = yaml.safe_load(f)

        for filename, data in loaded_files.items():
            assert "name" in data, f"{filename} missing 'name'"
            assert "description" in data, f"{filename} missing 'description'"
            assert "rules" in data, f"{filename} missing 'rules'"
            assert isinstance(data["rules"], list), f"{filename} 'rules' not a list"

    def test_no_ids_duplicated_across_files(self, heuristics_files):
        """No rule ID should appear in multiple files."""
        all_ids = {}

        for yaml_file in heuristics_files:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            for rule in data["rules"]:
                rule_id = rule["id"]
                if rule_id in all_ids:
                    pytest.fail(
                        f"Rule ID '{rule_id}' appears in both "
                        f"{all_ids[rule_id]} and {yaml_file.name}"
                    )
                all_ids[rule_id] = yaml_file.name

    def test_all_files_are_valid_yaml(self, heuristics_files):
        """All YAML files should be valid YAML."""
        for yaml_file in heuristics_files:
            try:
                with open(yaml_file) as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"{yaml_file.name} has invalid YAML: {e}")
