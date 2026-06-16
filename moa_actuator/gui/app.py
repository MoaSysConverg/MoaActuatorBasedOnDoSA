"""PyQt6 application entry point."""

from __future__ import annotations

import sys


def launch():
    """Launch the MoA Actuator GUI application."""
    from PyQt6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("MoA Actuator")
    app.setOrganizationName("MoaSysConverg")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
