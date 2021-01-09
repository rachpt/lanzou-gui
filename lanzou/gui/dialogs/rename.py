from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QLabel, QGridLayout, QDialogButtonBox, QLineEdit, QTextEdit

from lanzou.gui.qss import dialog_qss_style
from lanzou.debug import SRC_DIR


class RenameDialog(QDialog):
    out = pyqtSignal(object)

    def __init__(self, parent=None):
        super(RenameDialog, self).__init__(parent)
        self.infos = []
        self.min_width = 400
        self.initUI()
        self.update_text()
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, infos=None):
        self.infos = infos or []
        self.update_text()  # 更新界面

    def initUI(self):
        self.setWindowIcon(QIcon(SRC_DIR + "desc.ico"))
        self.lb_name = QLabel()
        self.lb_name.setText("文件夹名：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        self.lb_desc = QLabel()
        self.tx_desc = QTextEdit()
        self.lb_desc.setText("描　　述：")
        self.lb_desc.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_name, 1, 0)
        self.grid.addWidget(self.tx_name, 1, 1)
        self.grid.addWidget(self.lb_desc, 2, 0)
        self.grid.addWidget(self.tx_desc, 2, 1, 5, 1)
        self.grid.addWidget(self.buttonBox, 7, 1, 1, 1)
        self.setLayout(self.grid)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def update_text(self):
        self.tx_desc.setFocus()
        num = len(self.infos)
        if num == 1:
            self.lb_name.setVisible(True)
            self.tx_name.setVisible(True)
            infos = self.infos[0]
            self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("")  # 去除新建文件夹影响
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)  # 去除新建文件夹影响
            self.setWindowTitle("修改文件夹名与描述")
            self.tx_name.setText(str(infos.name))
            if infos.desc:
                self.tx_desc.setText(str(infos.desc))
                self.tx_desc.setToolTip('原描述：' + str(infos.desc))
            else:
                self.tx_desc.setText("")
                self.tx_desc.setToolTip('')
            self.tx_desc.setPlaceholderText("无")
            self.min_width = len(str(infos.name)) * 8
            if infos.is_file:
                self.setWindowTitle("修改文件描述")
                self.tx_name.setFocusPolicy(Qt.NoFocus)
                self.tx_name.setReadOnly(True)
            else:
                self.tx_name.setFocusPolicy(Qt.StrongFocus)
                self.tx_name.setReadOnly(False)
                self.tx_name.setFocus()
        elif num > 1:
            self.lb_name.setVisible(False)
            self.tx_name.setVisible(False)
            self.setWindowTitle(f"批量修改{num}个文件(夹)的描述")
            self.tx_desc.setText('')
            self.tx_desc.setPlaceholderText("建议160字数以内。")

        else:
            self.setWindowTitle("新建文件夹")
            self.tx_name.setText("")
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("请先输入文件名！")
            self.tx_name.textChanged.connect(self.slot_new_ok_btn)
            self.tx_name.setPlaceholderText("不支持空格，如有会被自动替换成 _")
            self.tx_name.setFocusPolicy(Qt.StrongFocus)
            self.tx_name.setReadOnly(False)
            self.tx_desc.setPlaceholderText("可选项，建议160字数以内。")
            self.tx_name.setFocus()
        if self.min_width < 400:
            self.min_width = 400
        self.resize(self.min_width, 200)

    def slot_new_ok_btn(self):
        """新建文件夹槽函数"""
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("")

    def btn_ok(self):
        new_name = self.tx_name.text()
        new_des = self.tx_desc.toPlainText()
        info_len = len(self.infos)
        if info_len == 0:  # 在 work_id 新建文件夹
            if new_name:
                self.out.emit(("new", new_name, new_des))
        elif info_len == 1:
            if new_name != self.infos[0].name or new_des != self.infos[0].desc:
                self.infos[0].new_des = new_des
                self.infos[0].new_name = new_name
                self.out.emit(("change", self.infos))
        else:
            if new_des:
                for infos in self.infos:
                    infos.new_des = new_des
                self.out.emit(("change", self.infos))
