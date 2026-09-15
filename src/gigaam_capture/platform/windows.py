from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Protocol

from PySide6.QtGui import QGuiApplication

from gigaam_capture.log import get_logger

from .targets import (
    ActiveTargetInfo,
    AppProfile,
    AutomationPermissionError,
    describe_with_profile,
    focus_hint_for,
)
from .windows_uia import UiaFocusInspector, create_focus_inspector

logger = get_logger("platform.windows")

# Sentinel meaning "detect the UI Automation inspector automatically".
_AUTO_DETECT_INSPECTOR = object()

# Win32 window classes that are known editable text surfaces (lowercase).
_GENERIC_EDITABLE_CLASSES = frozenset(
    {
        "edit",
        "richedit20a",
        "richedit20w",
        "richedit50w",
        "richedit60w",
        "scintilla",
        "internet explorer_server",
        "textinputhost",
    }
)

# UI Automation control types that accept typed text.
_EDITABLE_CONTROL_TYPES = frozenset({"Edit", "Document", "ComboBox"})

# Shell classes used by Chromium, Electron and Gecko surfaces. They are only
# accepted together with a recognized application profile, because a browser
# window can just as easily hold a button or a page background.
_SHELL_CLASSES = frozenset(
    {
        "chrome_widgetwin_0",
        "chrome_widgetwin_1",
        "chrome_renderwidgethosthwnd",
        "mozillawindowclass",
    }
)

_QT_SHELL_PREFIXES = ("qt4", "qt5", "qt6")

_TELEGRAM_HINT = "Focus the Telegram message composer before starting capture."
_WHATSAPP_HINT = "Focus the WhatsApp message composer before starting capture."
_BROWSER_HINT = (
    "Focus the chat input inside the browser window before starting capture."
)


def _messenger_profile(
    display_name: str,
    focus_hint: str,
    *,
    allows_qt_shells: bool = False,
) -> AppProfile:
    return AppProfile(
        display_name=display_name,
        allowed_classes=_SHELL_CLASSES,
        focus_hint=focus_hint,
        allows_qt_shells=allows_qt_shells,
    )


def _browser_profile(display_name: str) -> AppProfile:
    return AppProfile(
        display_name=display_name,
        allowed_classes=_SHELL_CLASSES,
        focus_hint=_BROWSER_HINT,
    )


_PROCESS_PROFILES = {
    "telegram.exe": _messenger_profile(
        "Telegram Desktop", _TELEGRAM_HINT, allows_qt_shells=True
    ),
    "whatsapp.exe": _messenger_profile("WhatsApp Desktop", _WHATSAPP_HINT),
    "discord.exe": _messenger_profile(
        "Discord",
        "Focus the Discord message box before starting capture.",
        allows_qt_shells=True,
    ),
    "slack.exe": _messenger_profile(
        "Slack", "Focus the Slack message box before starting capture."
    ),
    "chrome.exe": _browser_profile("Google Chrome"),
    "msedge.exe": _browser_profile("Microsoft Edge"),
    "brave.exe": _browser_profile("Brave"),
    "opera.exe": _browser_profile("Opera"),
    "chromium.exe": _browser_profile("Chromium"),
    "firefox.exe": _browser_profile("Firefox"),
}


class WindowsAutomationApi(Protocol):
    def foreground_window(self) -> int:
        ...

    def window_text(self, hwnd: int) -> str:
        ...

    def class_name(self, hwnd: int) -> str:
        ...

    def focused_window(self) -> int:
        ...

    def process_name(self, hwnd: int) -> str:
        ...


class _GuiThreadInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class Win32AutomationApi:
    """Thin ``ctypes`` wrapper over the Win32 calls the backend needs."""

    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

    def foreground_window(self) -> int:
        return int(self._user32.GetForegroundWindow() or 0)

    def window_text(self, hwnd: int) -> str:
        return self._window_string(self._user32.GetWindowTextW, hwnd)

    def class_name(self, hwnd: int) -> str:
        return self._window_string(self._user32.GetClassNameW, hwnd)

    def focused_window(self) -> int:
        hwnd = self.foreground_window()
        if not hwnd:
            return 0

        thread_id = self._user32.GetWindowThreadProcessId(hwnd, None)
        info = _GuiThreadInfo(cbSize=ctypes.sizeof(_GuiThreadInfo))
        if not self._user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            return 0
        return int(info.hwndFocus or 0)

    def process_name(self, hwnd: int) -> str:
        pid = wintypes.DWORD()
        if not self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)):
            return ""
        if not pid.value:
            return ""

        handle = self._kernel32.OpenProcess(
            self._PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not handle:
            return ""

        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buffer))
            written = self._kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)
            )
        finally:
            self._kernel32.CloseHandle(handle)

        if not written:
            return ""
        return Path(buffer.value).name

    def _window_string(self, function: Any, hwnd: int) -> str:
        buffer = ctypes.create_unicode_buffer(512)
        function(hwnd, buffer, len(buffer))
        return buffer.value


