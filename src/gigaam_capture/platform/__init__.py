from __future__ import annotations

import sys
from dataclasses import dataclass

from ..models import TARGET_ACTIVE_TEXT_FIELD, TARGET_CLIPBOARD

__all__ = [
    "TargetCapability",
    "active_text_field_backend",
    "is_target_supported",
    "supported_targets",
    "target_capabilities",
    "target_unavailable_reason",
]

# Active text-field delivery backends keyed by `sys.platform`. A platform is
# listed here only once its backend module is actually implemented, so the
# capability report can never promise delivery the runtime cannot perform.
_ACTIVE_TEXT_FIELD_BACKENDS = {
    "darwin": "macOS Accessibility (Quartz paste)",
    "win32": "Windows UI Automation + Win32 paste",
}


@dataclass(frozen=True, slots=True)
class TargetCapability:
    mode: str
    available: bool
    backend: str
    reason: str | None = None


def active_text_field_backend() -> str | None:
    return _ACTIVE_TEXT_FIELD_BACKENDS.get(sys.platform)


def active_text_field_unavailable_reason() -> str | None:
    if active_text_field_backend() is not None:
        return None
    return (
        f"Active text-field delivery is not implemented on this platform "
        f"({sys.platform}). Use clipboard mode instead."
    )


def target_capabilities() -> list[TargetCapability]:
    backend = active_text_field_backend()
    return [
        TargetCapability(
            mode=TARGET_CLIPBOARD,
            available=True,
            backend="Qt clipboard",
        ),
        TargetCapability(
            mode=TARGET_ACTIVE_TEXT_FIELD,
            available=backend is not None,
            backend=backend or "not implemented",
            reason=active_text_field_unavailable_reason(),
        ),
    ]


def supported_targets() -> list[str]:
    return [
        capability.mode
        for capability in target_capabilities()
        if capability.available
    ]


def is_target_supported(mode: str) -> bool:
    return any(
        capability.mode == mode and capability.available
        for capability in target_capabilities()
    )


def target_unavailable_reason(mode: str) -> str | None:
    for capability in target_capabilities():
        if capability.mode == mode:
            return None if capability.available else capability.reason
    return f"Unknown output target: {mode!r}"

