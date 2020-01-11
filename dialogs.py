import os
from pickle import dump, load
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from Ui_share import Ui_Dialog


def update_settings(_config, up_info):
    """更新配置文件"""
    try:
        with open(_config, "rb") as _file:
            _info = load(_file)
    except Exception:
        _info = {}
    _info.update(up_info)
    with open(_config, "wb") as _file:
        dump(_info, _file)


class MyLineEdit(QLineEdit):
    """添加单击事件的输入框，用于设置下载路径"""

    clicked = pyqtSignal()

    def __init__(self, parent):
        super(MyLineEdit, self).__init__(parent)

    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.LeftButton:
            self.clicked.emit()


class LoginDialog(QDialog):
    """登录对话框"""

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._user = ""
        self._pwd = ""
        self._cookie = ""
        self.initUI()
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.cookie_ed.textChanged.connect(self.set_cookie)
        self.btn_ok.clicked.connect(self.clicked_ok)
        self.btn_cancel.clicked.connect(self.clicked_cancel)

    def default_var(self):
        try:
            with open(self._config, "rb") as _file:
                _info = load(_file)
            self._user = _info["user"]
            self._pwd = _info["pwd"]
            self._cookie = _info["cookie"]
        except Exception:
            pass
        self.name_ed.setText(self._user)
        self.pwd_ed.setText(self._pwd)
        self.cookie_ed.setPlainText(self._cookie)

    def initUI(self):
        self.setWindowTitle("登录蓝奏云")
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)
        self.name_lb = QLabel("&User")
        self.name_ed = QLineEdit()
        self.name_lb.setBuddy(self.name_ed)

        self.pwd_lb = QLabel("&Password")
        self.pwd_ed = QLineEdit()
        self.pwd_ed.setEchoMode(QLineEdit.Password)
        self.pwd_lb.setBuddy(self.pwd_ed)

        self.cookie_lb = QLabel("&Cookie")
        self.cookie_ed = QTextEdit()
        notice = "如果由于滑动验证，无法使用用户名与密码登录，则需要输入cookie，自行使用浏览器获取，" \
            "cookie会保持在本地，下次使用。其格式如下：\n\n key1=value1; key2=value2"
        self.cookie_ed.setPlaceholderText(notice)
        self.cookie_lb.setBuddy(self.cookie_ed)

        self.btn_ok = QPushButton("&OK")
        self.btn_cancel = QPushButton("&Cancel")
        main_layout = QGridLayout()
        main_layout.addWidget(self.logo, 0, 0, 2, 4)
        main_layout.addWidget(self.name_lb, 2, 0)
        main_layout.addWidget(self.name_ed, 2, 1, 1, 3)
        main_layout.addWidget(self.pwd_lb, 3, 0)
        main_layout.addWidget(self.pwd_ed, 3, 1, 1, 3)
        main_layout.addWidget(self.cookie_lb, 4, 0)
        main_layout.addWidget(self.cookie_ed, 4, 1, 2, 3)
        main_layout.addWidget(self.btn_ok, 6, 2)
        main_layout.addWidget(self.btn_cancel, 6, 3)
        self.setLayout(main_layout)
        self.default_var()

    def set_user(self, user):
        self._user = user

    def set_pwd(self, pwd):
        self._pwd = pwd

    def set_cookie(self):
        self._cookie = self.cookie_ed.toPlainText()

    def clicked_cancel(self):
        self.default_var()
        self.close()

    def clicked_ok(self):
        up_info = {"user": self._user, "pwd": self._pwd, "cookie": self._cookie}
        update_settings(self._config, up_info)
        self.close()


