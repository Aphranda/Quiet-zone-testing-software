from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class MainWindowFeedback:
    show_status: Callable[[str], None]
    append_info: Callable[[str], None]
    append_error: Callable[[str], None]
    show_error_dialog: Callable[[str, str], None] | None = None
    max_error_chars: int = 500

    def info(self, status: str, log_message: str | None = None) -> None:
        self.show_status(status)
        if log_message:
            self.append_info(log_message)

    def error(self, title: str, message: str, *, dialog: bool = True) -> str:
        formatted = self.format_error_message(message)
        self.show_status(title)
        self.append_error(f"{title}: {formatted}")
        if dialog and self.show_error_dialog is not None:
            self.show_error_dialog(title, formatted)
        return formatted

    def format_error_message(self, message: str) -> str:
        message = str(message or "未知错误").strip()
        if not message:
            return "未知错误"
        if len(message) <= self.max_error_chars:
            return message
        return f"{message[:self.max_error_chars]}..."
