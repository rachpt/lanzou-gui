from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QLineEdit, QDialog, QLabel, QFormLayout,
                             QDialogButtonBox, QVBoxLayout)

from lanzou.gui.qss import dialog_qss_style
from lanzou.gui.others import AutoResizingTextEdit
from lanzou.debug import SRC_DIR


class InfoDialog(QDialog):
    """文件信息对话框"""
    get_dl_link = pyqtSignal(str, str)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.infos = None
        self._short_link_flag = True  # 防止多次重试
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def update_ui(self):
        self.tx_dl_link.setPlaceholderText("单击获取")
        self.tx_name.setText(self.infos.name)
        if self.infos.is_file:
            self.setWindowTitle("文件信息")
            self.lb_name.setText("文件名：")
            self.lb_desc.setText("文件描述：")
            self.tx_dl_link.setText("")  # 清空旧的信息
            self.lb_dl_link.setVisible(True)
            self.tx_dl_link.setVisible(True)
        else:
            self.setWindowTitle("文件夹信息")
            self.lb_name.setText("文件夹名：")
            self.lb_desc.setText("文件夹描述：")
            self.lb_dl_link.setVisible(False)
            self.tx_dl_link.setVisible(False)

        if self.infos.size:
            self.tx_size.setText(self.infos.size)
            self.lb_size.setVisible(True)
            self.tx_size.setVisible(True)
        else:
            self.tx_size.setVisible(False)
            self.lb_size.setVisible(False)

        if self.infos.time:
            self.lb_time.setVisible(True)
            self.tx_time.setVisible(True)
            self.tx_time.setText(self.infos.time)
        else:
            self.lb_time.setVisible(False)
            self.tx_time.setVisible(False)

        if self.infos.downs:
            self.lb_dl_count.setVisible(True)
            self.tx_dl_count.setVisible(True)
            self.tx_dl_count.setText(str(self.infos.downs))
        else:
            self.tx_dl_count.setVisible(False)
            self.lb_dl_count.setVisible(False)

        if self.infos.pwd:
            self.tx_pwd.setText(self.infos.pwd)
            self.tx_pwd.setPlaceholderText("")
        else:
            self.tx_pwd.setText("")
            self.tx_pwd.setPlaceholderText("无")

        if self.infos.desc:
            self.tx_desc.setText(self.infos.desc)
            self.tx_desc.setPlaceholderText("")
        else:
            self.tx_desc.setText("")
            self.tx_desc.setPlaceholderText("无")

        self.tx_share_url.setText(self.infos.url)
        self.adjustSize()

    def set_values(self, infos):
        self.infos = infos
        self.update_ui()

    def set_dl_link_tx(self, text):
        self.tx_dl_link.setText(text)
        self.adjustSize()

    def call_get_dl_link(self):
        url = self.tx_share_url.text()
        pwd = self.tx_pwd.text()
        self.get_dl_link.emit(url, pwd)
        self.tx_dl_link.setPlaceholderText("后台获取中，请稍候！")

    def call_get_short_url(self):
        if self._short_link_flag:
            self._short_link_flag = False
            self.tx_short.setPlaceholderText("后台获取中，请稍候！")
            url = self.tx_share_url.text()
            from lanzou.api.extra import get_short_url

            short_url = get_short_url(url)
            if short_url:
                self.tx_short.setText(short_url)
                self.tx_short.setPlaceholderText("")
                self._short_link_flag = True
            else:
                self.tx_short.setText("")
                self.tx_short.setPlaceholderText("生成失败！api 可能已经失效")

    def clean(self):
        self._short_link_flag = True
        self.tx_short.setText("")
        self.tx_short.setPlaceholderText("单击获取")

    def initUI(self):
        self.setWindowIcon(QIcon(SRC_DIR + "share.ico"))
        self.setWindowTitle("文件信息")
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.rejected.connect(self.clean)
        self.buttonBox.rejected.connect(self.closed.emit)

        self.logo = QLabel()
        self.logo.setPixmap(QPixmap(SRC_DIR + "q9.gif"))
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("background-color:rgb(255,204,51);")

        self.lb_name = QLabel()
        self.lb_name.setText("文件名：")
        self.tx_name = AutoResizingTextEdit()
        self.tx_name.setReadOnly(True)
        self.tx_name.setMinimumLines(1)

        self.lb_size = QLabel()
        self.lb_size.setText("文件大小：")
        self.tx_size = QLabel()

        self.lb_time = QLabel()
        self.lb_time.setText("上传时间：")
        self.tx_time = QLabel()

        self.lb_dl_count = QLabel()
        self.lb_dl_count.setText("下载次数：")
        self.tx_dl_count = QLabel()

        self.lb_share_url = QLabel()
        self.lb_share_url.setText("分享链接：")
        self.tx_share_url = QLineEdit()
        self.tx_share_url.setReadOnly(True)

        self.lb_pwd = QLabel()
        self.lb_pwd.setText("提取码：")
        self.tx_pwd = QLineEdit()
        self.tx_pwd.setReadOnly(True)

        self.lb_short = QLabel()
        self.lb_short.setText("短链接：")
        self.tx_short = AutoResizingTextEdit(self)
        self.tx_short.setPlaceholderText("单击获取")
        self.tx_short.clicked.connect(self.call_get_short_url)
        self.tx_short.setReadOnly(True)
        self.tx_short.setMinimumLines(1)

        self.lb_desc = QLabel()
        self.lb_desc.setText("文件描述：")
        self.tx_desc = AutoResizingTextEdit()
        self.tx_desc.setReadOnly(True)
        self.tx_desc.setMinimumLines(1)

        self.lb_dl_link = QLabel()
        self.lb_dl_link.setText("下载直链：")
        self.tx_dl_link = AutoResizingTextEdit(self)
        self.tx_dl_link.setPlaceholderText("单击获取")
        self.tx_dl_link.clicked.connect(self.call_get_dl_link)
        self.tx_dl_link.setReadOnly(True)
        self.tx_dl_link.setMinimumLines(1)

        vbox = QVBoxLayout()
        vbox.addWidget(self.logo)
        vbox.addStretch(1)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow(self.lb_name, self.tx_name)
        form.addRow(self.lb_size, self.tx_size)
        form.addRow(self.lb_time, self.tx_time)
        form.addRow(self.lb_dl_count, self.tx_dl_count)
        form.addRow(self.lb_share_url, self.tx_share_url)
        form.addRow(self.lb_pwd, self.tx_pwd)
        form.addRow(self.lb_short, self.tx_short)
        form.addRow(self.lb_desc, self.tx_desc)
        form.addRow(self.lb_dl_link, self.tx_dl_link)
        vbox.addLayout(form)
        vbox.addStretch(1)
        vbox.addWidget(self.buttonBox)

        self.setLayout(vbox)
        self.setMinimumWidth(500)
