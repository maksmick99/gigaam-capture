from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Any, Protocol

from PySide6.QtGui import QGuiApplication


class ActiveAppAutomation(Protocol):
    def paste_text(self, text: str) -> None:
        ...

    def describe_target(self) -> str:
        ...


class AutomationPermissionError(RuntimeError):
    pass


@dataclass(slots=True)
class AccessibilityAutomationPlan:
    platform_name: str
    status: str
    notes: str


@dataclass(slots=True)
class ActiveTargetInfo:
    app_name: str
    bundle_id: str
    window_title: str
    role: str

    def summary(self) -> str:
        parts = [self.app_name or "Unknown app"]
        if self.window_title:
            parts.append(self.window_title)
        if self.role:
            parts.append(self.role)
        return " | ".join(parts)


@dataclass(frozen=True, slots=True)
class AppProfile:
    display_name: str
    allowed_roles: frozenset[str]
    focus_hint: str


PLANNED_AUTOMATION = {
    "darwin": AccessibilityAutomationPlan(
        platform_name="macOS",
        status="planned",
        notes="Use Accessibility APIs to focus active input and inject clipboard/paste.",
    ),
    "win32": AccessibilityAutomationPlan(
        platform_name="Windows",
        status="planned",
        notes="Use UI Automation or Win32 focus APIs for active text controls.",
    ),
    "linux": AccessibilityAutomationPlan(
        platform_name="Linux",
        status="planned",
        notes="Use X11/Wayland specific automation backend depending on session type.",
    ),
}


