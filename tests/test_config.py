from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from gigaam_capture.config import SettingsStore, build_app_paths, ensure_app_dirs
from gigaam_capture.models import AppSettings
from gigaam_capture.output_targets import (
    ActiveTextFieldTarget,
    ClipboardTarget,
    create_output_target,
)
from gigaam_capture.platform.automation import (
    ActiveTargetInfo,
    AutomationPermissionError,
    MacOSPasteAutomation,
)
from gigaam_capture.services.recording import RecordingResult
from gigaam_capture.ui.tray import AppController, TrayApplication


def test_settings_roundtrip(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)

    store = SettingsStore(paths)
    expected = AppSettings(hotkey="<ctrl>+<shift>+r", model_name="v3_ctc")
    store.save(expected)

    actual = store.load()
    assert actual.hotkey == expected.hotkey
    assert actual.model_name == expected.model_name


def test_controller_enters_transcribing_without_blocking(tmp_path: Path):
    app = QCoreApplication.instance() or QCoreApplication([])
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    settings = AppSettings()

    class FakeRecording:
        is_recording = True

        def stop(self):
            audio_path = paths.recordings_dir / "sample.wav"
            audio_path.write_bytes(b"wav")
            return RecordingResult(audio_path=audio_path, duration_seconds=1.25)

    controller = AppController(paths, settings, recording_service=FakeRecording())
    states = []
    launched = []

    controller.state_changed.connect(states.append)
    controller._launch_transcription = lambda result: launched.append(result)  # type: ignore[method-assign]

    controller.toggle_capture()
    app.processEvents()

    assert states[-1] == "transcribing"
    assert len(launched) == 1


