import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QDialog, QLabel, QDialogButtonBox, QLineEdit, QCheckBox,
                             QHBoxLayout, QVBoxLayout, QFormLayout, QFileDialog)

from lanzou.gui.qss import dialog_qss_style
from lanzou.gui.others import MyLineEdit, AutoResizingTextEdit
from lanzou.debug import SRC_DIR


class SettingDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, parent=None):
        super(SettingDialog, self).__init__(parent)
        self._config = object
        self.download_threads = 3
        self.max_size = 100
        self.timeout = 5
        self.dl_path = None
        self.time_fmt = False
        self.to_tray = False
        self.watch_clipboard = False
        self.debug = False
        self.set_pwd = False
        self.set_desc = False
        self.upload_delay = 0
        self.allow_big_file = False
        self.upgrade = True
        self.pwd = ""
        self.desc = ""
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def open_dialog(self, config):
        """"打开前先更新一下显示界面"""
        self._config = config
        if self._config.name:
            self.setWindowTitle(f"设置 <{self._config.name}>")
        else:
            self.setWindowTitle("设置")
        self.cwd = self._config.path
        self.set_values()
        self.exec()

    def show_values(self):
        """控件显示值"""
        self.download_threads_var.setText(str(self.download_threads))
        self.max_size_var.setText(str(self.max_size))
        self.timeout_var.setText(str(self.timeout))
        self.dl_path_var.setText(str(self.dl_path))
        self.time_fmt_box.setChecked(self.time_fmt)
        self.to_tray_box.setChecked(self.to_tray)
        self.watch_clipboard_box.setChecked(self.watch_clipboard)
        self.debug_box.setChecked(self.debug)
        self.set_pwd_box.setChecked(self.set_pwd)
        self.set_pwd_var.setEnabled(self.set_pwd)
        self.set_pwd_var.setText(self.pwd)
        self.set_desc_box.setChecked(self.set_desc)
        self.set_desc_var.setEnabled(self.set_desc)
        self.set_desc_var.setText(self.desc)
        self.upload_delay_var.setText(str(self.upload_delay))
        self.big_file_box.setChecked(self.allow_big_file)
        self.big_file_box.setText(f"允许上传超过 {self.max_size}MB 的大文件")
        # self.big_file_box.setDisabled(True)  # 关闭允许上传大文件设置入口
        self.upgrade_box.setChecked(self.upgrade)

    def set_values(self, reset=False):
        """设置控件对应变量初始值"""
        settings = self._config.default_settings if reset else self._config.settings
        self.download_threads = settings["download_threads"]
        self.max_size = settings["max_size"]
        self.timeout = settings["timeout"]
        self.dl_path = settings["dl_path"]
        self.time_fmt = settings["time_fmt"]
        self.to_tray = settings["to_tray"]
        self.watch_clipboard = settings["watch_clipboard"]
        self.debug = settings["debug"]
        self.set_pwd = settings["set_pwd"]
        self.pwd = settings["pwd"]
        self.set_desc = settings["set_desc"]
        self.desc = settings["desc"]
        self.upload_delay = settings["upload_delay"]
        if 'upgrade' in settings:
            self.upgrade = settings["upgrade"]
        if 'allow_big_file' in settings:
            self.allow_big_file = settings["allow_big_file"]
        self.show_values()

    def get_values(self) -> dict:
        """读取输入控件的值"""
        if self.download_threads_var.text():
            self.download_threads = int(self.download_threads_var.text())
        if self.max_size_var.text():
            self.max_size = int(self.max_size_var.text())
        if self.timeout_var.text():
            self.timeout = int(self.timeout_var.text())
        if self.upload_delay_var.text():
            self.upload_delay = int(self.upload_delay_var.text())
        self.dl_path = str(self.dl_path_var.text())
        self.pwd = str(self.set_pwd_var.toPlainText())
        self.desc = str(self.set_desc_var.toPlainText())
        return {"download_threads": self.download_threads,
                "max_size": self.max_size,
                "timeout": self.timeout,
                "dl_path": self.dl_path,
                "time_fmt": self.time_fmt,
                "to_tray": self.to_tray,
                "watch_clipboard": self.watch_clipboard,
                "debug": self.debug,
                "set_pwd": self.set_pwd,
                "pwd": self.pwd,
                "set_desc": self.set_desc,
                "desc": self.desc,
                "upload_delay": self.upload_delay,
                "allow_big_file": self.allow_big_file,
                "upgrade": self.upgrade}

    def initUI(self):
        self.setWindowTitle("设置")
        logo = QLabel()
        logo.setPixmap(QPixmap(SRC_DIR + "logo2.gif"))
        logo.setStyleSheet("background-color:rgb(255,255,255);")
        logo.setAlignment(Qt.AlignCenter)
        self.download_threads_lb = QLabel("同时下载文件数")
        self.download_threads_var = QLineEdit()
        self.download_threads_var.setPlaceholderText("范围：1-9")
        self.download_threads_var.setToolTip("范围：1-9")
        self.download_threads_var.setInputMask("D")
        self.max_size_lb = QLabel("分卷大小(MB)")
        self.max_size_var = QLineEdit()
        self.max_size_var.setPlaceholderText("普通用户最大100，vip用户根据具体情况设置")
        self.max_size_var.setToolTip("普通用户最大100，vip用户根据具体情况设置")
        self.max_size_var.setInputMask("D99")
        self.timeout_lb = QLabel("请求超时(秒)")
        self.timeout_var = QLineEdit()
        self.timeout_var.setPlaceholderText("范围：1-99")
        self.timeout_var.setToolTip("范围：1-99")
        self.timeout_var.setInputMask("D9")
        self.upload_delay_lb = QLabel("上传延时(秒)")
        self.upload_delay_var = QLineEdit()
        self.upload_delay_var.setPlaceholderText("范围：1-99")
        self.upload_delay_var.setToolTip("范围：1-99")
        self.upload_delay_var.setInputMask("D9")
        self.dl_path_lb = QLabel("下载保存路径")
        self.dl_path_var = MyLineEdit(self)
        self.dl_path_var.clicked.connect(self.set_download_path)
        self.time_fmt_box = QCheckBox("使用[年-月-日]时间格式")
        self.time_fmt_box.setToolTip("文件上传日期显示格式")
        self.to_tray_box = QCheckBox("关闭到系统托盘")
        self.to_tray_box.setToolTip("点击关闭软件按钮是最小化软件至系统托盘")
        self.watch_clipboard_box = QCheckBox("监听系统剪切板")
        self.watch_clipboard_box.setToolTip("检测到系统剪切板中有符合规范的蓝奏链接时自动唤起软件，并提取")
        self.debug_box = QCheckBox("开启调试日志")
        self.debug_box.setToolTip("记录软件 debug 信息至 debug-lanzou-gui.log 文件")
        self.set_pwd_box = QCheckBox("上传文件自动设置密码")
        self.set_pwd_var = AutoResizingTextEdit()
        self.set_pwd_var.setPlaceholderText(" 2-8 位数字或字母")
        self.set_pwd_var.setToolTip("2-8 位数字或字母")
        self.set_desc_box = QCheckBox("上传文件自动设置描述")
        self.set_desc_var = AutoResizingTextEdit()
        self.big_file_box = QCheckBox(f"允许上传超过 {self.max_size}MB 的大文件")
        self.big_file_box.setToolTip("开启大文件上传支持 (功能下线)")
        self.upgrade_box = QCheckBox("自动检测新版本")
        self.upgrade_box.setToolTip("在软件打开时自动检测是否有新的版本发布，如有则弹出更新信息")

        self.time_fmt_box.toggle()
        self.time_fmt_box.stateChanged.connect(self.change_time_fmt)
        self.to_tray_box.stateChanged.connect(self.change_to_tray)
        self.watch_clipboard_box.stateChanged.connect(self.change_watch_clipboard)
        self.debug_box.stateChanged.connect(self.change_debug)
        self.set_pwd_box.stateChanged.connect(self.change_set_pwd)
        self.set_pwd_var.editingFinished.connect(self.check_pwd)
        self.set_desc_box.stateChanged.connect(self.change_set_desc)
        self.big_file_box.stateChanged.connect(self.change_big_file)
        self.upgrade_box.stateChanged.connect(self.change_upgrade)

        buttonBox = QDialogButtonBox()
        buttonBox.setOrientation(Qt.Horizontal)
        buttonBox.setStandardButtons(QDialogButtonBox.Reset | QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttonBox.button(QDialogButtonBox.Reset).setText("重置")
        buttonBox.button(QDialogButtonBox.Save).setText("保存")
        buttonBox.button(QDialogButtonBox.Cancel).setText("取消")
        buttonBox.button(QDialogButtonBox.Reset).clicked.connect(lambda: self.set_values(reset=True))
        buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.slot_save)
        buttonBox.rejected.connect(self.reject)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)
        form.addRow(self.download_threads_lb, self.download_threads_var)
        form.addRow(self.timeout_lb, self.timeout_var)
        form.addRow(self.upload_delay_lb, self.upload_delay_var)
        form.addRow(self.max_size_lb, self.max_size_var)
        form.addRow(self.dl_path_lb, self.dl_path_var)

        vbox = QVBoxLayout()
        vbox.addWidget(logo)
        vbox.addStretch(1)
        vbox.addLayout(form)
        vbox.addStretch(1)
        hbox = QHBoxLayout()
        hbox.addWidget(self.time_fmt_box)
        hbox.addWidget(self.to_tray_box)
        hbox.addWidget(self.watch_clipboard_box)
        hbox.addWidget(self.debug_box)
        vbox.addLayout(hbox)
        vbox.addStretch(1)
        hbox_2 = QHBoxLayout()
        hbox_2.addWidget(self.set_pwd_box)
        hbox_2.addWidget(self.set_pwd_var)
        vbox.addLayout(hbox_2)
        vbox.addStretch(1)
        hbox_3 = QHBoxLayout()
        hbox_3.addWidget(self.set_desc_box)
        hbox_3.addWidget(self.set_desc_var)
        vbox.addLayout(hbox_3)
        hbox_4 = QHBoxLayout()
        hbox_4.addWidget(self.big_file_box)
        hbox_4.addWidget(self.upgrade_box)
        vbox.addStretch(1)
        vbox.addLayout(hbox_4)
        vbox.addStretch(2)
        vbox.addWidget(buttonBox)
        self.setLayout(vbox)
        self.setMinimumWidth(500)

    def change_time_fmt(self, state):
        if state == Qt.Checked:
            self.time_fmt = True
        else:
            self.time_fmt = False

    def change_to_tray(self, state):
        if state == Qt.Checked:
            self.to_tray = True
        else:
            self.to_tray = False

    def change_watch_clipboard(self, state):
        if state == Qt.Checked:
            self.watch_clipboard = True
        else:
            self.watch_clipboard = False

    def change_debug(self, state):
        if state == Qt.Checked:
            self.debug = True
        else:
            self.debug = False

    def change_big_file(self, state):
        if state == Qt.Checked:
            self.allow_big_file = True
        else:
            self.allow_big_file = False

    def change_upgrade(self, state):
        if state == Qt.Checked:
            self.upgrade = True
        else:
            self.upgrade = False

    def change_set_pwd(self, state):
        if state == Qt.Checked:
            self.set_pwd = True
            self.set_pwd_var.setDisabled(False)
        else:
            self.set_pwd = False
            self.set_pwd_var.setDisabled(True)

    def change_set_desc(self, state):
        if state == Qt.Checked:
            self.set_desc = True
            self.set_desc_var.setDisabled(False)
        else:
            self.set_desc = False
            self.set_desc_var.setDisabled(True)

    def check_pwd(self):
        pwd = self.set_pwd_var.toPlainText()
        pwd = ''.join(list(filter(str.isalnum, pwd)))
        if len(pwd) < 2:
            pwd = ""
        self.set_pwd_var.setText(pwd[:8])

    def set_download_path(self):
        """设置下载路径"""
        dl_path = QFileDialog.getExistingDirectory(self, "选择文件下载保存文件夹", self.cwd)
        dl_path = os.path.normpath(dl_path)  # windows backslash
        if dl_path == self.dl_path or dl_path == ".":
            return None
        self.dl_path_var.setText(dl_path)
        self.dl_path = dl_path

    def slot_save(self):
        """保存槽函数"""
        self._config.settings = self.get_values()
        self.saved.emit()
        self.close()
