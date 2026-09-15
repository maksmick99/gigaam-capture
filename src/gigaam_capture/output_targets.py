from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from PySide6.QtGui import QGuiApplication

from gigaam_capture.models import (
    TARGET_ACTIVE_TEXT_FIELD,
    TARGET_CLIPBOARD,
    AppSettings,
)
from gigaam_capture.platform import is_target_supported, target_unavailable_reason
from gigaam_capture.platform.automation import (
    ActiveAppAutomation,
    create_active_app_automation,
)


class UnsupportedTargetError(RuntimeError):
    """Raised when an output target cannot run on the current platform."""


class OutputTarget(Protocol):
    name: str

    def deliver(self, text: str) -> None:
        ...


@dataclass(slots=True)
class ClipboardTarget:
    name: str = TARGET_CLIPBOARD

    def deliver(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)


@dataclass(slots=True)
class ActiveTextFieldTarget:
    automation: ActiveAppAutomation
    name: str = TARGET_ACTIVE_TEXT_FIELD

    def deliver(self, text: str) -> None:
        self.automation.paste_text(text)

    def describe_target(self) -> str:
        return self.automation.describe_target()


def create_output_target(target_mode: str) -> OutputTarget:
    if target_mode == TARGET_CLIPBOARD:
        return ClipboardTarget()

    if target_mode == TARGET_ACTIVE_TEXT_FIELD:
        _require_platform_support(target_mode)
        return ActiveTextFieldTarget(automation=create_active_app_automation())

    raise UnsupportedTargetError(f"Unknown output target: {target_mode!r}")


def ensure_supported_target_mode(
    settings: AppSettings,
) -> tuple[AppSettings, str | None]:
    """Return settings with a usable target mode plus an optional notice.

    A target saved on another platform (or before a backend existed) must never
    prevent the app from starting, so it is replaced by clipboard delivery.
    """
    if is_target_supported(settings.target_mode):
        return settings, None

    reason = target_unavailable_reason(settings.target_mode) or (
        f"Output target {settings.target_mode!r} is not available."
    )
    return (
        replace(settings, target_mode=TARGET_CLIPBOARD),
        f"{reason} Clipboard mode enabled.",
    )


def _require_platform_support(target_mode: str) -> None:
    if is_target_supported(target_mode):
        return

    raise UnsupportedTargetError(
        target_unavailable_reason(target_mode)
        or f"Output target {target_mode!r} is not available on this platform."
    )
