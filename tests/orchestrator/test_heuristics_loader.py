"""Tests for heuristics loader and prompt builder."""

from pathlib import Path

import pytest

from src.gemmacode.orchestrator.heuristics import (
    build_heuristics_prompt,
    load_all_heuristics,
)


HEURISTICS_DIR = Path(__file__).parent.parent.parent / "src/gemmacode/orchestrator/heuristics"


class TestLoadAllHeuristics:
    """Tests for load_all_heuristics function."""

    def test_loads_all_yaml_files(self):
        """Should load all YAML files from heuristics directory."""
        heuristics = load_all_heuristics()
        assert len(heuristics) >= 4, "Should have at least 4 heuristics files"

    def test_returns_dict_with_expected_keys(self):
        """Should return dict with file stems as keys."""
        heuristics = load_all_heuristics()
        expected_keys = {"python_project", "testing_patterns", "file_structure", "gemmacode_project"}
        assert expected_keys.issubset(heuristics.keys()), f"Missing heuristics: {expected_keys - heuristics.keys()}"

    def test_each_heuristic_has_required_fields(self):
        """Each heuristic dict should have name, description, rules."""
        heuristics = load_all_heuristics()
        for name, data in heuristics.items():
            assert "name" in data, f"{name} missing 'name'"
            assert "description" in data, f"{name} missing 'description'"
            assert "rules" in data, f"{name} missing 'rules'"

    def test_each_rule_has_required_fields(self):
        """Each rule should have id and description."""
        heuristics = load_all_heuristics()
        for heuristic_name, heuristic in heuristics.items():
            for idx, rule in enumerate(heuristic["rules"]):
                assert "id" in rule, f"{heuristic_name}[{idx}] missing 'id'"
                assert "description" in rule, f"{heuristic_name}[{idx}] missing 'description'"


class TestBuildHeuristicsPrompt:
    """Tests for build_heuristics_prompt function."""

    def test_builds_prompt_with_all_heuristics_when_none_specified(self):
        """When heuristics_applied is None, should include all heuristics."""
        prompt = build_heuristics_prompt(heuristics_applied=None)
        assert len(prompt) > 0
        # Check for content from each heuristic file (checking formatted titles)
        assert "Python Project" in prompt
        assert "Testing Patterns" in prompt
        assert "File Structure" in prompt

    def test_builds_prompt_with_specific_heuristics(self):
        """When heuristics_applied is specified, should include only those."""
        prompt = build_heuristics_prompt(heuristics_applied=["python_project"])
        assert "Python Project" in prompt
        # Should not have other heuristics
        assert "Testing Patterns" not in prompt
        assert "File Structure" not in prompt

    def test_filters_to_requested_heuristics(self):
        """Should only include specified heuristics files."""
        prompt = build_heuristics_prompt(heuristics_applied=["gemmacode_project"])
        # Check for gemmacode-specific content
        assert "Gemmacode Project" in prompt
        # Should not have other heuristics
        assert "Python Project" not in prompt
        assert "Testing Patterns" not in prompt

    def test_empty_heuristics_list_returns_empty_prompt(self):
        """With empty heuristics_applied list, should return minimal prompt."""
        prompt = build_heuristics_prompt(heuristics_applied=[])
        assert prompt == ""

    def test_invalid_heuristics_ignored(self):
        """Invalid heuristics names should be silently ignored."""
        prompt = build_heuristics_prompt(heuristics_applied=["nonexistent_file"])
        assert prompt == ""

    def test_mixed_valid_invalid_heuristics(self):
        """Should include valid heuristics and ignore invalid ones."""
        prompt = build_heuristics_prompt(heuristics_applied=["python_project", "nonexistent"])
        assert len(prompt) > 0
        assert "python_project" in prompt.lower() or "Python" in prompt

    def test_prompt_includes_markdown_formatting(self):
        """Prompt should include markdown headers (##, ###)."""
        prompt = build_heuristics_prompt(heuristics_applied=["python_project"])
        assert "##" in prompt, "Should include markdown section headers"
        assert "###" in prompt, "Should include markdown rule headers"

    def test_prompt_includes_rule_descriptions(self):
        """Prompt should include full rule descriptions."""
        prompt = build_heuristics_prompt(heuristics_applied=["python_project"])
        # Check for a known rule from python_project
        assert "test-location" in prompt

    def test_prompt_includes_examples_when_present(self):
        """Rules with examples should include them in prompt."""
        prompt = build_heuristics_prompt(heuristics_applied=["python_project"])
        # Most rules have examples, so prompt should contain "Example:" text
        assert "Example" in prompt or "example" in prompt or "✓" in prompt or "❌" in prompt

    def test_all_heuristics_prompt_is_comprehensive(self):
        """Prompt with all heuristics should contain rules from all files."""
        prompt = build_heuristics_prompt(heuristics_applied=None)
        # Count section headers (roughly proportional to number of heuristics)
        section_count = prompt.count("##")
        assert section_count >= 4, f"Should have at least 4 heuristic sections, got {section_count}"

    def test_prompt_structure_consistency(self):
        """Prompt structure should be consistent across all heuristics."""
        prompt = build_heuristics_prompt(heuristics_applied=None)
        # Each heuristic section should have multiple rule headers (using regex to count ### not ##)
        import re
        section_headers = len(re.findall(r"^## ", prompt, re.MULTILINE))
        rule_headers = len(re.findall(r"^### ", prompt, re.MULTILINE))
        assert rule_headers > section_headers, f"Should have more rule headers ({rule_headers}) than section headers ({section_headers})"

    def test_no_duplicate_content_in_prompt(self):
        """Same heuristics should not appear multiple times."""
        prompt = build_heuristics_prompt(heuristics_applied=["python_project", "python_project"])
        # Count a specific known rule ID
        count = prompt.count("test-location")
        assert count == 1, f"Rule should appear once, not {count} times"

    def test_handles_all_heuristics_files(self):
        """Should successfully load and format all heuristics files."""
        prompt = build_heuristics_prompt(heuristics_applied=None)
        heuristics = load_all_heuristics()
        # Rough check: prompt should contain at least some content from each file
        total_rules = sum(len(h["rules"]) for h in heuristics.values())
        # Each rule generates at least rule header + description
        assert len(prompt) > total_rules * 10, "Prompt should be substantial relative to rule count"


