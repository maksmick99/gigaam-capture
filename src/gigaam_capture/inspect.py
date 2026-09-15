from __future__ import annotations

import json
import platform as platform_module
import sys
from dataclasses import dataclass, field
from typing import Any

from . import __version__
from .config import build_app_paths, ensure_app_dirs
from .log import configure_logging, get_logger
from .models import TARGET_ACTIVE_TEXT_FIELD
from .platform import target_capabilities
from .platform.automation import create_active_app_automation

logger = get_logger("inspect")

__all__ = ["InspectionReport", "collect_report", "main", "render_report"]


@dataclass(slots=True)
class InspectionReport:
    version: str
    platform_name: str
    python_version: str
    targets: list[dict[str, Any]] = field(default_factory=list)
    active_target: str | None = None
    active_target_source: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "platform": self.platform_name,
            "python": self.python_version,
            "targets": self.targets,
            "active_target": self.active_target,
            "active_target_source": self.active_target_source,
            "error": self.error,
        }


def collect_report(*, inspect_active_target: bool = True) -> InspectionReport:
    """Collect platform capabilities and, optionally, the current target."""
    report = InspectionReport(
        version=__version__,
        platform_name=sys.platform,
        python_version=platform_module.python_version(),
        targets=[
            {
                "mode": capability.mode,
                "available": capability.available,
                "backend": capability.backend,
                "reason": capability.reason,
            }
            for capability in target_capabilities()
        ],
    )

    if not inspect_active_target:
        return report

    automation = create_active_app_automation()
    source = getattr(automation, "uses_ui_automation", None)
    if source is not None:
        report.active_target_source = (
            "UI Automation + Win32" if source else "Win32 window classes only"
        )

    try:
        report.active_target = automation.describe_target()
    except Exception as exc:  # noqa: BLE001 - diagnostics must never raise
        report.error = str(exc)
        logger.warning("Active target inspection failed: %s", exc)

    return report


def render_report(report: InspectionReport, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.as_dict(), indent=2, ensure_ascii=False)

    lines = [
        f"gigaam-capture {report.version}",
        f"platform: {report.platform_name} (Python {report.python_version})",
        "",
        "output targets:",
    ]
    for target in report.targets:
        status = "available" if target["available"] else "unavailable"
        lines.append(f"  - {target['mode']}: {status} ({target['backend']})")
        if target["reason"]:
            lines.append(f"      reason: {target['reason']}")

    lines.extend(["", "active target:"])
    if report.active_target_source:
        lines.append(f"  inspector: {report.active_target_source}")
    if report.error is not None:
        lines.append(f"  error: {report.error}")
    elif report.active_target:
        lines.append(f"  {report.active_target}")
    else:
        lines.append("  not inspected")

    lines.extend(
        [
            "",
            f"clipboard mode needs no further permissions; "
            f"{TARGET_ACTIVE_TEXT_FIELD} requires the platform backend above.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in arguments
    skip_active = "--no-active-target" in arguments

    paths = build_app_paths()
    ensure_app_dirs(paths)
    configure_logging(paths.log_path)

    report = collect_report(inspect_active_target=not skip_active)
    print(render_report(report, as_json=as_json))

    if report.error is not None:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
