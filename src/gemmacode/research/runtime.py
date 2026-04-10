"""Runtime phase enforcement for the RepoMap-first loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import (
    ResearchDecision,
    ResearchPlan,
    looks_like_read_only_command,
)


SEARCH_PREFIXES = ("rg ", "grep ", "git grep")
ALWAYS_ALLOWED_PREFIXES = (
    "echo ",
    "printf ",
    "pwd",
    "true",
    "false",
    "date",
    "whoami",
    "uname ",
    "id ",
)


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term and term.lower() in lowered for term in terms)


def _looks_like_search_command(command: str) -> bool:
    normalized = command.strip().lower()
    return normalized.startswith(SEARCH_PREFIXES)


def _looks_like_file_read_command(command: str) -> bool:
    return looks_like_read_only_command(command)


@dataclass(slots=True)
class ResearchGate:
    plan: ResearchPlan
    phase: str = field(default="research")
    relevant_searches: int = 0
    open_reads: int = 0
    blocked_edits: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "ResearchGate | None":
        if not payload:
            return None
        return cls(plan=ResearchPlan.from_dict(payload), phase=str(payload.get("phase", "research")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "phase": self.phase,
            "relevant_searches": self.relevant_searches,
            "open_reads": self.open_reads,
            "blocked_edits": self.blocked_edits,
            "events": list(self.events),
            "transitions": list(self.transitions),
        }

    def _allowed_to_implement(self) -> bool:
        if self.plan.mode == "off":
            return True
        if self.plan.task_kind == "explicit_file":
            return True
        return (
            self.relevant_searches >= self.plan.budgets.get("min_relevant_searches", 0)
            and self.open_reads >= self.plan.budgets.get("min_open_reads", 0)
        )

    def _transition(self, phase: str, reason: str) -> None:
        if self.phase == phase:
            return
        self.phase = phase
        self.transitions.append({"phase": phase, "reason": reason})
        self.events.append({"type": "transition", "phase": phase, "reason": reason})

    def should_transition_now(self) -> bool:
        return self.phase == "research" and self._allowed_to_implement()

    def evaluate_command(self, command: str) -> ResearchDecision:
        command = command.strip()
        if not command:
            return ResearchDecision(True, "empty command", "noop")
        if self.plan.mode == "off" or self.phase == "implementation":
            return ResearchDecision(True, "research gate disabled or already completed", "implementation")
        normalized = command.lower()
        if "complete_task_and_submit_final_output" in normalized or normalized.startswith(ALWAYS_ALLOWED_PREFIXES):
            return ResearchDecision(True, "harmless command", "research")
        if _looks_like_file_read_command(command) or _looks_like_search_command(command):
            return ResearchDecision(True, "research command", "research")
        if self._allowed_to_implement():
            self._transition("implementation", "research minimum satisfied")
            return ResearchDecision(True, "transitioned to implementation", "implementation", should_transition=True)
        self.blocked_edits += 1
        self.events.append({"type": "blocked", "command": command, "reason": "research minimum not satisfied"})
        return ResearchDecision(
            False,
            "Stay in research: consult the RepoMap, shortlist candidates, run rg, and open a few files before editing.",
            "blocked",
        )

    def record_execution(self, command: str, output: dict[str, Any]) -> None:
        command = command.strip()
        self.events.append(
            {
                "type": "execution",
                "command": command,
                "returncode": output.get("returncode"),
            }
        )
        if _looks_like_search_command(command):
            if _contains_any(command, self.plan.search_terms) or not self.plan.search_terms:
                self.relevant_searches += 1
            else:
                self.relevant_searches += 1
        if _looks_like_file_read_command(command):
            self.open_reads += 1
        if self.phase == "research" and self.should_transition_now():
            self._transition("implementation", "research minimum satisfied after execution")
        elif self.phase == "implementation" and _looks_like_search_command(command):
            if output.get("returncode") == 1 or "No such file" in str(output.get("output", "")):
                self._transition("research", "search contradicted the working hypothesis")

    def blocked_output(self, command: str, reason: str) -> dict[str, Any]:
        return {
            "output": f"{reason}\n\nCommand blocked: {command}",
            "returncode": 1,
            "exception_info": "",
            "extra": {
                "blocked": True,
                "research_phase": self.phase,
                "reason": reason,
            },
        }
