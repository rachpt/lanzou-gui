from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QLabel, QGridLayout, QDialogButtonBox, QComboBox

from lanzou.gui.qss import dialog_qss_style
from lanzou.gui.others import AutoResizingTextEdit
from lanzou.debug import SRC_DIR


class MoveFileDialog(QDialog):
    '''移动文件对话框'''
    new_infos = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MoveFileDialog, self).__init__(parent)
        self.infos = None
        self.dirs = {}
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def update_ui(self):
        names = "\n".join([i.name for i in self.infos])
        names_tip = "\n".join([i.name for i in self.infos])
        self.tx_name.setText(names)
        self.tx_name.setToolTip(names_tip)

        self.tx_new_path.clear()
        f_icon = QIcon(SRC_DIR + "folder.gif")
        for f_name, fid in self.dirs.items():
            if len(f_name) > 50:  # 防止文件夹名字过长？
                f_name = f_name[:47] + "..."
            self.tx_new_path.addItem(f_icon, "id：{:>8}，name：{}".format(fid, f_name))

    def set_values(self, infos, all_dirs_dict):
        self.infos = infos
        self.dirs = all_dirs_dict
        self.update_ui()
        self.exec()

    def initUI(self):
        self.setWindowTitle("移动文件(夹)")
        self.setWindowIcon(QIcon(SRC_DIR + "move.ico"))
        self.lb_name = QLabel()
        self.lb_name.setText("文件(夹)名：")
        self.lb_name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.tx_name = AutoResizingTextEdit()
        self.tx_name.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 只读
        self.tx_name.setReadOnly(True)
        self.lb_new_path = QLabel()
        self.lb_new_path.setText("目标文件夹：")
        self.lb_new_path.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.tx_new_path = QComboBox()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_name, 1, 0)
        self.grid.addWidget(self.tx_name, 1, 1)
        self.grid.addWidget(self.lb_new_path, 2, 0)
        self.grid.addWidget(self.tx_new_path, 2, 1)
        self.grid.addWidget(self.buttonBox, 3, 0, 1, 2)
        self.setLayout(self.grid)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setMinimumWidth(280)

    def btn_ok(self):
        new_id = self.tx_new_path.currentText().split("，")[0].split("：")[1]
        for index in range(len(self.infos)):
            self.infos[index].new_id = int(new_id)
        self.new_infos.emit(self.infos)
