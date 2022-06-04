
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import  QDialog, QLabel, QListView, QDialogButtonBox, QVBoxLayout

from lanzou.gui.others import set_file_icon
from lanzou.gui.qss import dialog_qss_style
from lanzou.debug import SRC_DIR


class DeleteDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(DeleteDialog, self).__init__(parent)
        self.infos = infos
        self.out = []
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def initUI(self):
        self.setWindowTitle("确认删除")
        self.setWindowIcon(QIcon(SRC_DIR + "delete.ico"))
        self.layout = QVBoxLayout()
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ViewMode.ListMode)
        # 列表
        self.slm = QStandardItem()
        self.model = QStandardItemModel()
        max_len = 10
        count = 0
        for info in self.infos:
            if info.is_file:  # 文件
                self.model.appendRow(QStandardItem(set_file_icon(info.name), info.name))
            else:
                self.model.appendRow(QStandardItem(QIcon(SRC_DIR + "folder.gif"), info.name))
            self.out.append({'fid': info.id, 'is_file': info.is_file, 'name': info.name})  # id，文件标示, 文件名
            count += 1
            if max_len < len(info.name):  # 使用最大文件名长度
                max_len = len(info.name)
        self.list_view.setModel(self.model)

        self.lb_name = QLabel("尝试删除以下{}个文件(夹)：".format(count))
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")

        self.layout.addWidget(self.lb_name)
        self.layout.addWidget(self.list_view)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setMinimumWidth(400)
        self.resize(int(max_len*8), int(count*34+60))

    def btn_ok(self):
        self.new_infos.emit(self.out)