class TestHeuristicsIntegration:
    """Integration tests for heuristics loading and formatting."""

    def test_load_and_prompt_consistency(self):
        """Data loaded by load_all_heuristics should match prompt content."""
        heuristics = load_all_heuristics()
        prompt = build_heuristics_prompt(heuristics_applied=list(heuristics.keys()))
        # Every heuristic name should appear in prompt
        for name in heuristics.keys():
            # Check for the human-readable title (titlecase of name)
            human_name = name.replace("_", " ").title()
            assert human_name in prompt, f"Heuristic name '{human_name}' should appear in prompt"

    def test_prompt_with_selective_heuristics(self):
        """Selectively including heuristics should work correctly."""
        heuristics = load_all_heuristics()
        all_names = list(heuristics.keys())

        # Test with each heuristic individually
        for single_name in all_names[:2]:  # Test first 2 to keep test fast
            prompt = build_heuristics_prompt(heuristics_applied=[single_name])
            assert len(prompt) > 0, f"Prompt should not be empty for {single_name}"
            # Count rules in the heuristic
            rule_count = len(heuristics[single_name]["rules"])
            # Very rough check: prompt should have similar order of magnitude
            assert len(prompt) > rule_count * 5, f"Prompt should reflect {rule_count} rules"

    def test_multiple_heuristics_dont_duplicate(self):
        """Multiple heuristics should not have duplicate rule IDs."""
        heuristics = load_all_heuristics()
        prompt = build_heuristics_prompt(heuristics_applied=None)

        # Extract all rule IDs that appear in prompt
        all_ids = set()
        for heuristic in heuristics.values():
            for rule in heuristic["rules"]:
                rule_id = rule["id"]
                assert rule_id not in all_ids, f"Duplicate rule ID: {rule_id}"
                all_ids.add(rule_id)

    def test_prompt_matches_heuristic_specification(self):
        """Prompt content should match the heuristic YAML specification."""
        heuristics = load_all_heuristics()
        prompt = build_heuristics_prompt(heuristics_applied=["python_project"])

        # Get python_project heuristic
        py_proj = heuristics["python_project"]
        # Check that each rule ID appears in prompt
        for rule in py_proj["rules"]:
            assert rule["id"] in prompt, f"Rule ID '{rule['id']}' should appear in prompt"