class UploadDialog(QDialog):
    """文件上传对话框"""
    new_infos = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()
        self.selected = []
        self.max_len = 400
        self.initUI()
        self.set_size()

    def initUI(self):
        self.setWindowTitle("上传文件")
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)

        # btn 1
        self.btn_chooseDir = QPushButton("选择文件夹", self)
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setIcon(QIcon("./icon/folder_open.gif"))

        # btn 2
        self.btn_chooseMutiFile = QPushButton("选择多文件", self)
        self.btn_chooseMutiFile.setObjectName("btn_chooseMutiFile")
        self.btn_chooseMutiFile.setIcon(QIcon("./icon/file.ico"))

        # btn 3
        self.btn_deleteSelect = QPushButton("删除", self)
        self.btn_deleteSelect.setObjectName("btn_deleteSelect")
        self.btn_deleteSelect.setIcon(QIcon("./icon/delete.ico"))

        # 列表
        self.list_view = QListView(self)
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

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self.logo, 1, 0, 1, 3)
        grid.addWidget(self.btn_chooseDir, 2, 0)
        grid.addWidget(self.btn_chooseMutiFile, 2, 2)
        grid.addWidget(self.list_view, 3, 0, 2, 3)
        grid.addWidget(self.btn_deleteSelect, 5, 0)
        grid.addWidget(self.buttonBox, 5, 1, 1, 2)
        self.setLayout(grid)

        self.setMinimumWidth(350)

        # 设置信号
        self.btn_chooseDir.clicked.connect(self.slot_btn_chooseDir)
        self.btn_chooseMutiFile.clicked.connect(self.slot_btn_chooseMutiFile)
        self.btn_deleteSelect.clicked.connect(self.slot_btn_deleteSelect)

        self.buttonBox.accepted.connect(self.slot_btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.clear_old)
        self.buttonBox.rejected.connect(self.reject)

    def set_size(self):
        rows = self.model.rowCount()
        for i in range(rows):
            m_len = int(len(self.model.item(i, 0).text()) * 4)
            if m_len > self.max_len:
                self.max_len = m_len
        self.resize(self.max_len, 250+rows*28)

    def clear_old(self):
        self.selected = []
        self.model.removeRows(0, self.model.rowCount())
        self.set_size()

    def slot_btn_ok(self):
        if self.selected:
            self.new_infos.emit(self.selected)
            self.clear_old()

    def slot_btn_deleteSelect(self):
        _indexs = self.list_view.selectionModel().selection().indexes()
        if not _indexs:
            return
        indexs = []
        for i in _indexs:  # 获取所选行号
            indexs.append(i.row())
        indexs = set(indexs)
        for i in sorted(indexs, reverse=True):
            self.selected.remove(self.model.item(i, 0).text())
            self.model.removeRow(i)
        self.set_size()

    def slot_btn_chooseDir(self):
        dir_choose = QFileDialog.getExistingDirectory(self, "选择文件夹", self.cwd)  # 起始路径

        if dir_choose == "":
            return
        if dir_choose not in self.selected:
            self.selected.append(dir_choose)
            self.model.appendRow(QStandardItem(QIcon("./icon/folder_open.gif"), dir_choose))
            self.set_size()

    def slot_btn_chooseMutiFile(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择多文件", self.cwd, "All Files (*)")
        if len(files) == 0:
            return

        for _file in files:
            if _file not in self.selected:
                self.selected.append(_file)
                self.model.appendRow(QStandardItem(QIcon("./icon/file.ico"), _file))
        self.set_size()


class InfoDialog(QDialog, Ui_Dialog):
    """文件信息对话框"""

    def __init__(self, infos, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.infos = infos
        self.initUI()

    def initUI(self):
        self.setWindowTitle("文件信息" if self.infos[2] else "文件夹信息")
        self.logo.setPixmap(QPixmap("./icon/q9.gif"))
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("background-color:rgb(255,204,51);")
        self.tx_name.setText(self.infos[1])
        self.tx_name.setReadOnly(True)
        if self.infos[2]:
            self.tx_size.setText(self.infos[2])
        else:
            self.tx_size.hide()
            self.lb_size.hide()
        if self.infos[3]:
            self.tx_time.setText(self.infos[3])
        else:
            self.lb_time.hide()
            self.tx_time.hide()
        if self.infos[4]:
            self.tx_dl_count.setText(str(self.infos[4]))
        else:
            self.tx_dl_count.hide()
            self.lb_dl_count.hide()
        self.tx_share_url.setText(self.infos[7])
        self.tx_share_url.setReadOnly(True)
        line_h = 28  # 行高
        self.tx_share_url.setMinimumHeight(line_h)
        self.tx_share_url.setMaximumHeight(line_h)
        self.lb_share_url.setMinimumHeight(line_h)
        self.lb_share_url.setMaximumHeight(line_h)
        self.lb_name.setMinimumHeight(line_h)
        self.lb_name.setMaximumHeight(line_h)
        self.tx_name.setMinimumHeight(line_h)
        self.tx_name.setMaximumHeight(line_h)
        self.lb_pwd.setMinimumHeight(line_h)
        self.lb_pwd.setMaximumHeight(line_h)
        self.tx_pwd.setMinimumHeight(line_h)
        self.tx_pwd.setMaximumHeight(line_h)
        self.tx_pwd.setText(self.infos[5])
        self.tx_pwd.setReadOnly(True)
        self.tx_dl_link.setText(self.infos[8])
        min_width = int(len(self.infos[1]) * 7.8)
        if self.infos[8] == "无":
            if min_width < 380:
                min_width = 380
            min_height = 260
            dl_link_height = line_h
        else:
            if min_width < 480:
                min_width = 480
            min_height = 420
            dl_link_height = 120
            self.setMinimumSize(QSize(min_width, min_height))
        self.resize(min_width, min_height)
        self.tx_dl_link.setMinimumHeight(dl_link_height)
        self.tx_dl_link.setMaximumHeight(dl_link_height)
        self.lb_dl_link.setMinimumHeight(dl_link_height)
        self.lb_dl_link.setMaximumHeight(dl_link_height)


class RenameDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(RenameDialog, self).__init__(parent)
        self.infos = infos
        self.initUI()

    def initUI(self):
        self.lb_name = QLabel()
        self.lb_name.setText("文件夹名：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        self.lb_desc = QLabel()
        self.tx_desc = QTextEdit()
        if self.infos:
            self.setWindowTitle("修改文件夹名与描述")
            self.tx_name.setText(str(self.infos[1]))
            self.tx_desc.setText(str(self.infos[6]))
            min_width = len(str(self.infos[1])) * 8
            if self.infos[2]:
                # 文件无法重命名，由 infos[2] size表示文件
                self.tx_name.setFocusPolicy(Qt.NoFocus)
                self.tx_name.setReadOnly(True)
        else:
            min_width = 400
            self.setWindowTitle("新建文件夹")
        self.lb_desc.setText("描　　述：")
        self.lb_desc.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_name, 1, 0)
        self.grid.addWidget(self.tx_name, 1, 1)
        self.grid.addWidget(self.lb_desc, 2, 0)
        self.grid.addWidget(self.tx_desc, 2, 1, 5, 1)
        self.grid.addWidget(self.buttonBox, 7, 1, 1, 1)
        self.setLayout(self.grid)
        if min_width < 340:
            min_width = 340
        self.resize(min_width, 200)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def btn_ok(self):
        new_name = self.tx_name.text()
        new_desc = self.tx_desc.toPlainText()
        if not self.infos and new_name:
            self.new_infos.emit((new_name, new_desc))
            return
        if new_name != self.infos[0] or new_desc != self.infos[6]:
            self.new_infos.emit(((self.infos[0], new_name), (self.infos[6], new_desc)))


class SetPwdDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(SetPwdDialog, self).__init__(parent)
        self.infos = infos
        self.initUI()

    def initUI(self):
        if self.infos[2]:  # 通过size列判断是否为文件
            self.setWindowTitle("修改文件提取码")
        else:
            self.setWindowTitle("修改文件夹名提取码")
        self.lb_oldpwd = QLabel()
        self.lb_oldpwd.setText("当前提取码：")
        self.lb_oldpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_oldpwd = QLineEdit()
        _pwd = self.infos[5] or "无"
        self.tx_oldpwd.setText(str(_pwd))
        # 当前提取码 只读
        self.tx_oldpwd.setFocusPolicy(Qt.NoFocus)
        self.tx_oldpwd.setReadOnly(True)
        self.lb_newpwd = QLabel()
        self.lb_newpwd.setText("新的提取码：")
        self.lb_newpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_newpwd = QLineEdit()
        self.tx_newpwd.setMaxLength(6)  # 最长6个字符
        self.tx_newpwd.setPlaceholderText("2-6位字符,关闭请留空")

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

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
        self.buttonBox.rejected.connect(self.reject)
        self.setMinimumWidth(280)

    def btn_ok(self):
        new_pwd = self.tx_newpwd.text()
        if new_pwd != self.infos[5]:
            self.new_infos.emit((self.infos[0], new_pwd, self.infos[2]))  # 最后一位用于标示文件还是文件夹


class MoveFileDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, all_dirs, parent=None):
        super(MoveFileDialog, self).__init__(parent)
        self.infos = infos
        self.dirs = all_dirs
        self.initUI()

    def initUI(self):
        self.setWindowTitle("移动文件")
        self.lb_name = QLabel()
        self.lb_name.setText("文件路径：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        self.tx_name.setText(self.infos[1])
        # 只读
        self.tx_name.setFocusPolicy(Qt.NoFocus)
        self.tx_name.setReadOnly(True)
        self.lb_new_path = QLabel()
        self.lb_new_path.setText("目标文件夹：")
        self.lb_new_path.setAlignment(
            Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter
        )
        self.tx_new_path = QComboBox()
        f_icon = QIcon("./icon/folder_open.gif")
        # 莫名其妙，15 = 8*2 - 1
        self.tx_new_path.addItem(f_icon, "id：{:>15}，name：{}".format("-1", "根目录"))
        for i in self.dirs:
            f_name = i["folder_name"]
            if len(f_name) > 1000:  # 防止文件夹名字过长？
                f_name = f_name[:998] + "..."
            self.tx_new_path.addItem(f_icon, "id：{:>8}，name：{}".format(i["folder_id"], f_name))

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

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
        selected = self.tx_new_path.currentText().split("，")[0].split("：")[1]
        self.new_infos.emit((self.infos[0], selected, self.infos[1]))


class DeleteDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(DeleteDialog, self).__init__(parent)
        self.infos = infos
        self.out = []
        self.initUI()

    def set_file_icon(self, name):
        suffix = name.split(".")[-1]
        ico_path = "./icon/{}.gif".format(suffix)
        if os.path.isfile(ico_path):
            return QIcon(ico_path)
        else:
            return QIcon("./icon/file.ico")

    def initUI(self):
        self.setWindowTitle("确认删除")
        self.layout = QVBoxLayout()
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ListMode)
        # 列表
        self.slm = QStandardItem()
        self.model = QStandardItemModel()
        max_len = 10
        count = 0
        for i in self.infos:
            if i[2]:  # 有大小，是文件
                self.model.appendRow(QStandardItem(self.set_file_icon(i[1]), i[1]))
            else:
                self.model.appendRow(QStandardItem(QIcon("./icon/folder_open.gif"), i[1]))
            self.out.append((i[0], i[2]))  # id，文件标示
            count += 1
            if max_len < len(i[1]):  # 使用最大文件名长度
                max_len = len(i[1])
        self.list_view.setModel(self.model)

        self.lb_name = QLabel("尝试删除以下{}个文件(夹)：".format(count))
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

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
