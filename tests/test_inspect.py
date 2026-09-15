from __future__ import annotations

from unittest.mock import patch

from gigaam_capture.inspect import collect_report, main, render_report
from gigaam_capture.platform import TargetCapability


class FakeAutomation:
    uses_ui_automation = True

    def __init__(self, *, result: str | None = None, error: Exception | None = None):
        self._result = result
        self._error = error

    def describe_target(self) -> str:
        if self._error is not None:
            raise self._error
        return self._result or ""


def _capabilities(*, windows: bool):
    return [
        TargetCapability("clipboard", True, "Qt clipboard"),
        TargetCapability(
            "active-text-field",
            windows,
            "UI Automation + Win32" if windows else "not implemented",
            None if windows else "not implemented on this platform",
        ),
    ]


def test_report_lists_target_capabilities():
    with patch(
        "gigaam_capture.inspect.target_capabilities",
        return_value=_capabilities(windows=True),
    ):
        report = collect_report(inspect_active_target=False)

    assert report.platform_name
    modes = {item["mode"]: item for item in report.targets}
    assert modes["clipboard"]["available"] is True
    assert modes["active-text-field"]["available"] is True


def test_report_includes_active_target_and_inspector_source():
    with patch(
        "gigaam_capture.inspect.create_active_app_automation",
        return_value=FakeAutomation(result="Code.exe | editor | Edit"),
    ):
        report = collect_report()

    assert report.active_target == "Code.exe | editor | Edit"
    assert report.error is None


def test_report_captures_inspection_errors_without_raising():
    with patch(
        "gigaam_capture.inspect.create_active_app_automation",
        return_value=FakeAutomation(error=RuntimeError("Accessibility missing")),
    ):
        report = collect_report()

    assert report.error == "Accessibility missing"
    assert report.active_target is None


def test_render_report_marks_unavailable_targets_with_reason():
    with patch(
        "gigaam_capture.inspect.target_capabilities",
        return_value=_capabilities(windows=False),
    ):
        report = collect_report(inspect_active_target=False)

    text = render_report(report)

    assert "active-text-field: unavailable" in text
    assert "not implemented on this platform" in text


def _tmp_paths(tmp_path):
    from gigaam_capture.config import build_app_paths

    return build_app_paths(tmp_path)


def test_main_reports_inspection_failure_with_exit_code_one(tmp_path):
    with patch(
        "gigaam_capture.inspect.build_app_paths", return_value=_tmp_paths(tmp_path)
    ), patch(
        "gigaam_capture.inspect.create_active_app_automation",
        return_value=FakeAutomation(error=RuntimeError("Accessibility missing")),
    ), patch("builtins.print") as printer:
        exit_code = main([])

    assert exit_code == 1
    assert printer.called


def test_main_prints_json_report(tmp_path):
    with patch(
        "gigaam_capture.inspect.build_app_paths", return_value=_tmp_paths(tmp_path)
    ), patch(
        "gigaam_capture.inspect.create_active_app_automation",
        return_value=FakeAutomation(result="Code.exe | editor | Edit"),
    ), patch("builtins.print") as printer:
        exit_code = main(["--json"])

    assert exit_code == 0
    assert '"active_target"' in printer.call_args.args[0]
