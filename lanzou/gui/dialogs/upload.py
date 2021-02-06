import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import (QDialog, QLabel, QDialogButtonBox, QPushButton, QListView,
                             QVBoxLayout, QHBoxLayout, QAbstractItemView, QFileDialog)

from lanzou.gui.qss import dialog_qss_style
from lanzou.gui.others import MyListView
from lanzou.gui.models import UpJob
from lanzou.debug import SRC_DIR


class UploadDialog(QDialog):
    """文件上传对话框"""
    new_infos = pyqtSignal(object)

    def __init__(self, user_home):
        super().__init__()
        self.cwd = user_home
        self._folder_id = -1
        self._folder_name = "LanZouCloud"
        self.set_pwd = False
        self.set_desc = False
        self.pwd = ''
        self.desc = ''
        self.allow_big_file = False
        self.max_size = 100
        self.selected = []
        self.initUI()
        self.set_size()
        self.setStyleSheet(dialog_qss_style)

    def set_pwd_desc_bigfile(self, settings):
        self.set_pwd = settings["set_pwd"]
        self.set_desc = settings["set_desc"]
        self.pwd = settings["pwd"]
        self.desc = settings["desc"]
        self.allow_big_file = settings["allow_big_file"]
        self.max_size = settings["max_size"]
        if self.allow_big_file:
            self.btn_chooseMultiFile.setToolTip("")
        else:
            self.btn_chooseMultiFile.setToolTip(f"文件大小上限 {self.max_size}MB")

    def set_values(self, folder_name, folder_id, files):
        self.setWindowTitle("上传文件至 ➩ " + str(folder_name))
        self._folder_id = folder_id
        self._folder_name = folder_name
        if files:
            self.selected = files
            self.show_selected()
        self.exec()

    def initUI(self):
        self.setWindowTitle("上传文件")
        self.setWindowIcon(QIcon(SRC_DIR + "upload.ico"))
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap(SRC_DIR + "logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)

        # btn 1
        self.btn_chooseDir = QPushButton("选择文件夹", self)
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setIcon(QIcon(SRC_DIR + "folder.gif"))

        # btn 2
        self.btn_chooseMultiFile = QPushButton("选择多文件", self)
        self.btn_chooseDir.setObjectName("btn_chooseMultiFile")
        self.btn_chooseMultiFile.setObjectName("btn_chooseMultiFile")
        self.btn_chooseMultiFile.setIcon(QIcon(SRC_DIR + "file.ico"))

        # btn 3
        self.btn_deleteSelect = QPushButton("移除", self)
        self.btn_deleteSelect.setObjectName("btn_deleteSelect")
        self.btn_deleteSelect.setIcon(QIcon(SRC_DIR + "delete.ico"))
        self.btn_deleteSelect.setToolTip("按 Delete 移除选中文件")

        # 列表
        self.list_view = MyListView()
        self.list_view.drop_files.connect(self.add_drop_files)
        self.list_view.setViewMode(QListView.ListMode)
        self.slm = QStandardItem()
        self.model = QStandardItemModel()
        self.list_view.setModel(self.model)
        self.model.removeRows(0, self.model.rowCount())  # 清除旧的选择
        self.list_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

        vbox = QVBoxLayout()
        hbox_head = QHBoxLayout()
        hbox_button = QHBoxLayout()
        hbox_head.addWidget(self.btn_chooseDir)
        hbox_head.addStretch(1)
        hbox_head.addWidget(self.btn_chooseMultiFile)
        hbox_button.addWidget(self.btn_deleteSelect)
        hbox_button.addStretch(1)
        hbox_button.addWidget(self.buttonBox)
        vbox.addWidget(self.logo)
        vbox.addLayout(hbox_head)
        vbox.addWidget(self.list_view)
        vbox.addLayout(hbox_button)
        self.setLayout(vbox)
        self.setMinimumWidth(350)

        # 设置信号
        self.btn_chooseDir.clicked.connect(self.slot_btn_chooseDir)
        self.btn_chooseMultiFile.clicked.connect(self.slot_btn_chooseMultiFile)
        self.btn_deleteSelect.clicked.connect(self.slot_btn_deleteSelect)

        self.buttonBox.accepted.connect(self.slot_btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.clear_old)
        self.buttonBox.rejected.connect(self.reject)

    def set_size(self):
        if self.selected:
            h = 18 if len(self.selected) > 18 else 10
            w = 40
            for i in self.selected:
                i_len = len(i)
                if i_len > 100:
                    w = 100
                    break
                if i_len > w:
                    w = i_len
            self.resize(120 + w * 7, h * 30)
        else:
            self.resize(400, 300)

    def clear_old(self):
        self.selected = []
        self.model.removeRows(0, self.model.rowCount())
        self.set_size()

    def show_selected(self):
        self.model.removeRows(0, self.model.rowCount())
        for item in self.selected:
            if os.path.isfile(item):
                self.model.appendRow(QStandardItem(QIcon(SRC_DIR + "file.ico"), item))
            else:
                self.model.appendRow(QStandardItem(QIcon(SRC_DIR + "folder.gif"), item))
            self.set_size()

    def backslash(self):
        """Windows backslash"""
        tasks = {}
        for item in self.selected:
            url = os.path.normpath(item)
            total_size = 0
            total_file = 0
            if os.path.isfile(url):
                total_size = os.path.getsize(url)
                total_file += 1
            else:
                for filename in os.listdir(url):
                    file_path = os.path.join(url, filename)
                    if not os.path.isfile(file_path):
                        continue  # 跳过子文件夹
                    total_size += os.path.getsize(file_path)
                    total_file += 1
            tasks[url] = UpJob(url=url,
                               fid=self._folder_id,
                               folder=self._folder_name,
                               pwd=self.pwd if self.set_pwd else None,
                               desc=self.desc if self.set_desc else None,
                               total_size=total_size,
                               total_file=total_file)
        return tasks

    def slot_btn_ok(self):
        tasks = self.backslash()
        if self.selected:
            self.new_infos.emit(tasks)
            self.clear_old()

    def slot_btn_deleteSelect(self):
        _indexes = self.list_view.selectionModel().selection().indexes()
        if not _indexes:
            return
        indexes = []
        for i in _indexes:  # 获取所选行号
            indexes.append(i.row())
        indexes = set(indexes)
        for i in sorted(indexes, reverse=True):
            self.selected.remove(self.model.item(i, 0).text())
            self.model.removeRow(i)
        self.set_size()

    def add_drop_files(self, files):
        for item in files:
            if item not in self.selected:
                self.selected.append(item)
            self.show_selected()

    def slot_btn_chooseDir(self):
        dir_choose = QFileDialog.getExistingDirectory(self, "选择文件夹", self.cwd)  # 起始路径
        if dir_choose == "":
            return
        if dir_choose not in self.selected:
            self.selected.append(dir_choose)
            self.cwd = os.path.dirname(dir_choose)
        self.show_selected()

    def slot_btn_chooseMultiFile(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择多文件", self.cwd, "All Files (*)")
        if len(files) == 0:
            return
        for _file in files:
            if _file not in self.selected:
                if os.path.getsize(_file) <= self.max_size * 1048576:
                    self.selected.append(_file)
                elif self.allow_big_file:
                    self.selected.append(_file)
        self.show_selected()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:  # delete
            self.slot_btn_deleteSelect()
