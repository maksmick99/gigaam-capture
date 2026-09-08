from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtGui import QGuiApplication

from gigaam_capture.platform.automation import ActiveAppAutomation, create_active_app_automation


class OutputTarget(Protocol):
    name: str

    def deliver(self, text: str) -> None:
        ...


@dataclass(slots=True)
class ClipboardTarget:
    name: str = "clipboard"

    def deliver(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)


@dataclass(slots=True)
class ActiveTextFieldTarget:
    automation: ActiveAppAutomation
    name: str = "active-text-field"

    def deliver(self, text: str) -> None:
        self.automation.paste_text(text)

    def describe_target(self) -> str:
        return self.automation.describe_target()


def create_output_target(target_mode: str) -> OutputTarget:
    if target_mode == "clipboard":
        return ClipboardTarget()

    if target_mode == "active-text-field":
        return ActiveTextFieldTarget(automation=create_active_app_automation())

    raise ValueError(
        f"Unsupported output target: {target_mode!r} on platform {sys.platform}"
    )
