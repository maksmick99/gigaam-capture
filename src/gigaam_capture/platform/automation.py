from __future__ import annotations

import sys

from .targets import (
    ActiveAppAutomation,
    ActiveTargetInfo,
    AppProfile,
    AutomationPermissionError,
)

__all__ = [
    "ActiveAppAutomation",
    "ActiveTargetInfo",
    "AppProfile",
    "AutomationPermissionError",
    "create_active_app_automation",
]

# ``MacOSPasteAutomation`` and ``WindowsPasteAutomation`` stay importable from
# this module through ``__getattr__`` below, which keeps a single import path
# for existing callers while loading OS-specific frameworks only when needed.


def create_active_app_automation() -> ActiveAppAutomation:
    """Return the active text-field backend for the current platform.

    ``MacOSPasteAutomation`` is imported eagerly because its macOS frameworks
    are loaded lazily, so importing it is safe on every platform. The Windows
    backend is imported on demand.
    """
    if sys.platform == "darwin":
        from .macos import MacOSPasteAutomation

        return MacOSPasteAutomation()

    if sys.platform == "win32":
        from .windows import WindowsPasteAutomation

        return WindowsPasteAutomation()

    raise NotImplementedError(
        f"Active text-field automation is not implemented for platform: {sys.platform}"
    )


def __getattr__(name: str):
    """Resolve the platform backend classes lazily for backwards compatibility."""
    if name == "MacOSPasteAutomation":
        from .macos import MacOSPasteAutomation

        return MacOSPasteAutomation

    if name == "WindowsPasteAutomation":
        from .windows import WindowsPasteAutomation

        return WindowsPasteAutomation

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
