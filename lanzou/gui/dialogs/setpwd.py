from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QLabel, QGridLayout, QDialogButtonBox, QLineEdit

from lanzou.gui.qss import dialog_qss_style
from lanzou.gui.models import FileInfos
from lanzou.debug import SRC_DIR


class SetPwdDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, parent=None):
        super(SetPwdDialog, self).__init__(parent)
        self.infos = []
        self.initUI()
        self.update_text()
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, infos):
        self.infos = infos
        self.update_text()  # 更新界面

    def set_tip(self):  # 用于提示状态
        self.setWindowTitle("请稍等……")

    def initUI(self):
        self.setWindowTitle("请稍等……")
        self.setWindowIcon(QIcon(SRC_DIR + "password.ico"))
        self.lb_oldpwd = QLabel()
        self.lb_oldpwd.setText("当前提取码：")
        self.lb_oldpwd.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.tx_oldpwd = QLineEdit()
        # 当前提取码 只读
        self.tx_oldpwd.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tx_oldpwd.setReadOnly(True)
        self.lb_newpwd = QLabel()
        self.lb_newpwd.setText("新的提取码：")
        self.lb_newpwd.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.tx_newpwd = QLineEdit()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_oldpwd, 1, 0)
        self.grid.addWidget(self.tx_oldpwd, 1, 1)
        self.grid.addWidget(self.lb_newpwd, 2, 0)
        self.grid.addWidget(self.tx_newpwd, 2, 1)
        self.grid.addWidget(self.buttonBox, 3, 0, 1, 2)
        self.setLayout(self.grid)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.accepted.connect(self.set_tip)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.rejected.connect(self.set_tip)
        self.setMinimumWidth(280)

    def update_text(self):
        num = len(self.infos)
        if num == 1:
            self.tx_oldpwd.setVisible(True)
            self.lb_oldpwd.setVisible(True)
            infos = self.infos[0]
            if infos.has_pwd:
                self.tx_oldpwd.setText(str(infos.pwd))
                self.tx_oldpwd.setPlaceholderText("")
            else:
                self.tx_oldpwd.setText("")
                self.tx_oldpwd.setPlaceholderText("无")

            if isinstance(infos, FileInfos):  # 文件  通过size列判断是否为文件
                self.setWindowTitle("修改文件提取码")
                self.tx_newpwd.setPlaceholderText("2-6位字符,关闭请留空")
                self.tx_newpwd.setMaxLength(6)  # 最长6个字符
            else:  # 文件夹
                self.setWindowTitle("修改文件夹名提取码")
                self.tx_newpwd.setPlaceholderText("2-12位字符,关闭请留空")
                self.tx_newpwd.setMaxLength(12)  # 最长12个字符
        elif num > 1:
            self.tx_oldpwd.setVisible(False)
            self.lb_oldpwd.setVisible(False)
            self.setWindowTitle(f"批量修改{num}个文件(夹)的提取码")
            self.tx_newpwd.setPlaceholderText("2-12位字符,关闭请留空")
            self.tx_newpwd.setMaxLength(12)  # 最长12个字符
            self.tx_newpwd.setText('')
            for infos in self.infos:
                if isinstance(infos, FileInfos):  # 文件
                    self.tx_newpwd.setPlaceholderText("2-6位字符,文件无法关闭")
                    self.tx_newpwd.setMaxLength(6)  # 最长6个字符
                    break

    def btn_ok(self):
        new_pwd = self.tx_newpwd.text()
        for infos in self.infos:
            infos.new_pwd = new_pwd
        self.new_infos.emit(self.infos)  # 最后一位用于标示文件还是文件夹
