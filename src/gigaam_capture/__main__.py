from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import __version__
from .config import APP_NAME, SettingsStore, build_app_paths, ensure_app_dirs
from .log import configure_logging, get_logger
from .output_targets import ensure_supported_target_mode
from .ui.tray import TrayApplication

logger = get_logger("main")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    paths = build_app_paths()
    ensure_app_dirs(paths)
    configure_logging(paths.log_path)
    logger.info("GigaAM Capture %s starting on %s", __version__, sys.platform)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.warning("No system tray available; the tray icon may not be visible")

    settings_store = SettingsStore(paths)
    settings = settings_store.load()
    settings, notice = ensure_supported_target_mode(settings)
    if notice is not None:
        logger.warning("%s", notice)
        try:
            settings_store.save(settings)
        except OSError as exc:
            logger.warning("Could not persist the target fallback: %s", exc)

    tray = TrayApplication(app, paths, settings, settings_store, startup_notice=notice)
    tray.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
