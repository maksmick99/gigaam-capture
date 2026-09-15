from __future__ import annotations

import sys
import time
from typing import Any

from PySide6.QtGui import QGuiApplication

from .targets import (
    ActiveTargetInfo,
    AppProfile,
    AutomationPermissionError,
    describe_with_profile,
    focus_hint_for,
)

_MESSENGER_ROLES = frozenset(
    {"AXTextArea", "AXTextField", "AXGroup", "AXScrollArea", "AXWebArea"}
)
_BROWSER_ROLES = frozenset(
    {"AXTextArea", "AXTextField", "AXSearchField", "AXWebArea"}
)

_TELEGRAM_HINT = "Focus the Telegram message composer before starting capture."
_WHATSAPP_HINT = "Focus the WhatsApp message composer before starting capture."
_BROWSER_HINT = "Focus the chat input inside the browser tab before starting capture."


def _messenger_profile(display_name: str, focus_hint: str) -> AppProfile:
    return AppProfile(
        display_name=display_name,
        allowed_roles=_MESSENGER_ROLES,
        focus_hint=focus_hint,
    )


def _browser_profile(display_name: str) -> AppProfile:
    return AppProfile(
        display_name=display_name,
        allowed_roles=_BROWSER_ROLES,
        focus_hint=_BROWSER_HINT,
    )


class MacOSPasteAutomation:
    _GENERIC_TEXT_ENTRY_ROLES = {
        "AXTextArea",
        "AXTextField",
        "AXComboBox",
        "AXSearchField",
    }
    _BUNDLE_PROFILES = {
        "ru.keepcoder.Telegram": _messenger_profile("Telegram Desktop", _TELEGRAM_HINT),
        "org.telegram.desktop": _messenger_profile("Telegram Desktop", _TELEGRAM_HINT),
        "net.whatsapp.WhatsApp": _messenger_profile("WhatsApp Desktop", _WHATSAPP_HINT),
        "com.apple.Safari": _browser_profile("Safari"),
        "com.google.Chrome": _browser_profile("Google Chrome"),
        "org.chromium.Chromium": _browser_profile("Chromium"),
        "org.mozilla.firefox": _browser_profile("Firefox"),
        "com.operasoftware.Opera": _browser_profile("Opera"),
        "com.brave.Browser": _browser_profile("Brave"),
        "com.microsoft.edgemac": _browser_profile("Microsoft Edge"),
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
        focused_ui = AXUIElementCopyAttributeValue(
            element, kAXFocusedUIElementAttribute, None
        )
        focused_window = AXUIElementCopyAttributeValue(
            element, kAXFocusedWindowAttribute, None
        )

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
            if info.role in self._ROLE_GUIDANCE and not self._bundle_has_role_override(
                info
            ):
                extra_guidance = (
                    " The focused control may belong to a browser or Electron surface; "
                    "support for this role is limited to known messenger/browser apps."
                )
            focus_hint = focus_hint_for(self._profile_for_target(info))
            raise RuntimeError(
                "The currently focused UI element does not look like a text input. "
                f"Frontmost target: {self._summarize_target(info)}. "
                f"{focus_hint}{extra_guidance}"
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

    def _summarize_target(self, info: ActiveTargetInfo) -> str:
        return describe_with_profile(info, self._profile_for_target(info))

    def paste_text(self, text: str) -> None:
        if sys.platform != "darwin":
            raise RuntimeError(
                "macOS active text-field automation is only available on darwin"
            )

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
            kCGEventFlagMaskCommand,
            kCGHIDEventTap,
        )

        keycode_v = 9
        key_down = CGEventCreateKeyboardEvent(None, keycode_v, True)
        key_up = CGEventCreateKeyboardEvent(None, keycode_v, False)

        if key_down is None or key_up is None:
            raise AutomationPermissionError(
                "Could not create paste keyboard events. "
                "Check Accessibility permissions."
            )

        key_down.setFlags(kCGEventFlagMaskCommand)
        key_up.setFlags(kCGEventFlagMaskCommand)

        CGEventPost(kCGHIDEventTap, key_down)
        CGEventPost(kCGHIDEventTap, key_up)

    def _safe_attribute(self, element: Any, attribute: str) -> str:
        if element is None:
            return ""

        from HIServices import (  # type: ignore[import-not-found]
            AXUIElementCopyAttributeValue,
        )

        try:
            value = AXUIElementCopyAttributeValue(element, attribute, None)
        except Exception:
            return ""

        return str(value) if value is not None else ""
