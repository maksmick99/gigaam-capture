from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from gigaam_capture.platform.automation import (
    MacOSPasteAutomation,
    create_active_app_automation,
)
from gigaam_capture.platform.windows import Win32AutomationApi, WindowsPasteAutomation
from gigaam_capture.platform.windows_uia import UiaFocusInfo


class FakeWindowsApi:
    def __init__(
        self,
        *,
        hwnd: int = 100,
        focused: int = 101,
        process: str = "chrome.exe",
        class_name: str = "Chrome_WidgetWin_1",
        title: str = "Chat with Alice",
    ) -> None:
        self._hwnd = hwnd
        self._focused = focused
        self._process = process
        self._class_name = class_name
        self._title = title

    def foreground_window(self) -> int:
        return self._hwnd

    def window_text(self, hwnd: int) -> str:
        return self._title

    def class_name(self, hwnd: int) -> str:
        return self._class_name

    def focused_window(self) -> int:
        return self._focused

    def process_name(self, hwnd: int) -> str:
        return self._process


class FakeInspector:
    def __init__(self, info: UiaFocusInfo | None) -> None:
        self._info = info

    def available(self) -> bool:
        return True

    def focused_element(self) -> UiaFocusInfo | None:
        return self._info


def _automation(
    *,
    api: FakeWindowsApi,
    focus: UiaFocusInfo | None = None,
    with_inspector: bool = True,
) -> WindowsPasteAutomation:
    inspector = FakeInspector(focus) if with_inspector else None
    return WindowsPasteAutomation(api=api, focus_inspector=inspector)


def test_target_info_uses_profile_display_name():
    automation = _automation(
        api=FakeWindowsApi(process="Telegram.exe"),
        with_inspector=False,
    )

    info = automation.get_active_target_info()

    assert info.app_name == "Telegram Desktop"
    assert info.process_name == "Telegram.exe"
    assert info.window_title == "Chat with Alice"
    assert info.profile_key() == "telegram.exe"


def test_describe_target_includes_profile():
    automation = _automation(
        api=FakeWindowsApi(process="telegram.exe"),
        focus=UiaFocusInfo("Edit", "Chrome_WidgetWin_1", "", ""),
    )

    assert automation.describe_target() == (
        "Telegram Desktop | Chat with Alice | Edit | Profile: Telegram Desktop"
    )


def test_ui_automation_edit_control_is_accepted():
    automation = _automation(
        api=FakeWindowsApi(process="notepad.exe", class_name="Notepad"),
        focus=UiaFocusInfo("Edit", "Edit", "", "15"),
    )

    info = automation.validate_target()

    assert info.control_type == "Edit"
    assert info.automation_id == "15"


def test_ui_automation_document_control_is_accepted():
    automation = _automation(
        api=FakeWindowsApi(),
        focus=UiaFocusInfo("Document", "Chrome_RenderWidgetHostHWND", "", ""),
    )

    assert automation.validate_target().control_type == "Document"


def test_ui_automation_rejects_non_text_control():
    automation = _automation(
        api=FakeWindowsApi(process="code.exe", class_name="Chrome_WidgetWin_1"),
        focus=UiaFocusInfo("Pane", "View", "", ""),
    )

    with pytest.raises(RuntimeError) as excinfo:
        automation.validate_target()

    message = str(excinfo.value)
    assert "does not look like a text input" in message
    assert "reports the focused control as Pane" in message


def test_ui_automation_rejection_mentions_known_focus_hint():
    automation = _automation(
        api=FakeWindowsApi(process="whatsapp.exe"),
        focus=UiaFocusInfo("Button", "Chrome_WidgetWin_1", "", ""),
    )

    with pytest.raises(RuntimeError) as excinfo:
        automation.validate_target()

    assert "WhatsApp message composer" in str(excinfo.value)


def test_win32_fallback_accepts_known_edit_class():
    automation = _automation(
        api=FakeWindowsApi(process="notepad.exe", class_name="RichEdit50W"),
        with_inspector=False,
    )

    assert automation.validate_target().class_name == "RichEdit50W"


def test_win32_fallback_accepts_shell_class_for_known_messenger():
    automation = _automation(
        api=FakeWindowsApi(process="WhatsApp.exe", class_name="Chrome_WidgetWin_1"),
        with_inspector=False,
    )

    assert automation.validate_target().class_name == "Chrome_WidgetWin_1"


def test_win32_fallback_accepts_qt_shell_only_for_qt_profiles():
    telegram = _automation(
        api=FakeWindowsApi(process="Telegram.exe", class_name="Qt5152QWindowIcon"),
        with_inspector=False,
    )
    whatsapp = _automation(
        api=FakeWindowsApi(process="WhatsApp.exe", class_name="Qt5152QWindowIcon"),
        with_inspector=False,
    )

    assert telegram.validate_target().class_name == "Qt5152QWindowIcon"

    with pytest.raises(RuntimeError):
        whatsapp.validate_target()


def test_win32_fallback_rejects_unknown_class_for_unknown_process():
    automation = _automation(
        api=FakeWindowsApi(process="notepad.exe", class_name="Notepad"),
        with_inspector=False,
    )

    with pytest.raises(RuntimeError) as excinfo:
        automation.validate_target()

    message = str(excinfo.value)
    assert "does not look like a text input" in message
    assert "UI Automation introspection is unavailable" in message


def test_missing_foreground_window_is_reported():
    automation = _automation(api=FakeWindowsApi(hwnd=0))

    with pytest.raises(RuntimeError) as excinfo:
        automation.get_active_target_info()

    assert "foreground window" in str(excinfo.value)


def test_paste_requires_the_windows_platform():
    automation = _automation(api=FakeWindowsApi())

    with patch("sys.platform", "linux"):
        with pytest.raises(RuntimeError):
            automation.paste_text("hello")


def test_paste_validates_before_touching_the_clipboard():
    automation = _automation(
        api=FakeWindowsApi(),
        focus=UiaFocusInfo("Pane", "View", "", ""),
    )

    with patch("sys.platform", "win32"), patch(
        "gigaam_capture.platform.windows.QGuiApplication"
    ) as gui_application:
        with pytest.raises(RuntimeError):
            automation.paste_text("hello")

    gui_application.clipboard.assert_not_called()


def test_factory_returns_macos_backend_on_darwin():
    with patch("sys.platform", "darwin"):
        automation = create_active_app_automation()

    assert isinstance(automation, MacOSPasteAutomation)


def test_factory_returns_windows_backend_on_win32():
    with patch(
        "gigaam_capture.platform.windows.create_focus_inspector", return_value=None
    ), patch(
        "gigaam_capture.platform.windows.Win32AutomationApi",
        return_value=FakeWindowsApi(),
    ):
        with patch("sys.platform", "win32"):
            automation = create_active_app_automation()

    assert isinstance(automation, WindowsPasteAutomation)
    assert automation.uses_ui_automation is False


def test_factory_rejects_unsupported_platform():
    with patch("sys.platform", "linux"):
        with pytest.raises(NotImplementedError):
            create_active_app_automation()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 API is Windows only")
def test_win32_api_reads_the_foreground_window():
    api = Win32AutomationApi()

    hwnd = api.foreground_window()

    assert isinstance(hwnd, int)
    assert isinstance(api.process_name(hwnd), str)
    assert isinstance(api.class_name(hwnd), str)