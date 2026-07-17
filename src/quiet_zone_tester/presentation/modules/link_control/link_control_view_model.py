from __future__ import annotations

from dataclasses import dataclass

from quiet_zone_tester.domains.link_management import normalize_s_parameter


DEFAULT_LINK_COMMANDS = (
    "CONFigure:LINK DUT, AMP1, SA",
    "CONFigure:LINK DUT, VNA2",
    "CONFigure:LINK DUT, AMP1, VNA2",
    "CONFigure:LINK H, SG",
    "CONFigure:LINK H, VNA1",
    "CONFigure:LINK H, SA",
    "CONFigure:LINK H, AMP2, SG",
    "CONFigure:LINK H, AMP2, VNA1",
    "CONFigure:LINK H, AMP2, SA",
    "CONFigure:LINK V, SG",
    "CONFigure:LINK V, VNA1",
    "CONFigure:LINK V, SA",
    "CONFigure:LINK V, AMP2, SG",
    "CONFigure:LINK V, AMP2, VNA1",
    "CONFigure:LINK V, AMP2, SA",
)


@dataclass(frozen=True)
class LinkControlUiState:
    inputs_enabled: bool


@dataclass(frozen=True)
class LinkDiagramState:
    selected_command: str
    highlighted_tokens: frozenset[str]


class LinkControlViewModel:
    def link_commands(self) -> tuple[str, ...]:
        return DEFAULT_LINK_COMMANDS

    def route_parameter(self, parameter: str) -> str:
        return normalize_s_parameter(parameter)

    def send_command(self, command: str) -> str:
        command = str(command).strip()
        if not command:
            return DEFAULT_LINK_COMMANDS[0]
        return command

    def selected_command(self, command: str) -> str:
        return self.send_command(command)

    def current_command_text(self, command: str) -> str:
        return f"当前命令：{self.selected_command(command)}"

    def diagram_state(self, command: str) -> LinkDiagramState:
        selected_command = self.selected_command(command)
        command_upper = selected_command.upper()
        return LinkDiagramState(
            selected_command=selected_command,
            highlighted_tokens=frozenset(
                token
                for token in ("DUT", "H", "V", "VNA1", "VNA2", "SG", "SA", "AMP1", "AMP2")
                if token in command_upper
            ),
        )

    @staticmethod
    def result_text(message: str) -> str:
        return str(message or "").strip() or "-"

    @staticmethod
    def ui_state(*, connected: bool, busy: bool) -> LinkControlUiState:
        return LinkControlUiState(inputs_enabled=bool(connected) and not bool(busy))
