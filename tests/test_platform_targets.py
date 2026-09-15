from __future__ import annotations

from unittest.mock import patch

from gigaam_capture.models import (
    TARGET_ACTIVE_TEXT_FIELD,
    TARGET_CLIPBOARD,
    AppSettings,
)
from gigaam_capture.output_targets import (
    ClipboardTarget,
    UnsupportedTargetError,
    create_output_target,
    ensure_supported_target_mode,
)
from gigaam_capture.platform import (
    active_text_field_backend,
    is_target_supported,
    supported_targets,
    target_capabilities,
    target_unavailable_reason,
)
from gigaam_capture.ui.tray import AppController


def test_clipboard_target_is_supported_everywhere():
    for platform_name in ("darwin", "win32", "linux"):
        with patch("sys.platform", platform_name):
            assert is_target_supported(TARGET_CLIPBOARD)
            assert TARGET_CLIPBOARD in supported_targets()


def test_active_text_field_reports_reason_when_backend_is_missing():
    with patch("sys.platform", "linux"):
        assert not is_target_supported(TARGET_ACTIVE_TEXT_FIELD)
        reason = target_unavailable_reason(TARGET_ACTIVE_TEXT_FIELD)

    assert reason is not None
    assert "not implemented" in reason


def test_active_text_field_is_available_on_macos():
    with patch("sys.platform", "darwin"):
        assert is_target_supported(TARGET_ACTIVE_TEXT_FIELD)
        assert target_unavailable_reason(TARGET_ACTIVE_TEXT_FIELD) is None
        assert active_text_field_backend() is not None


def test_target_capabilities_describe_each_mode():
    with patch("sys.platform", "linux"):
        capabilities = {item.mode: item for item in target_capabilities()}

    assert capabilities[TARGET_CLIPBOARD].available
    assert capabilities[TARGET_CLIPBOARD].backend == "Qt clipboard"
    assert not capabilities[TARGET_ACTIVE_TEXT_FIELD].available
    assert capabilities[TARGET_ACTIVE_TEXT_FIELD].backend == "not implemented"
    assert capabilities[TARGET_ACTIVE_TEXT_FIELD].reason


def test_create_output_target_rejects_unsupported_mode():
    with patch("sys.platform", "linux"):
        try:
            create_output_target(TARGET_ACTIVE_TEXT_FIELD)
        except UnsupportedTargetError as exc:
            assert "not implemented" in str(exc)
        else:
            raise AssertionError("Expected UnsupportedTargetError")


def test_create_output_target_rejects_unknown_mode():
    try:
        create_output_target("telepathy")
    except UnsupportedTargetError as exc:
        assert "telepathy" in str(exc)
    else:
        raise AssertionError("Expected UnsupportedTargetError")


def test_ensure_supported_target_mode_falls_back_with_notice():
    settings = AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD)

    with patch("sys.platform", "linux"):
        resolved, notice = ensure_supported_target_mode(settings)

    assert resolved.target_mode == TARGET_CLIPBOARD
    assert notice is not None
    assert "clipboard" in notice.lower()


def test_ensure_supported_target_mode_keeps_available_target():
    settings = AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD)

    with patch("sys.platform", "darwin"):
        resolved, notice = ensure_supported_target_mode(settings)

    assert resolved is settings
    assert notice is None


def test_controller_falls_back_to_clipboard_when_target_creation_fails(app_paths):
    settings = AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD)

    with patch(
        "gigaam_capture.ui.tray.create_output_target",
        side_effect=UnsupportedTargetError("not implemented here"),
    ):
        controller = AppController(app_paths, settings)

    assert controller.state == "idle"
    assert controller._output.name == TARGET_CLIPBOARD
    assert isinstance(controller._output, ClipboardTarget)


def test_controller_settings_update_is_rejected_without_mutating_state(app_paths):
    controller = AppController(
        app_paths,
        AppSettings(target_mode=TARGET_CLIPBOARD),
        output_target=ClipboardTarget(),
    )

    with patch(
        "gigaam_capture.ui.tray.create_output_target",
        side_effect=UnsupportedTargetError("not implemented here"),
    ):
        try:
            controller.update_settings(AppSettings(target_mode=TARGET_ACTIVE_TEXT_FIELD))
        except UnsupportedTargetError:
            pass
        else:
            raise AssertionError("Expected UnsupportedTargetError")

    assert controller.settings.target_mode == TARGET_CLIPBOARD
    assert controller._output.name == TARGET_CLIPBOARD
