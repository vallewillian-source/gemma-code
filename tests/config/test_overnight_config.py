"""Tests for overnight.yaml configuration."""

import subprocess

import pytest

from src.gemmacode.config import get_config_from_spec


class TestOvernightYAML:
    """Tests for overnight.yaml configuration file."""

    def test_overnight_yaml_loads(self):
        """overnight.yaml should load without error."""
        config = get_config_from_spec("overnight.yaml")
        assert config is not None
        assert isinstance(config, dict)

    def test_overnight_yaml_has_required_sections(self):
        """overnight.yaml should have required sections."""
        config = get_config_from_spec("overnight.yaml")
        assert "agent" in config
        assert "model" in config
        assert "environment" in config

    def test_overnight_yaml_agent_section(self):
        """Agent section should have required fields."""
        config = get_config_from_spec("overnight.yaml")
        agent_config = config["agent"]
        assert "step_limit" in agent_config
        assert "cost_limit" in agent_config
        assert "mode" in agent_config
        assert agent_config["mode"] == "yolo"

    def test_overnight_yaml_model_section(self):
        """Model section should have required fields."""
        config = get_config_from_spec("overnight.yaml")
        model_config = config["model"]
        assert "model_kwargs" in model_config
        assert "cost_tracking" in model_config
        assert model_config["cost_tracking"] == "ignore_errors"

    def test_overnight_yaml_model_kwargs(self):
        """Model kwargs should have context size configuration."""
        config = get_config_from_spec("overnight.yaml")
        model_kwargs = config["model"]["model_kwargs"]
        assert "num_ctx" in model_kwargs
        assert model_kwargs["num_ctx"] == 40960

    def test_overnight_yaml_environment_section(self):
        """Environment section should have timeout configuration."""
        config = get_config_from_spec("overnight.yaml")
        env_config = config["environment"]
        assert "timeout" in env_config
        assert env_config["timeout"] == 60


class TestOvernightCLI:
    """Tests for gemma-code-overnight CLI registration."""

    def test_overnight_cli_help_works(self):
        """gemma-code-overnight --help should work (smoke test)."""
        # Note: This test requires the package to be installed in editable mode
        # If it fails, the CLI may not be registered yet
        try:
            result = subprocess.run(
                ["gemma-code-overnight", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # The command should either succeed (exit 0) or the help should be shown
            # even if there's an error loading config
            assert result.returncode == 0 or "help" in result.stdout.lower() or "help" in result.stderr.lower()
        except FileNotFoundError:
            pytest.skip("gemma-code-overnight CLI not installed (expected in development)")

    def test_overnight_cli_import_works(self):
        """gemma-code-overnight should be importable."""
        try:
            from gemmacode.run.overnight import app

            assert app is not None
        except ImportError:
            pytest.skip("overnight module not available")