def test_controller_updates_service_settings(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    settings = AppSettings(model_name="v3_e2e_rnnt", hotkey="<cmd>+<shift>+r")

    class FakeRecording:
        is_recording = False

        def __init__(self):
            self.settings = None

        def update_settings(self, new_settings):
            self.settings = new_settings

        def start(self):
            raise AssertionError("not used")

    class FakeTranscription:
        def __init__(self):
            self.model_name = "v3_e2e_rnnt"

        def update_settings(self, model_name):
            self.model_name = model_name

    recording = FakeRecording()
    transcription = FakeTranscription()
    controller = AppController(
        paths,
        settings,
        recording_service=recording,
        transcription_service=transcription,
    )

    updated = AppSettings(model_name="v3_ctc", hotkey="<ctrl>+<shift>+r")
    controller.update_settings(updated)

    assert recording.settings == updated
    assert transcription.model_name == "v3_ctc"


def test_create_output_target_clipboard():
    target = create_output_target("clipboard")
    assert isinstance(target, ClipboardTarget)


def test_create_output_target_active_text_field_uses_platform_factory():
    fake_automation = object()
    with patch(
        "gigaam_capture.output_targets.is_target_supported", return_value=True
    ), patch(
        "gigaam_capture.output_targets.create_active_app_automation",
        return_value=fake_automation,
    ):
        target = create_output_target("active-text-field")

    assert isinstance(target, ActiveTextFieldTarget)
    assert target.automation is fake_automation


def test_controller_switches_output_target_with_settings(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    settings = AppSettings(target_mode="clipboard")

    class FakeRecording:
        is_recording = False

        def update_settings(self, new_settings):
            self.settings = new_settings

        def start(self):
            raise AssertionError("not used")

    class FakeTranscription:
        model_name = "v3_e2e_rnnt"

        def update_settings(self, model_name):
            self.model_name = model_name

    class FakeTarget:
        name = "active-text-field"

        def deliver(self, text):
            raise AssertionError("not used")

    with patch(
        "gigaam_capture.ui.tray.create_output_target", return_value=FakeTarget()
    ):
        controller = AppController(
            paths,
            settings,
            recording_service=FakeRecording(),
            transcription_service=FakeTranscription(),
            output_target=ClipboardTarget(),
        )
        controller.update_settings(AppSettings(target_mode="active-text-field"))

    assert controller.settings.target_mode == "active-text-field"


def test_macos_paste_automation_raises_clear_permission_error_without_access():
    automation = MacOSPasteAutomation()

    with patch.object(automation, "has_accessibility_access", return_value=False):
        try:
            automation.ensure_accessibility_access()
        except AutomationPermissionError as exc:
            assert "Accessibility" in str(exc)
        else:
            raise AssertionError("Expected AutomationPermissionError")


def test_macos_paste_automation_accepts_when_access_is_available():
    automation = MacOSPasteAutomation()

    with patch.object(automation, "has_accessibility_access", return_value=True):
        automation.ensure_accessibility_access()


def test_macos_paste_automation_rejects_non_text_roles():
    automation = MacOSPasteAutomation()

    with patch.object(
        automation,
        "get_active_target_info",
        return_value=ActiveTargetInfo(
            app_name="Telegram",
            bundle_id="ru.keepcoder.Telegram",
            window_title="Chat",
            role="AXButton",
        ),
    ):
        try:
            automation.validate_target()
        except RuntimeError as exc:
            assert "does not look like a text input" in str(exc)
            assert "Telegram message composer" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError for non-text role")


def test_macos_paste_automation_accepts_text_like_role():
    automation = MacOSPasteAutomation()
    info = ActiveTargetInfo(
        app_name="Telegram",
        bundle_id="ru.keepcoder.Telegram",
        window_title="Chat",
        role="AXTextArea",
    )

    with patch.object(automation, "get_active_target_info", return_value=info):
        assert automation.validate_target() == info


def test_macos_paste_automation_rejects_webarea_for_unknown_bundle():
    automation = MacOSPasteAutomation()

    with patch.object(
        automation,
        "get_active_target_info",
        return_value=ActiveTargetInfo(
            app_name="Unknown App",
            bundle_id="com.example.unknown",
            window_title="Composer",
            role="AXWebArea",
        ),
    ):
        try:
            automation.validate_target()
        except RuntimeError as exc:
            assert "known messenger/browser apps" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError for unknown AXWebArea target")


def test_macos_paste_automation_accepts_webarea_for_telegram_bundle():
    automation = MacOSPasteAutomation()
    info = ActiveTargetInfo(
        app_name="Telegram",
        bundle_id="ru.keepcoder.Telegram",
        window_title="Chat",
        role="AXWebArea",
    )

    with patch.object(automation, "get_active_target_info", return_value=info):
        assert automation.validate_target() == info


def test_macos_paste_automation_accepts_webarea_for_browser_bundle():
    automation = MacOSPasteAutomation()
    info = ActiveTargetInfo(
        app_name="Google Chrome",
        bundle_id="com.google.Chrome",
        window_title="WhatsApp Web",
        role="AXWebArea",
    )

    with patch.object(automation, "get_active_target_info", return_value=info):
        assert automation.validate_target() == info


def test_macos_paste_automation_describe_target_includes_profile_for_telegram():
    automation = MacOSPasteAutomation()
    info = ActiveTargetInfo(
        app_name="Telegram",
        bundle_id="ru.keepcoder.Telegram",
        window_title="Chat with Alice",
        role="AXWebArea",
    )

    with patch.object(automation, "get_active_target_info", return_value=info):
        assert (
            automation.describe_target()
            == "Telegram | Chat with Alice | AXWebArea | Profile: Telegram Desktop"
        )


def test_macos_paste_automation_rejects_whatsapp_non_text_role_with_focus_hint():
    automation = MacOSPasteAutomation()

    with patch.object(
        automation,
        "get_active_target_info",
        return_value=ActiveTargetInfo(
            app_name="WhatsApp",
            bundle_id="net.whatsapp.WhatsApp",
            window_title="Team Chat",
            role="AXButton",
        ),
    ):
        try:
            automation.validate_target()
        except RuntimeError as exc:
            assert "WhatsApp message composer" in str(exc)
            assert "Profile: WhatsApp Desktop" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError for invalid WhatsApp role")


def test_controller_records_described_output_target(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    settings = AppSettings(target_mode="active-text-field")

    class FakeRecording:
        is_recording = False

        def update_settings(self, new_settings):
            self.settings = new_settings

        def start(self):
            raise AssertionError("not used")

    class FakeTranscription:
        model_name = "v3_e2e_rnnt"

        def update_settings(self, model_name):
            self.model_name = model_name

    class FakeHistory:
        def __init__(self):
            self.record = None

        def append(self, record):
            self.record = record

    class FakeTarget:
        name = "active-text-field"

        def deliver(self, text):
            self.delivered = text

        def describe_target(self):
            return "Telegram | Chat with Alice | AXTextArea"

    history = FakeHistory()
    target = FakeTarget()
    controller = AppController(
        paths,
        settings,
        recording_service=FakeRecording(),
        transcription_service=FakeTranscription(),
        history_store=history,
        output_target=target,
    )
    controller._pending_recording = RecordingResult(
        audio_path=paths.recordings_dir / "sample.wav",
        duration_seconds=2.5,
    )

    controller._on_transcription_completed("hello")

    assert history.record is not None
    assert history.record.target_hint == "Telegram | Chat with Alice | AXTextArea"


def test_controller_inspects_clipboard_target_without_automation(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    controller = AppController(
        paths,
        AppSettings(target_mode="clipboard"),
        output_target=ClipboardTarget(),
    )

    assert (
        controller.inspect_active_target_context()
        == "Clipboard target selected; active app inspection is not required"
    )


def test_controller_inspects_active_target_context(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)

    class FakeTarget:
        name = "active-text-field"

        def deliver(self, text):
            raise AssertionError("not used")

        def describe_target(self):
            return "Telegram | Chat with Alice | AXTextArea"

    controller = AppController(
        paths,
        AppSettings(target_mode="active-text-field"),
        output_target=FakeTarget(),
    )

    assert (
        controller.inspect_active_target_context()
        == "Telegram | Chat with Alice | AXTextArea"
    )


def test_tray_inspect_active_target_reports_success(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)

    class FakeController:
        def inspect_active_target_context(self):
            return "Telegram | Chat with Alice | AXTextArea"

    class FakeTray:
        def __init__(self):
            self.calls = []

        def showMessage(self, title, message, icon, timeout):
            self.calls.append((title, message, icon, timeout))

    tray = TrayApplication.__new__(TrayApplication)
    tray._controller = FakeController()
    tray._tray = FakeTray()

    TrayApplication._inspect_active_target(tray)

    assert tray._tray.calls
    assert tray._tray.calls[-1][0] == "GigaAM Capture"
    assert tray._tray.calls[-1][1] == "Telegram | Chat with Alice | AXTextArea"


def test_tray_inspect_active_target_reports_failure(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)

    class FakeController:
        def inspect_active_target_context(self):
            raise RuntimeError("Accessibility permission is missing")

    class FakeTray:
        def __init__(self):
            self.calls = []

        def showMessage(self, title, message, icon, timeout):
            self.calls.append((title, message, icon, timeout))

    tray = TrayApplication.__new__(TrayApplication)
    tray._controller = FakeController()
    tray._tray = FakeTray()

    TrayApplication._inspect_active_target(tray)

    assert tray._tray.calls
    assert tray._tray.calls[-1][1] == "Accessibility permission is missing"


def test_tray_status_reflects_hotkey_and_target(tmp_path: Path):
    paths = build_app_paths(tmp_path)
    ensure_app_dirs(paths)
    settings = AppSettings(hotkey="<ctrl>+<shift>+r", target_mode="active-text-field")
    controller = AppController(paths, settings, output_target=ClipboardTarget())

    class FakeAction:
        def __init__(self):
            self._text = ""

        def setText(self, text: str):
            self._text = text

        def text(self) -> str:
            return self._text

    tray = TrayApplication.__new__(TrayApplication)
    tray._controller = controller
    tray._status_action = FakeAction()

    TrayApplication._refresh_status_action(tray)

    assert "<ctrl>+<shift>+r" in tray._status_action.text()
    assert "Active text field" in tray._status_action.text()