class MacOSPasteAutomation:
    _GENERIC_TEXT_ENTRY_ROLES = {
        "AXTextArea",
        "AXTextField",
        "AXComboBox",
        "AXSearchField",
    }
    _BUNDLE_PROFILES = {
        "ru.keepcoder.Telegram": AppProfile(
            display_name="Telegram Desktop",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXGroup", "AXScrollArea", "AXWebArea"}
            ),
            focus_hint="Focus the Telegram message composer before starting capture.",
        ),
        "org.telegram.desktop": AppProfile(
            display_name="Telegram Desktop",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXGroup", "AXScrollArea", "AXWebArea"}
            ),
            focus_hint="Focus the Telegram message composer before starting capture.",
        ),
        "net.whatsapp.WhatsApp": AppProfile(
            display_name="WhatsApp Desktop",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXGroup", "AXScrollArea", "AXWebArea"}
            ),
            focus_hint="Focus the WhatsApp message composer before starting capture.",
        ),
        "com.apple.Safari": AppProfile(
            display_name="Safari",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
            ),
            focus_hint="Focus the chat input inside the browser tab before starting capture.",
        ),
        "com.google.Chrome": AppProfile(
            display_name="Google Chrome",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
            ),
            focus_hint="Focus the chat input inside the browser tab before starting capture.",
        ),
        "org.chromium.Chromium": AppProfile(
            display_name="Chromium",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
            ),
            focus_hint="Focus the chat input inside the browser tab before starting capture.",
        ),
        "org.mozilla.firefox": AppProfile(
            display_name="Firefox",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
            ),
            focus_hint="Focus the chat input inside the browser tab before starting capture.",
        ),
        "com.operasoftware.Opera": AppProfile(
            display_name="Opera",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
            ),
            focus_hint="Focus the chat input inside the browser tab before starting capture.",
        ),
        "com.brave.Browser": AppProfile(
            display_name="Brave",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
            ),
            focus_hint="Focus the chat input inside the browser tab before starting capture.",
        ),
        "com.microsoft.edgemac": AppProfile(
            display_name="Microsoft Edge",
            allowed_roles=frozenset(
                {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
            ),
            focus_hint="Focus the chat input inside the browser tab before starting capture.",
        ),
    }

    _ROLE_GUIDANCE = {
        "AXWebArea",
    }

    def has_accessibility_access(self) -> bool:
        if sys.platform != "darwin":
            return False

        from Quartz import AXIsProcessTrusted  # type: ignore[import-not-found]

        return bool(AXIsProcessTrusted())

    def ensure_accessibility_access(self) -> None:
        if self.has_accessibility_access():
            return

        raise AutomationPermissionError(
            "macOS Accessibility access is required for active text-field paste mode. "
            "Grant Accessibility permissions to your Python runtime or packaged app in "
            "System Settings -> Privacy & Security -> Accessibility."
        )

    def describe_target(self) -> str:
        info = self.get_active_target_info()
        return self._summarize_target(info)

    def get_active_target_info(self) -> ActiveTargetInfo:
        self.ensure_accessibility_access()

        from AppKit import NSWorkspace  # type: ignore[import-not-found]
        from HIServices import (  # type: ignore[import-not-found]
            AXUIElementCopyAttributeValue,
            AXUIElementCreateApplication,
            kAXFocusedUIElementAttribute,
            kAXFocusedWindowAttribute,
            kAXRoleAttribute,
            kAXTitleAttribute,
        )

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            raise RuntimeError("Could not determine the frontmost application")

        element = AXUIElementCreateApplication(app.processIdentifier())
        focused_ui = AXUIElementCopyAttributeValue(element, kAXFocusedUIElementAttribute, None)
        focused_window = AXUIElementCopyAttributeValue(element, kAXFocusedWindowAttribute, None)

        role = self._safe_attribute(focused_ui, kAXRoleAttribute)
        window_title = self._safe_attribute(focused_window, kAXTitleAttribute)

        return ActiveTargetInfo(
            app_name=app.localizedName() or "",
            bundle_id=app.bundleIdentifier() or "",
            window_title=window_title or "",
            role=role or "",
        )

    def validate_target(self) -> ActiveTargetInfo:
        info = self.get_active_target_info()
        allowed_roles = self._allowed_roles_for_target(info)
        if info.role and info.role not in allowed_roles:
            extra_guidance = ""
            if info.role in self._ROLE_GUIDANCE and not self._bundle_has_role_override(info):
                extra_guidance = (
                    " The focused control may belong to a browser or Electron surface; "
                    "support for this role is limited to known messenger/browser apps."
                )
            focus_hint = self._focus_hint_for_target(info)
            raise RuntimeError(
                "The currently focused UI element does not look like a text input. "
                f"Frontmost target: {self._summarize_target(info)}. {focus_hint}{extra_guidance}"
            )
        return info

    def _allowed_roles_for_target(self, info: ActiveTargetInfo) -> set[str]:
        roles = set(self._GENERIC_TEXT_ENTRY_ROLES)
        profile = self._profile_for_target(info)
        if profile is not None:
            roles.update(profile.allowed_roles)
        return roles

    def _bundle_has_role_override(self, info: ActiveTargetInfo) -> bool:
        return info.bundle_id in self._BUNDLE_PROFILES

    def _profile_for_target(self, info: ActiveTargetInfo) -> AppProfile | None:
        return self._BUNDLE_PROFILES.get(info.bundle_id)

    def _focus_hint_for_target(self, info: ActiveTargetInfo) -> str:
        profile = self._profile_for_target(info)
        if profile is not None:
            return profile.focus_hint
        return "Focus a text input in the target app and retry."

    def _summarize_target(self, info: ActiveTargetInfo) -> str:
        summary = info.summary()
        profile = self._profile_for_target(info)
        if profile is None:
            return summary
        return f"{summary} | Profile: {profile.display_name}"

    def paste_text(self, text: str) -> None:
        if sys.platform != "darwin":
            raise RuntimeError("macOS active text-field automation is only available on darwin")

        self.validate_target()

        clipboard = QGuiApplication.clipboard()
        previous_text = clipboard.text()
        clipboard.setText(text)

        try:
            self._send_cmd_v()
            time.sleep(0.12)
        finally:
            clipboard.setText(previous_text)

    def _send_cmd_v(self) -> None:
        from Quartz import (  # type: ignore[import-not-found]
            CGEventCreateKeyboardEvent,
            CGEventPost,
            kCGHIDEventTap,
            kCGEventFlagMaskCommand,
        )

        keycode_v = 9
        key_down = CGEventCreateKeyboardEvent(None, keycode_v, True)
        key_up = CGEventCreateKeyboardEvent(None, keycode_v, False)

        if key_down is None or key_up is None:
            raise AutomationPermissionError(
                "Could not create paste keyboard events. Check Accessibility permissions."
            )

        key_down.setFlags(kCGEventFlagMaskCommand)
        key_up.setFlags(kCGEventFlagMaskCommand)

        CGEventPost(kCGHIDEventTap, key_down)
        CGEventPost(kCGHIDEventTap, key_up)

    def _safe_attribute(self, element: Any, attribute: str) -> str:
        if element is None:
            return ""

        from HIServices import AXUIElementCopyAttributeValue  # type: ignore[import-not-found]

        try:
            value = AXUIElementCopyAttributeValue(element, attribute, None)
        except Exception:
            return ""

        return str(value) if value is not None else ""


def create_active_app_automation() -> ActiveAppAutomation:
    if sys.platform == "darwin":
        return MacOSPasteAutomation()

    raise NotImplementedError(
        f"Active text-field automation is not implemented for platform: {sys.platform}"
    )
