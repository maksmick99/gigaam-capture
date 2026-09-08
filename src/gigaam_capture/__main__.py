from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .config import SettingsStore, build_app_paths, ensure_app_dirs
from .ui.tray import TrayApplication


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    paths = build_app_paths()
    ensure_app_dirs(paths)
    settings_store = SettingsStore(paths)
    settings = settings_store.load()

    tray = TrayApplication(app, paths, settings, settings_store)
    tray.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
