"""A small generalization of the default agent that puts the user in the loop.

There are three modes:
- human: commands issued by the user are executed immediately
- confirm: commands issued by the LM but not whitelisted are confirmed by the user
- yolo: commands issued by the LM are executed immediately without confirmation
"""

import re
from contextlib import contextmanager
from typing import Literal, NoReturn

from rich.console import Console
from rich.rule import Rule

from gemmacode.agents.default import AgentConfig, DefaultAgent
from gemmacode.agents.utils.prompt_user import _multiline_prompt, prompt_session
from gemmacode.exceptions import LimitsExceeded, Submitted, UserInterruption
from gemmacode.models.utils.content_string import get_content_string
from gemmacode.utils.status import build_status_text

console = Console(highlight=False)


class InteractiveAgentConfig(AgentConfig):
    mode: Literal["human", "confirm", "yolo"] = "confirm"
    """Whether to confirm actions."""
    whitelist_actions: list[str] = []
    """Never confirm actions that match these regular expressions."""
    confirm_exit: bool = True
    """If the agent wants to finish, do we ask for confirmation from user?"""


class InteractiveAgent(DefaultAgent):
    _MODE_COMMANDS_MAPPING = {"/u": "human", "/c": "confirm", "/y": "yolo"}

    def __init__(self, *args, config_class=InteractiveAgentConfig, **kwargs):
        super().__init__(*args, config_class=config_class, **kwargs)
        self.cost_last_confirmed = 0.0

    def _interrupt(self, content: str, *, itype: str = "UserInterruption") -> NoReturn:
        raise UserInterruption({"role": "user", "content": content, "extra": {"interrupt_type": itype}})

    def _short_preview(self, content: str, *, limit: int = 120) -> str | None:
        preview = " ".join(content.split())
        if not preview:
            return None
        if len(preview) > limit:
            return None
        return preview

    def _message_stage(self, msg: dict, role: str) -> tuple[str, str]:
        if role == "assistant":
            return "Resposta do modelo", "magenta"
        if role == "system":
            return "Contexto do sistema carregado", "cyan"
        if role == "user" and msg.get("extra", {}).get("actions"):
            return "Observação do ambiente recebida", "green"
        if role == "user":
            return "Tarefa carregada", "blue"
        if role == "tool":
            return "Ferramenta executada", "green"
        if role == "exit":
            return "Encerramento do agente", "red"
        return role.capitalize(), "cyan"

    @contextmanager
    def _status_scope(
        self,
        title: str,
        detail: str | None = None,
        *,
        color: str = "cyan",
        symbol: str = "●",
        done: str | None = None,
    ):
        with console.status(build_status_text(title, detail, color=color, symbol=symbol), spinner="dots", spinner_style=color):
            yield
        if done:
            console.print(build_status_text(done, detail, color="green", symbol="✓"))

    def add_messages(self, *messages: dict) -> list[dict]:
        for msg in messages:
            role, content = msg.get("role") or msg.get("type", "unknown"), get_content_string(msg)
            if role == "assistant":
                console.print(
                    build_status_text(
                        "Resposta do modelo",
                        f"passo {self.n_calls} • ${self.cost:.2f}",
                        color="magenta",
                        symbol="↳",
                    )
                )
            else:
                stage_title, stage_color = self._message_stage(msg, role)
                detail = self._short_preview(content)
                console.print(build_status_text(stage_title, detail, color=stage_color, symbol="↳"))
            if role == "assistant" or (preview := self._short_preview(content)):
                console.print(content if role == "assistant" else preview, highlight=False, markup=False)
        return super().add_messages(*messages)

    def query(self) -> dict:
        # Extend supermethod to handle human mode
        if self.config.mode == "human":
            match command := self._prompt_and_handle_slash_commands("[bold yellow]>[/bold yellow] "):
                case "/y" | "/c":
                    pass
                case _:
                    msg = {
                        "role": "user",
                        "content": f"User command: \n```bash\n{command}\n```",
                        "extra": {"actions": [{"command": command}]},
                    }
                    self.add_messages(msg)
                    return msg
        try:
            return super().query()
        except LimitsExceeded:
            console.print(
                f"Limits exceeded. Limits: {self.config.step_limit} steps, ${self.config.cost_limit}.\n"
                f"Current spend: {self.n_calls} steps, ${self.cost:.2f}."
            )
            self.config.step_limit = int(input("New step limit: "))
            self.config.cost_limit = float(input("New cost limit: "))
            return super().query()

    def step(self) -> list[dict]:
        # Override the step method to handle user interruption
        try:
            console.print(Rule(style="bright_black"))
            return super().step()
        except KeyboardInterrupt:
            interruption_message = self._prompt_and_handle_slash_commands(
                "\n\n[bold yellow]Interrupted.[/bold yellow] "
                "[green]Type a comment/command[/green] (/h for available commands)"
                "\n[bold yellow]>[/bold yellow] "
            ).strip()
            if not interruption_message or interruption_message in self._MODE_COMMANDS_MAPPING:
                interruption_message = "Temporary interruption caught."
            self._interrupt(f"Interrupted by user: {interruption_message}")

    def execute_actions(self, message: dict) -> list[dict]:
        # Override to handle user confirmation and confirm_exit, with try/finally to preserve partial outputs
        actions = message.get("extra", {}).get("actions", [])
        commands = [action["command"] for action in actions]
        outputs = []
        try:
            self._ask_confirmation_or_interrupt(commands)
            with self._status_scope(
                "Executando ações",
                detail=f"{len(actions)} ação(ões)",
                color="magenta",
                done="Ações concluídas",
            ):
                for index, action in enumerate(actions, start=1):
                    console.print(
                        build_status_text(
                            "Executando ação",
                            f"{index}/{len(actions)}",
                            color="magenta",
                            symbol="→",
                        )
                    )
                    outputs.append(self.env.execute(action))
        except Submitted as e:
            self._check_for_new_task_or_submit(e)
        finally:
            result = self.add_messages(
                *self.model.format_observation_messages(message, outputs, self.get_template_vars())
            )
        return result

    def _add_observation_messages(self, message: dict, outputs: list[dict]) -> list[dict]:
        return self.add_messages(*self.model.format_observation_messages(message, outputs, self.get_template_vars()))

    def _check_for_new_task_or_submit(self, e: Submitted) -> NoReturn:
        """Check if user wants to add a new task or submit."""
        if self.config.confirm_exit:
            message = (
                "[bold yellow]Agent wants to finish.[/bold yellow] "
                "[bold green]Type new task[/bold green] or [bold]Enter[/bold] to quit "
                "([bold]/h[/bold] for commands)\n"
                "[bold yellow]>[/bold yellow] "
            )
            user_input = self._prompt_and_handle_slash_commands(message).strip()
            if user_input == "/u":  # directly continue
                self._interrupt("Switched to human mode.")
            elif user_input in self._MODE_COMMANDS_MAPPING:  # ask again
                return self._check_for_new_task_or_submit(e)
            elif user_input:
                self._interrupt(f"The user added a new task: {user_input}", itype="UserNewTask")
        raise e

    def _should_ask_confirmation(self, action: str) -> bool:
        return self.config.mode == "confirm" and not any(re.match(r, action) for r in self.config.whitelist_actions)

    def _ask_confirmation_or_interrupt(self, commands: list[str]) -> None:
        if not any(self._should_ask_confirmation(c) for c in commands):
            return
        console.print(build_status_text("Aguardando confirmação", f"{len(commands)} ação(ões)", color="yellow", symbol="?"))
        prompt = (
            f"[bold yellow]Execute {len(commands)} action(s)?[/] [green][bold]Enter[/] to confirm[/], "
            "[red]type [bold]comment[/] to reject[/], or [blue][bold]/h[/] to show available commands[/]\n"
            "[bold yellow]>[/bold yellow] "
        )
        match user_input := self._prompt_and_handle_slash_commands(prompt).strip():
            case "" | "/y":
                console.print(build_status_text("Ação confirmada", color="green", symbol="✓"))
            case "/u":  # Skip execution action and get back to query
                self._interrupt("Commands not executed. Switching to human mode", itype="UserRejection")
            case _:
                console.print(build_status_text("Ação rejeitada", color="red", symbol="✗"))
                self._interrupt(
                    f"Commands not executed. The user rejected your commands with the following message: {user_input}",
                    itype="UserRejection",
                )

    def _prompt_and_handle_slash_commands(self, prompt: str, *, _multiline: bool = False) -> str:
        """Prompts the user, takes care of /h (followed by requery) and sets the mode. Returns the user input."""
        console.print(prompt, end="")
        if _multiline:
            return _multiline_prompt()
        user_input = prompt_session.prompt("")
        if user_input == "/m":
            return self._prompt_and_handle_slash_commands(prompt, _multiline=True)
        if user_input == "/h":
            console.print(
                f"Current mode: [bold green]{self.config.mode}[/bold green]\n"
                f"[bold green]/y[/bold green] to switch to [bold yellow]yolo[/bold yellow] mode (execute LM commands without confirmation)\n"
                f"[bold green]/c[/bold green] to switch to [bold yellow]confirmation[/bold yellow] mode (ask for confirmation before executing LM commands)\n"
                f"[bold green]/u[/bold green] to switch to [bold yellow]human[/bold yellow] mode (execute commands issued by the user)\n"
                f"[bold green]/m[/bold green] to enter multiline comment "
                f"([bold yellow]Enter[/bold yellow] sends, [bold yellow]Shift+Enter[/bold yellow] adds a new line)",
            )
            return self._prompt_and_handle_slash_commands(prompt)
        if user_input in self._MODE_COMMANDS_MAPPING:
            if self.config.mode == self._MODE_COMMANDS_MAPPING[user_input]:
                return self._prompt_and_handle_slash_commands(
                    f"[bold red]Already in {self.config.mode} mode.[/bold red]\n{prompt}"
                )
            self.config.mode = self._MODE_COMMANDS_MAPPING[user_input]
            console.print(f"Switched to [bold green]{self.config.mode}[/bold green] mode.")
            return user_input
        return user_input
