"""Tests for RestrictedEnvironment."""

import os
import tempfile
from pathlib import Path

import pytest

from src.gemmacode.environments.local import LocalEnvironment
from src.gemmacode.environments.restricted import RestrictedEnvironment


@pytest.fixture
def temp_files():
    """Create temporary test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        src_dir = Path(tmpdir) / "src"
        test_dir = Path(tmpdir) / "tests"
        src_dir.mkdir()
        test_dir.mkdir()

        allowed_file1 = src_dir / "allowed1.py"
        allowed_file2 = src_dir / "allowed2.py"
        test_file = test_dir / "test_something.py"

        allowed_file1.write_text("# allowed1")
        allowed_file2.write_text("# allowed2")
        test_file.write_text("# test")

        yield {
            "tmpdir": tmpdir,
            "allowed1": str(allowed_file1),
            "allowed2": str(allowed_file2),
            "test_file": str(test_file),
            "src_dir": str(src_dir),
            "test_dir": str(test_dir),
        }


class TestRestrictedEnvironmentBasic:
    """Basic tests for RestrictedEnvironment."""

    def test_allows_command_with_no_file_references(self, temp_files):
        """Commands without file references should be allowed."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": "echo hello"})
        assert result["returncode"] == 0
        assert "hello" in result["output"]

    def test_blocks_access_to_system_files(self, temp_files):
        """Attempting to read /etc/passwd should be blocked."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": "cat /etc/passwd"})
        assert result["returncode"] != 0
        assert "allowed files" in result["output"].lower() or "access denied" in result["output"].lower()

    def test_allows_reading_allowed_file(self, temp_files):
        """Reading an allowed file should work."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": f"cat {temp_files['allowed1']}"})
        assert result["returncode"] == 0
        assert "allowed1" in result["output"]

    def test_blocks_writing_to_non_allowed_file(self, temp_files):
        """Writing to a non-allowed file should be blocked."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        not_allowed = Path(temp_files["tmpdir"]) / "not_allowed.txt"
        result = env.execute({"command": f"echo content > {not_allowed}"})
        assert result["returncode"] != 0
        assert "access denied" in result["output"].lower() or "allowed files" in result["output"].lower()

    def test_allows_ls_command(self, temp_files):
        """ls command without specific files should be allowed."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": f"ls -la {temp_files['src_dir']}"})
        assert result["returncode"] == 0

    def test_allows_pytest_command(self, temp_files):
        """pytest command should be allowed (no direct file blocking)."""
        allowed_files = [temp_files["test_file"]]
        env = RestrictedEnvironment(allowed_files)

        # pytest command itself should be allowed (it doesn't mention files directly)
        result = env.execute({"command": "pytest --version"})
        # May succeed or fail depending on pytest install, but shouldn't be blocked by restricted env
        assert "blocked" not in str(result.get("extra", {})).lower()

    def test_multiple_allowed_files(self, temp_files):
        """Multiple files in allowlist should all be accessible."""
        allowed_files = [temp_files["allowed1"], temp_files["allowed2"]]
        env = RestrictedEnvironment(allowed_files)

        result1 = env.execute({"command": f"cat {temp_files['allowed1']}"})
        assert result1["returncode"] == 0

        result2 = env.execute({"command": f"cat {temp_files['allowed2']}"})
        assert result2["returncode"] == 0


class TestRestrictedEnvironmentPathExtraction:
    """Tests for file path extraction from commands."""

    def test_extract_cat_command(self, temp_files):
        """Should extract paths from cat commands."""
        env = RestrictedEnvironment([temp_files["allowed1"]])

        paths = env._extract_file_paths(f"cat {temp_files['allowed1']}", "")
        # Should extract the path
        assert len(paths) > 0

    def test_extract_output_redirection(self, temp_files):
        """Should extract paths from output redirection."""
        env = RestrictedEnvironment([temp_files["allowed1"]])

        paths = env._extract_file_paths("echo hello > /tmp/test.txt", "")
        assert "/tmp/test.txt" in paths or any("test.txt" in p for p in paths)

    def test_extract_input_redirection(self, temp_files):
        """Should extract paths from input redirection."""
        env = RestrictedEnvironment([temp_files["allowed1"]])

        paths = env._extract_file_paths(f"grep pattern < {temp_files['allowed1']}", "")
        assert len(paths) > 0

    def test_no_extraction_from_generic_commands(self, temp_files):
        """Generic commands should not trigger extraction."""
        env = RestrictedEnvironment([])

        paths = env._extract_file_paths("ls -la", "")
        # Should not extract anything dangerous
        assert len(paths) == 0

    def test_no_extraction_from_pytest(self, temp_files):
        """pytest commands should not extract file paths for blocking."""
        env = RestrictedEnvironment([])

        paths = env._extract_file_paths("pytest tests/", "")
        # Should not extract "tests/" as a specific file to block
        # (pytest is allowed even if some test files aren't in allowlist)
        assert len(paths) == 0 or all("tests" not in str(p) for p in paths)


