from PyQt6.QtCore import Qt, pyqtSignal, QLine, QPoint, PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtGui import  QPixmap, QPainter, QPen
from PyQt6.QtWidgets import (QPushButton, QDialog, QLabel, QFormLayout,
                             QDialogButtonBox, QVBoxLayout, QHBoxLayout)

from lanzou.gui.qss import others_style, btn_style
from lanzou.debug import SRC_DIR


class AboutDialog(QDialog):
    check_update = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self._ver = ''
        self._github = 'https://github.com/rachpt/lanzou-gui'
        self._api_url = 'https://github.com/zaxtyson/LanZouCloud-API'
        self._gitee = 'https://gitee.com/rachpt/lanzou-gui'
        self._home_page = 'https://rachpt.cn/lanzou-gui/'
        self.initUI()
        self.setStyleSheet(others_style)

    def set_values(self, version):
        self._ver = version
        self.lb_name_text.setText(f"v{version}  (点击检查更新)")  # 更新版本

    def show_update(self, ver, msg):
        self.lb_new_ver = QLabel("新版")  # 检测新版
        self.lb_new_ver_msg = QLabel()
        self.lb_new_ver_msg.setOpenExternalLinks(True)
        self.lb_new_ver_msg.setWordWrap(True)
        if ver != '0':
            self.lb_name_text.setText(f"{self._ver}  ➡  {ver}")
        self.lb_new_ver_msg.setText(msg)
        self.lb_new_ver_msg.setMinimumWidth(700)
        if self.form.rowCount() < 5:
            self.form.insertRow(1, self.lb_new_ver, self.lb_new_ver_msg)

    def initUI(self):
        self.setWindowTitle("关于 lanzou-gui")
        about = f'本项目使用PyQt6实现图形界面，可以完成蓝奏云的大部分功能<br/> \
    得益于 <a href="{self._api_url}">API</a> 的功能，可以间接突破单文件最大 100MB 的限制，同时增加了批量上传/下载的功能<br/> \
Python 依赖见<a href="{self._github }/blob/master/requirements.txt">requirements.txt</a>，\
<a href="{self._github}/releases">releases</a> 有打包好了的 Windows 可执行程序，但可能不是最新的'
        project_url = f'<a href="{self._home_page}">主页</a> | <a href="{self._github}">repo</a> | \
                        <a href="{self._gitee}">mirror repo</a>'
        self.logo = QLabel()  # logo
        self.logo.setPixmap(QPixmap(SRC_DIR + "logo2.gif"))
        self.logo.setStyleSheet("background-color:rgb(255,255,255);")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lb_qt_ver = QLabel("依赖")  # QT 版本
        self.lb_qt_text = QLabel(f"QT: {QT_VERSION_STR}, PyQt: {PYQT_VERSION_STR}")  # QT 版本
        self.lb_name = QLabel("版本")  # 版本
        self.lb_name_text = QPushButton("")  # 版本
        self.lb_name_text.setToolTip("点击检查更新")
        ver_style = "QPushButton {border:none; background:transparent;font-weight:bold;color:blue;}"
        self.lb_name_text.setStyleSheet(ver_style)
        self.lb_name_text.clicked.connect(lambda: self.check_update.emit(self._ver, True))
        self.lb_about = QLabel("关于")  # about
        self.lb_about_text = QLabel()
        self.lb_about_text.setText(about)
        self.lb_about_text.setOpenExternalLinks(True)
        self.lb_author = QLabel("作者")  # author
        self.lb_author_mail = QLabel("<a href='mailto:rachpt@126.com'>rachpt</a>")
        self.lb_author_mail.setOpenExternalLinks(True)
        self.lb_update = QLabel("项目")  # 更新
        self.lb_update_url = QLabel(project_url)
        self.lb_update_url.setOpenExternalLinks(True)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.setStyleSheet(btn_style)

        self.recommend = QLabel("<br />大文件推荐使用 <a href='https://github.com/Aruelius/cloud189'>cloud189-cli</a>")
        self.recommend.setOpenExternalLinks(True)

        self.line = QLine(QPoint(), QPoint(550, 0))
        self.lb_line = QLabel('<html><hr /></html>')

        vbox = QVBoxLayout()
        vbox.addWidget(self.logo)
        vbox.addStretch(1)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.form.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        self.form.setHorizontalSpacing(40)
        self.form.setVerticalSpacing(15)
        self.form.addRow(self.lb_qt_ver, self.lb_qt_text)
        self.form.addRow(self.lb_name, self.lb_name_text)
        self.form.addRow(self.lb_update, self.lb_update_url)
        self.form.addRow(self.lb_author, self.lb_author_mail)
        self.form.addRow(self.lb_about, self.lb_about_text)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)  # 覆盖MacOS的默认样式
        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addWidget(self.recommend)
        vbox.addWidget(self.lb_line)
        donate = QLabel()
        donate.setText("<b>捐助我</b>&nbsp;如果你愿意")
        donate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hbox = QHBoxLayout()
        hbox.addStretch(2)
        for it in ["wechat", "alipay", "qqpay"]:
            lb = QLabel()
            lb.setPixmap(QPixmap(SRC_DIR + f"{it}.jpg"))
            hbox.addWidget(lb)
        hbox.addStretch(1)
        hbox.addWidget(self.buttonBox)
        vbox.addWidget(donate)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        self.setMinimumWidth(720)

    def paintEvent(self, event):
        QDialog.paintEvent(self, event)
        if not self.line.isNull():
            painter = QPainter(self)
            pen = QPen(Qt.GlobalColor.red, 3)
            painter.setPen(pen)
            painter.drawLine(self.line)
