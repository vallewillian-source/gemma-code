from unittest.mock import MagicMock, patch

import pytest

from gemmacode.exceptions import FormatError
from gemmacode.models.litellm_model import LitellmModel, LitellmModelConfig
from gemmacode.models.utils.actions_toolcall import BASH_TOOL


class TestLitellmModelConfig:
    def test_default_format_error_template(self):
        assert LitellmModelConfig(model_name="test").format_error_template == "{{ error }}"


def _mock_litellm_response(tool_calls, function_call=None):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.tool_calls = tool_calls
    mock_response.choices[0].message.function_call = function_call
    dumped_message = {"role": "assistant", "content": None}
    if function_call is not None:
        dumped_message["function_call"] = function_call
    if tool_calls is not None:
        dumped_message["tool_calls"] = tool_calls
    mock_response.choices[0].message.model_dump.return_value = dumped_message
    mock_response.model_dump.return_value = {}
    return mock_response


class TestLitellmModel:
    @patch("gemmacode.models.litellm_model.litellm.completion")
    @patch("gemmacode.models.litellm_model.litellm.cost_calculator.completion_cost")
    def test_query_includes_bash_tool(self, mock_cost, mock_completion):
        tool_call = {"id": "call_1", "function": {"name": "bash", "arguments": '{"command": "echo test"}'}}
        mock_completion.return_value = _mock_litellm_response([tool_call])
        mock_cost.return_value = 0.001

        model = LitellmModel(model_name="gpt-4")
        model.query([{"role": "user", "content": "test"}])

        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs["tools"] == [BASH_TOOL]

    @patch("gemmacode.models.litellm_model.litellm.completion")
    @patch("gemmacode.models.litellm_model.litellm.cost_calculator.completion_cost")
    def test_parse_actions_valid_tool_call(self, mock_cost, mock_completion):
        tool_call = {"id": "call_abc", "function": {"name": "bash", "arguments": '{"command": "ls -la"}'}}
        mock_completion.return_value = _mock_litellm_response([tool_call])
        mock_cost.return_value = 0.001

        model = LitellmModel(model_name="gpt-4")
        result = model.query([{"role": "user", "content": "list files"}])
        assert result["extra"]["actions"] == [{"command": "ls -la", "tool_call_id": "call_abc"}]

    @patch("gemmacode.models.litellm_model.litellm.completion")
    @patch("gemmacode.models.litellm_model.litellm.cost_calculator.completion_cost")
    def test_parse_actions_no_tool_calls_raises(self, mock_cost, mock_completion):
        mock_completion.return_value = _mock_litellm_response(None)
        mock_cost.return_value = 0.001

        model = LitellmModel(model_name="gpt-4")
        with pytest.raises(FormatError):
            model.query([{"role": "user", "content": "test"}])

    @patch("gemmacode.models.litellm_model.litellm.completion")
    @patch("gemmacode.models.litellm_model.litellm.cost_calculator.completion_cost")
    def test_parse_actions_function_call_fallback(self, mock_cost, mock_completion):
        mock_completion.return_value = _mock_litellm_response(
            None, {"name": "bash", "arguments": '{"command": "ls -la"}', "id": "call_fc"}
        )
        mock_cost.return_value = 0.001

        model = LitellmModel(model_name="gpt-4")
        result = model.query([{"role": "user", "content": "list files"}])
        assert result["extra"]["actions"] == [{"command": "ls -la", "tool_call_id": "call_fc"}]

    @patch("gemmacode.models.utils.verbose.console.print_json")
    @patch("gemmacode.models.utils.verbose.console.print")
    @patch("gemmacode.models.litellm_model.litellm.completion")
    @patch("gemmacode.models.litellm_model.litellm.cost_calculator.completion_cost")
    def test_verbose_mode_emits_raw_response_diagnostics(self, mock_cost, mock_completion, mock_print, mock_print_json):
        mock_completion.return_value = _mock_litellm_response(None)
        mock_cost.return_value = 0.001

        model = LitellmModel(model_name="gpt-4", verbose=True)
        with pytest.raises(FormatError):
            model.query([{"role": "user", "content": "test"}])

        assert mock_print_json.call_count >= 2
        first_payload = mock_print_json.call_args_list[0].args[0]
        second_payload = mock_print_json.call_args_list[-1].args[0]
        assert "likely_pattern" in first_payload
        assert "plain_text" in first_payload or "empty_content" in first_payload
        assert "parse_error" in second_payload
        assert "No tool calls found" in second_payload

    @patch("gemmacode.models.utils.verbose.console.print_json")
    @patch("gemmacode.models.litellm_model.litellm.completion")
    @patch("gemmacode.models.litellm_model.litellm.cost_calculator.completion_cost")
    def test_verbose_mode_detects_function_call_fallback(self, mock_cost, mock_completion, mock_print_json):
        mock_completion.return_value = _mock_litellm_response(
            None, {"name": "bash", "arguments": '{"command": "ls"}', "id": "call_verbose"}
        )
        mock_cost.return_value = 0.001

        model = LitellmModel(model_name="gpt-4", verbose=True)
        result = model.query([{"role": "user", "content": "list files"}])

        assert result["extra"]["actions"] == [{"command": "ls", "tool_call_id": "call_verbose"}]
        payload = mock_print_json.call_args_list[0].args[0]
        assert '"tool_calls_source": "function_call"' in payload
        assert '"likely_pattern": "function_call_legacy"' in payload

    def test_format_observation_messages(self):
        model = LitellmModel(model_name="gpt-4", observation_template="{{ output.output }}")
        message = {"extra": {"actions": [{"command": "echo test", "tool_call_id": "call_1"}]}}
        outputs = [{"output": "test output", "returncode": 0}]
        result = model.format_observation_messages(message, outputs)
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "call_1"
        assert result[0]["content"] == "test output"

    def test_format_observation_messages_no_actions(self):
        model = LitellmModel(model_name="gpt-4")
        result = model.format_observation_messages({"extra": {}}, [])
        assert result == []
