import sys

from PySide6 import QtWidgets

from gui.qt_utils import apply_theme

from gui.app_window import AppWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)
    win = AppWindow()
    app.aboutToQuit.connect(win.shutdown)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
