from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ActiveAppAutomation(Protocol):
    def paste_text(self, text: str) -> None:
        ...

    def describe_target(self) -> str:
        ...


class AutomationPermissionError(RuntimeError):
    """Raised when the OS blocks automation for the current process."""


@dataclass(slots=True)
class ActiveTargetInfo:
    """Platform-neutral description of the current delivery target.

    ``bundle_id`` carries the macOS bundle identifier, ``process_name`` the
    Windows executable name, ``role`` the macOS accessibility role, and
    ``control_type``/``class_name`` the Windows UI Automation control type and
    Win32 window class.
    """

    app_name: str
    bundle_id: str = ""
    window_title: str = ""
    role: str = ""
    process_name: str = ""
    class_name: str = ""
    control_type: str = ""
    automation_id: str = ""

    def summary(self) -> str:
        parts = [self.app_name or "Unknown app"]
        if self.window_title:
            parts.append(self.window_title)
        detail = self.role or self.control_type or self.class_name
        if detail:
            parts.append(detail)
        return " | ".join(parts)

    def profile_key(self) -> str:
        """Return the key used to look up an app profile for this target."""
        return self.bundle_id or self.process_name.lower()


@dataclass(frozen=True, slots=True)
class AppProfile:
    """Delivery policy for a recognized target application."""

    display_name: str
    allowed_roles: frozenset[str] = frozenset()
    focus_hint: str = "Focus a text input in the target app and retry."
    allowed_classes: frozenset[str] = frozenset()
    allows_qt_shells: bool = False


def describe_with_profile(info: ActiveTargetInfo, profile: AppProfile | None) -> str:
    if profile is None:
        return info.summary()
    return f"{info.summary()} | Profile: {profile.display_name}"


def focus_hint_for(profile: AppProfile | None) -> str:
    if profile is None:
        return "Focus a text input in the target app and retry."
    return profile.focus_hint
