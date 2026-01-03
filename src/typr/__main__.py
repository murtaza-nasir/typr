"""Entry point for Typr application."""

import sys

from PyQt6.QtWidgets import QApplication

from typr.app import TyprApp


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Typr")
    app.setOrganizationName("Typr")

    typr = TyprApp()
    typr.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
