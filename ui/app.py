"""Запуск интерфейса v0.4 на PySide6."""
from __future__ import annotations

import sys


def run() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from utils import APP_NAME, APP_VERSION, setup_logging

    from .animations import MOTION
    from .controller import AppController
    from .theme import app_stylesheet, font
    from .window import MainWindow

    setup_logging()

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(app_stylesheet())
    app.setFont(font(9))

    controller = AppController()
    MOTION.set_mode(controller.settings.get("animations", "full"))

    # Штатная рамка Windows по умолчанию: безрамочный режим ломал кнопки.
    window = MainWindow(controller, APP_VERSION,
                        classic="--frameless" not in sys.argv)
    window.show()
    return app.exec()