class WindowsPasteAutomation:
    """Active text-field backend for Windows.

    Focus validation uses UI Automation control types when the COM API is
    available, and falls back to a Win32 window-class allowlist together with
    per-application profiles otherwise.
    """

    def __init__(
        self,
        api: WindowsAutomationApi | None = None,
        focus_inspector: Any = _AUTO_DETECT_INSPECTOR,
    ) -> None:
        self._api = api or Win32AutomationApi()
        if focus_inspector is _AUTO_DETECT_INSPECTOR:
            self._inspector: UiaFocusInspector | None = create_focus_inspector()
        else:
            self._inspector = focus_inspector

    @property
    def uses_ui_automation(self) -> bool:
        return self._inspector is not None

    def get_active_target_info(self) -> ActiveTargetInfo:
        hwnd = self._api.foreground_window()
        if not hwnd:
            raise RuntimeError("Could not determine the foreground window")

        process_name = self._api.process_name(hwnd)
        focused_hwnd = self._api.focused_window() or hwnd
        info = ActiveTargetInfo(
            app_name=process_name or "Unknown app",
            window_title=self._api.window_text(hwnd),
            process_name=process_name,
            class_name=self._api.class_name(focused_hwnd),
        )

        profile = self._profile_for(info)
        if profile is not None:
            info.app_name = profile.display_name

        focus = self._inspect_focus()
        if focus is not None:
            if focus.control_type:
                info.control_type = focus.control_type
            if focus.class_name:
                info.class_name = focus.class_name
            info.automation_id = focus.automation_id

        return info

    def describe_target(self) -> str:
        info = self.get_active_target_info()
        return describe_with_profile(info, self._profile_for(info))

    def validate_target(self) -> ActiveTargetInfo:
        info = self.get_active_target_info()
        profile = self._profile_for(info)

        if info.control_type:
            if info.control_type in _EDITABLE_CONTROL_TYPES:
                return info
            raise RuntimeError(
                self._rejection_message(info, profile, source="ui-automation")
            )

        if self._class_is_editable(info.class_name, profile):
            return info

        raise RuntimeError(self._rejection_message(info, profile, source="win32"))

    def paste_text(self, text: str) -> None:
        if sys.platform != "win32":
            raise RuntimeError(
                "Windows active text-field automation is only available on win32"
            )

        self.validate_target()

        clipboard = QGuiApplication.clipboard()
        previous_text = clipboard.text()
        clipboard.setText(text)

        try:
            self._send_ctrl_v()
            time.sleep(0.12)
        finally:
            clipboard.setText(previous_text)

    def _inspect_focus(self):
        if self._inspector is None:
            return None
        try:
            return self._inspector.focused_element()
        except Exception as exc:
            logger.debug("UI Automation focus inspection failed: %s", exc)
            return None

    def _profile_for(self, info: ActiveTargetInfo) -> AppProfile | None:
        if not info.process_name:
            return None
        return _PROCESS_PROFILES.get(info.process_name.lower())

    def _class_is_editable(
        self, class_name: str, profile: AppProfile | None
    ) -> bool:
        if not class_name:
            return False

        lowered = class_name.lower()
        if lowered in _GENERIC_EDITABLE_CLASSES:
            return True
        if profile is None:
            return False
        if lowered in profile.allowed_classes:
            return True
        return profile.allows_qt_shells and lowered.startswith(_QT_SHELL_PREFIXES)

    def _rejection_message(
        self,
        info: ActiveTargetInfo,
        profile: AppProfile | None,
        *,
        source: str,
    ) -> str:
        if source == "ui-automation":
            extra = (
                " UI Automation reports the focused control as "
                f"{info.control_type or 'unknown'}; supported control types are "
                f"{', '.join(sorted(_EDITABLE_CONTROL_TYPES))}."
            )
        else:
            extra = (
                " UI Automation introspection is unavailable here, so only known "
                "editable control classes are accepted for this target."
            )

        return (
            "The currently focused control does not look like a text input. "
            f"Frontmost target: {describe_with_profile(info, profile)}. "
            f"{focus_hint_for(profile)}{extra}"
        )

    def _send_ctrl_v(self) -> None:
        from pynput.keyboard import Controller, Key

        keyboard = Controller()
        try:
            try:
                keyboard.press(Key.ctrl)
                keyboard.press("v")
                keyboard.release("v")
            except Exception as exc:
                raise AutomationPermissionError(
                    "Could not send Ctrl+V to the active window. Windows blocks "
                    "synthetic input from a non-elevated process when the target "
                    f"application runs as administrator ({exc})."
                ) from exc
        finally:
            try:
                keyboard.release(Key.ctrl)
            except Exception:
                logger.debug("Could not release the Ctrl key after paste")
