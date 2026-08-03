#!/usr/bin/env python3
"""
main.py
-------
Entry point for i3x11wpl. Wires together Config, WallpaperManager and
the UI, then runs the Qt event loop. Launch this from an i3 keybinding.
"""
import signal
import sys

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QApplication

from config import Config, THUMB_DIR
from wallpaper_manager import WallpaperManager
from ui import WallpaperPicker


def main():
    # Qt's C++ event loop swallows SIGINT by default, so Ctrl+C in the
    # terminal does nothing. Restoring the default handler lets Ctrl+C
    # kill the process immediately, same as any normal CLI program.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    config = Config()
    manager = WallpaperManager(
        wallpaper_dir=config.wallpaper_dir,
        thumb_dir=THUMB_DIR,
        thumb_size=config.thumb_size,
    )

    picker = WallpaperPicker(config, manager)
    picker.show()
    picker.raise_()
    picker.activateWindow()

    exit_code = app.exec()

    # Escape/close can happen while a thumbnail worker is mid-run; give it
    # a moment to finish instead of tearing the process down underneath
    # it. Queued-but-not-started jobs were already dropped in _quit().
    QThreadPool.globalInstance().waitForDone(2000)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
