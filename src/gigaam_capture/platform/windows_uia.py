from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gigaam_capture.log import get_logger

logger = get_logger("platform.windows_uia")

_UIA_TYPELIB = "UIAutomationCore.dll"


@dataclass(frozen=True, slots=True)
class UiaFocusInfo:
    control_type: str
    class_name: str
    name: str
    automation_id: str


class UiaFocusInspector:
    """Read the focused UI Automation element through COM."""

    def __init__(self) -> None:
        self._automation: Any = None
        self._control_type_names: dict[int, str] = {}

    def available(self) -> bool:
        return self._ensure_automation() is not None

    def focused_element(self) -> UiaFocusInfo | None:
        automation = self._ensure_automation()
        if automation is None:
            return None

        try:
            element = automation.GetFocusedElement()
        except Exception as exc:
            logger.debug("UI Automation focus lookup failed: %s", exc)
            return None

        if element is None:
            return None

        return UiaFocusInfo(
            control_type=self._control_type_name(element),
            class_name=self._attribute(element, "CurrentClassName"),
            name=self._attribute(element, "CurrentName"),
            automation_id=self._attribute(element, "CurrentAutomationId"),
        )

    def _ensure_automation(self) -> Any:
        if self._automation is not None:
            return self._automation

        try:
            import comtypes.client

            comtypes.client.GetModule(_UIA_TYPELIB)
            from comtypes.gen import UIAutomationClient as uia
        except Exception as exc:
            logger.info("UI Automation module is unavailable: %s", exc)
            return None

        try:
            automation = comtypes.client.CreateObject(
                uia.CUIAutomation, interface=uia.IUIAutomation
            )
        except Exception as exc:
            logger.info("UI Automation automation object is unavailable: %s", exc)
            return None

        self._automation = automation
        self._control_type_names = control_type_names(uia)
        logger.info("UI Automation focus inspection is available")
        return self._automation

    def _attribute(self, element: Any, name: str) -> str:
        try:
            value = getattr(element, name)
        except Exception:
            return ""
        return str(value) if value is not None else ""

    def _control_type_name(self, element: Any) -> str:
        try:
            type_id = int(element.CurrentControlType)
        except Exception:
            return ""
        return self._control_type_names.get(type_id, str(type_id))


def control_type_names(uia_module: Any) -> dict[int, str]:
    """Map numeric UI Automation control type ids to readable names."""
    names: dict[int, str] = {}
    prefix = "UIA_"
    suffix = "ControlTypeId"
    for attribute in dir(uia_module):
        if attribute.startswith(prefix) and attribute.endswith(suffix):
            try:
                value = int(getattr(uia_module, attribute))
            except (TypeError, ValueError):
                continue
            names[value] = attribute[len(prefix) : -len(suffix)]
    return names


def create_focus_inspector() -> UiaFocusInspector | None:
    inspector = UiaFocusInspector()
    if inspector.available():
        return inspector
    return None