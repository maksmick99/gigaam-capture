from __future__ import annotations

from collections.abc import Callable

from pynput import keyboard

from gigaam_capture.log import get_logger

logger = get_logger("services.hotkeys")

MINIMUM_HOTKEY_KEYS = 2


def validate_hotkey(hotkey: str) -> str | None:
    """Return a human-readable problem description, or ``None`` when valid."""
    candidate = hotkey.strip()
    if not candidate:
        return "Hotkey must not be empty."

    try:
        keys = keyboard.HotKey.parse(candidate)
    except ValueError as exc:
        return (
            f"Unsupported key {exc} in hotkey {candidate!r}. "
            "Use pynput syntax such as <ctrl>+<alt>+r."
        )

    if len(keys) < MINIMUM_HOTKEY_KEYS:
        return "Hotkey must combine at least two keys, for example <ctrl>+<alt>+r."

    return None


class HotkeyService:
    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self._hotkey = hotkey
        self._callback = callback
        self._listener: keyboard.GlobalHotKeys | None = None

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def start(self) -> None:
        if self._listener is not None:
            return

        problem = validate_hotkey(self._hotkey)
        if problem is not None:
            raise ValueError(problem)

        listener = keyboard.GlobalHotKeys({self._hotkey: self._callback})
        listener.start()
        self._listener = listener
        logger.info("Global hotkey registered: %s", self._hotkey)

    def stop(self) -> None:
        if self._listener is None:
            return
        self._listener.stop()
        self._listener = None
        logger.info("Global hotkey released: %s", self._hotkey)
