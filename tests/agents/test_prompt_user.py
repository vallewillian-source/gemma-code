from prompt_toolkit.keys import Keys

from gemmacode.agents.utils import prompt_user


def test_multiline_prompt_ui_and_key_bindings():
    toolbar = prompt_user.MULTILINE_PROMPT_TOOLBAR_TEXT
    assert "Enter" in toolbar
    assert "Shift+Enter" in toolbar
    assert "Ctrl+J" in toolbar
    assert "Esc, then Enter" not in toolbar

    binding_keys = {binding.keys for binding in prompt_user.MULTILINE_PROMPT_KEY_BINDINGS.bindings}
    assert (Keys.ControlM,) in binding_keys
    assert (Keys.ControlJ,) in binding_keys