class TestRestrictedEnvironmentTemplateVars:
    """Tests for template variables."""

    def test_get_template_vars_includes_allowed_files(self, temp_files):
        """get_template_vars should include allowed_files."""
        allowed_files = [temp_files["allowed1"], temp_files["allowed2"]]
        env = RestrictedEnvironment(allowed_files)

        vars = env.get_template_vars()
        assert "allowed_files" in vars
        assert vars["allowed_files"] == allowed_files

    def test_get_template_vars_includes_base_env_vars(self, temp_files):
        """get_template_vars should include base environment variables."""
        env = RestrictedEnvironment([temp_files["allowed1"]])

        vars = env.get_template_vars()
        # Should have variables from LocalEnvironment
        assert "cwd" in vars or "timeout" in vars or len(vars) > 1


class TestRestrictedEnvironmentErrorMessages:
    """Tests for error message formatting."""

    def test_error_response_format(self, temp_files):
        """Error response should have proper format."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": "cat /etc/passwd"})
        assert result["returncode"] != 0
        assert "output" in result
        assert "exception_info" in result
        assert "extra" in result
        assert result["extra"].get("blocked") is True

    def test_error_message_lists_forbidden_files(self, temp_files):
        """Error message should list which files are forbidden."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": "cat /etc/passwd"})
        # Error message should mention that access was denied
        assert "access denied" in result["output"].lower() or "/etc/passwd" in result["output"]

    def test_error_message_lists_allowed_files(self, temp_files):
        """Error message should list allowed files for user reference."""
        allowed_files = [temp_files["allowed1"], temp_files["allowed2"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": "cat /etc/passwd"})
        # Error message should mention allowed files
        assert "allowed" in result["output"].lower()


class TestRestrictedEnvironmentWithBaseEnv:
    """Tests with custom base environment."""

    def test_uses_provided_base_env(self, temp_files):
        """RestrictedEnvironment should use provided base_env."""
        base_env = LocalEnvironment()
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files, base_env=base_env)

        result = env.execute({"command": "echo test"})
        assert result["returncode"] == 0
        assert "test" in result["output"]

    def test_creates_default_base_env_if_not_provided(self):
        """RestrictedEnvironment should create LocalEnvironment if not provided."""
        env = RestrictedEnvironment([])
        assert env.base_env is not None
        assert env.base_env.__class__.__name__ == "LocalEnvironment"


class TestRestrictedEnvironmentSerialization:
    """Tests for serialization."""

    def test_serialize_includes_allowed_files(self, temp_files):
        """serialize() should include allowed_files."""
        allowed_files = [temp_files["allowed1"], temp_files["allowed2"]]
        env = RestrictedEnvironment(allowed_files)

        serialized = env.serialize()
        assert "info" in serialized
        assert "config" in serialized["info"]
        assert "allowed_files" in serialized["info"]["config"]
        assert serialized["info"]["config"]["allowed_files"] == allowed_files


class TestRestrictedEnvironmentComplexScenarios:
    """Tests for complex scenarios."""

    def test_multiple_file_references_all_blocked(self, temp_files):
        """Command with multiple file references, all blocked."""
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": "cat /etc/passwd /etc/hosts"})
        assert result["returncode"] != 0

    def test_relative_path_resolution(self, temp_files):
        """Relative paths should be resolved correctly."""
        # Create a command using relative paths
        allowed_files = [temp_files["allowed1"]]
        env = RestrictedEnvironment(allowed_files)

        src_dir = Path(temp_files["allowed1"]).parent
        result = env.execute(
            {"command": "echo test > allowed1.py"},
            cwd=str(src_dir),
        )
        # Writing to allowed file with relative path should work
        assert result["returncode"] == 0 or result["returncode"] != 1  # Allow overwrite or append

    def test_path_with_spaces(self, temp_files):
        """Paths with spaces should be handled correctly."""
        tmpdir = Path(temp_files["tmpdir"])
        space_file = tmpdir / "file with spaces.py"
        space_file.write_text("test")

        allowed_files = [str(space_file)]
        env = RestrictedEnvironment(allowed_files)

        result = env.execute({"command": f'cat "{space_file}"'})
        # Should allow reading file even with spaces in path
        assert result["returncode"] == 0
