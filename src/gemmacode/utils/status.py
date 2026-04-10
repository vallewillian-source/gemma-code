from __future__ import annotations

from contextlib import contextmanager

from rich.console import Console
from rich.text import Text

console = Console(highlight=False)


def build_status_text(title: str, detail: str | None = None, *, color: str = "cyan", symbol: str = "●") -> Text:
    text = Text()
    text.append(symbol, style=f"bold {color}")
    text.append(" ")
    text.append(title, style=f"bold {color}")
    if detail:
        text.append("  ", style="dim")
        text.append(detail, style="dim")
    return text


def print_status(title: str, detail: str | None = None, *, color: str = "cyan", symbol: str = "●") -> None:
    console.print(build_status_text(title, detail, color=color, symbol=symbol))


@contextmanager
def status_scope(title: str, detail: str | None = None, *, color: str = "cyan", symbol: str = "●", done: str | None = None):
    print_status(title, detail, color=color, symbol=symbol)
    try:
        yield
    finally:
        if done:
            print_status(done, detail, color="green", symbol="✓")
