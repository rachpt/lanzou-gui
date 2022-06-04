#!/usr/bin/env python3

import sys
from PyQt6.QtWidgets import QApplication

from lanzou.gui.gui import MainWindow, get_lanzou_logo


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(get_lanzou_logo())
    form = MainWindow()
    form.show()
    form.call_login_launcher()
    sys.exit(app.exec())
