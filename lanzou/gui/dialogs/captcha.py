import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QLineEdit, QDialog, QLabel, QDialogButtonBox, QVBoxLayout)

from lanzou.gui.utils import others_style, btn_style

class CaptchaDialog(QDialog):
    captcha = pyqtSignal(object)

    def __init__(self, parent=None):
        super(CaptchaDialog, self).__init__(parent)
        self.img_path = os.getcwd() + os.sep + 'captcha.png'
        self.initUI()
        self.setStyleSheet(others_style)

    def show_img(self):
        self.captcha_pixmap = QPixmap(self.img_path)
        self.captcha_lb.setPixmap(self.captcha_pixmap)

    def handle(self, img_data):
        with open(self.img_path, 'wb') as f:
            f.write(img_data)
            f.flush()
        self.show_img()

    def on_ok(self):
        captcha = self.code.text()
        self.captcha.emit(captcha)
        if os.path.isfile(self.img_path):
            os.remove(self.img_path)

    def initUI(self):
        self.setWindowTitle("请输入下载验证码")

        self.captcha_lb = QLabel()
        self.captcha_pixmap = QPixmap(self.img_path)
        self.captcha_lb.setPixmap(self.captcha_pixmap)

        self.code = QLineEdit()
        self.code.setPlaceholderText("在此输入验证码")

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Reset|QDialogButtonBox.Ok|QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Reset).setText("显示图片")
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.setStyleSheet(btn_style)
        self.buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.show_img)
        self.buttonBox.accepted.connect(self.on_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        vbox = QVBoxLayout()
        vbox.addWidget(self.captcha_lb)
        vbox.addStretch(1)
        vbox.addWidget(self.code)
        vbox.addStretch(1)
        vbox.addWidget(self.buttonBox)
        self.setLayout(vbox)
        self.setMinimumWidth(260)
