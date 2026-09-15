from __future__ import annotations

from unittest.mock import patch

from gigaam_capture.models import default_hotkey
from gigaam_capture.services.hotkeys import HotkeyService, validate_hotkey


def test_default_hotkey_is_platform_aware():
    with patch("sys.platform", "darwin"):
        assert default_hotkey() == "<cmd>+<shift>+r"

    with patch("sys.platform", "win32"):
        assert default_hotkey() == "<ctrl>+<alt>+r"

    with patch("sys.platform", "linux"):
        assert default_hotkey() == "<ctrl>+<alt>+r"


def test_validate_hotkey_accepts_combination():
    assert validate_hotkey("<ctrl>+<alt>+r") is None


def test_validate_hotkey_rejects_empty_value():
    problem = validate_hotkey("   ")

    assert problem is not None
    assert "empty" in problem


def test_validate_hotkey_rejects_unknown_key():
    problem = validate_hotkey("<ctrl>+<boguskey>+r")

    assert problem is not None
    assert "Unsupported key" in problem


def test_validate_hotkey_rejects_single_key():
    problem = validate_hotkey("r")

    assert problem is not None
    assert "at least two keys" in problem


def test_hotkey_service_refuses_to_start_with_invalid_hotkey():
    calls: list[None] = []
    service = HotkeyService("<boguskey>+r", lambda: calls.append(None))

    try:
        service.start()
    except ValueError as exc:
        assert "Unsupported key" in str(exc)
    else:
        raise AssertionError("Expected ValueError for an invalid hotkey")

    assert calls == []
