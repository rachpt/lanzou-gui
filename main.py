#!/usr/bin/env python3

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from lanzou.gui.gui import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("./lanzou/gui/src/lanzou_logo2.png"))
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
