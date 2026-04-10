from prompt_toolkit.formatted_text.html import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.named_commands import accept_line
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import PromptSession

from gemmacode import global_config_dir

_history = FileHistory(global_config_dir / "interactive_history.txt")
prompt_session = PromptSession(history=_history)

MULTILINE_PROMPT_TOOLBAR_TEXT = (
    "Send message: <b fg='yellow' bg='black'>Enter</b> | "
    "New line: <b fg='yellow' bg='black'>Shift+Enter</b> "
    "(<b fg='yellow' bg='black'>Ctrl+J</b> fallback) | "
    "Navigate history: <b fg='yellow' bg='black'>Arrow Up/Down</b> | "
    "Search history: <b fg='yellow' bg='black'>Ctrl+R</b>"
)

MULTILINE_PROMPT_KEY_BINDINGS = KeyBindings()


@MULTILINE_PROMPT_KEY_BINDINGS.add("enter", eager=True)
def _accept_on_enter(event) -> None:
    accept_line(event)


@MULTILINE_PROMPT_KEY_BINDINGS.add("c-j", eager=True)
def _insert_newline(event) -> None:
    event.current_buffer.insert_text("\n")


_multiline_prompt_session = PromptSession(
    history=_history,
    multiline=True,
    key_bindings=MULTILINE_PROMPT_KEY_BINDINGS,
)


def _multiline_prompt() -> str:
    return _multiline_prompt_session.prompt(
        "",
        bottom_toolbar=HTML(MULTILINE_PROMPT_TOOLBAR_TEXT),
    )
