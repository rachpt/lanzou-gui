import os
from pickle import dump, load
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel, QPixmap, QLinearGradient
from PyQt5.QtWidgets import (QAbstractItemView, QPushButton, QFileDialog, QLineEdit, QDialog, QLabel, QFormLayout,
                             QTextEdit, QGridLayout, QListView, QDialogButtonBox, QVBoxLayout, QComboBox)

from Ui_share import Ui_Dialog


def update_settings(config_file: str, up_info: dict):
    """更新配置文件"""
    try:
        with open(config_file, "rb") as _file:
            _info = load(_file)
    except Exception:
        _info = {}
    _info.update(up_info)
    with open(config_file, "wb") as _file:
        dump(_info, _file)


dialog_qss_style = """
QLabel {
    font-weight: 400;
    font-size: 14px;
}
QLineEdit {
    padding: 1px;
    border-style: solid;
    border: 2px solid gray;
    border-radius: 8px;
}
QTextEdit {
    padding: 1px;
    border-style: solid;
    border: 2px solid gray;
    border-radius: 8px;
}
QPushButton {
    color: white;
    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 #88d,
        stop: 0.1 #99e, stop: 0.49 #77c, stop: 0.5 #66b, stop: 1 #77c);
    border-width: 1px;
    border-color: #339;
    border-style: solid;
    border-radius: 7;
    padding: 3px;
    font-size: 13px;
    padding-left: 5px;
    padding-right: 5px;
    min-width: 70px;
    max-width: 70px;
    min-height: 14px;
    max-height: 14px;
}
#btn_chooseMutiFile, #btn_chooseDir {
    min-width: 90px;
    max-width: 90px;
}
"""
# https://thesmithfam.org/blog/2009/09/10/qt-stylesheets-tutorial/


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

    clicked_ok = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._user = ""
        self._pwd = ""
        self._cookie = ""
        self.initUI()
        self.setStyleSheet(dialog_qss_style)
        self.setMinimumWidth(300)
        # 信号
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.cookie_ed.textChanged.connect(self.set_cookie)

        self.buttonBox.accepted.connect(self._ok)
        self.buttonBox.rejected.connect(self._cancel)

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
        self.setWindowIcon(QIcon("./icon/login.ico"))
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)
        self.name_lb = QLabel("&User")
        self.name_lb.setAlignment(Qt.AlignCenter)
        self.name_ed = QLineEdit()
        self.name_lb.setBuddy(self.name_ed)

        self.pwd_lb = QLabel("&Password")
        self.pwd_lb.setAlignment(Qt.AlignCenter)
        self.pwd_ed = QLineEdit()
        self.pwd_ed.setEchoMode(QLineEdit.Password)
        self.pwd_lb.setBuddy(self.pwd_ed)

        self.cookie_lb = QLabel("&Cookie")
        self.cookie_ed = QTextEdit()
        notice = "如果由于滑动验证，无法使用用户名与密码登录，则需要输入cookie，自行使用浏览器获取，" \
            "cookie会保持在本地，下次使用。其格式如下：\n\n key1=value1; key2=value2"
        self.cookie_ed.setPlaceholderText(notice)
        self.cookie_lb.setBuddy(self.cookie_ed)

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        main_layout = QGridLayout()
        main_layout.addWidget(self.logo, 0, 0, 2, 4)
        main_layout.addWidget(self.name_lb, 2, 0)
        main_layout.addWidget(self.name_ed, 2, 1, 1, 3)
        main_layout.addWidget(self.pwd_lb, 3, 0)
        main_layout.addWidget(self.pwd_ed, 3, 1, 1, 3)
        # main_layout.addWidget(self.cookie_lb, 4, 0)  # cookie输入框
        # main_layout.addWidget(self.cookie_ed, 4, 1, 2, 3)
        main_layout.addWidget(self.buttonBox, 4, 2)
        self.setLayout(main_layout)
        self.default_var()

    def set_user(self, user):
        self._user = user

    def set_pwd(self, pwd):
        self._pwd = pwd

    def set_cookie(self):
        self._cookie = self.cookie_ed.toPlainText()

    def _cancel(self):
        self.default_var()
        self.close()

    def _ok(self):
        up_info = {"user": self._user, "pwd": self._pwd, "cookie": self._cookie}
        update_settings(self._config, up_info)
        self.clicked_ok.emit()
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
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, folder_name):
        self.setWindowTitle("上传文件至 ➩ " + str(folder_name))

    def initUI(self):
        self.setWindowTitle("上传文件")
        self.setWindowIcon(QIcon("./icon/upload.ico"))
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)

        # btn 1
        self.btn_chooseDir = QPushButton("选择文件夹", self)
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setIcon(QIcon("./icon/folder.gif"))

        # btn 2
        self.btn_chooseMutiFile = QPushButton("选择多文件", self)
        self.btn_chooseDir.setObjectName("btn_chooseMutiFile")
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
        rows = 10 if rows >= 10 else rows  # 限制最大高度
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

    def slot_btn_chooseDir(self):
        dir_choose = QFileDialog.getExistingDirectory(self, "选择文件夹", self.cwd)  # 起始路径

        if dir_choose == "":
            return
        if dir_choose not in self.selected:
            self.selected.append(dir_choose)
            self.model.appendRow(QStandardItem(QIcon("./icon/folder.gif"), dir_choose))
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
        self.setStyleSheet(dialog_qss_style)

    def initUI(self):
        self.setWindowTitle("文件信息" if self.infos[2] else "文件夹信息")
        self.setWindowIcon(QIcon("./icon/share.ico"))
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
    out = pyqtSignal(object)

    def __init__(self, parent=None):
        super(RenameDialog, self).__init__(parent)
        self.infos = None
        self.min_width = 400
        self.initUI()
        self.update_text()
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, infos):
        self.infos = infos
        self.update_text()  # 更新界面

    def initUI(self):
        self.setWindowIcon(QIcon("./icon/desc.ico"))
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
        if self.infos:
            self.setWindowTitle("修改文件夹名与描述")
            self.tx_name.setText(str(self.infos[1]))
            if self.infos[6]:
                self.tx_desc.setText("")
                self.tx_desc.setPlaceholderText(str(self.infos[6]))
            else:
                self.tx_desc.setPlaceholderText("无")
            self.min_width = len(str(self.infos[1])) * 8
            if self.infos[2]:  # 文件无法重命名，由 infos[2] size表示文件
                self.setWindowTitle("修改文件描述")
                self.tx_name.setFocusPolicy(Qt.NoFocus)
                self.tx_name.setReadOnly(True)
            else:
                self.tx_name.setFocusPolicy(Qt.StrongFocus)
                self.tx_name.setReadOnly(False)

        else:
            self.setWindowTitle("新建文件夹")
            self.tx_name.setText("")
            self.tx_name.setPlaceholderText("不支持空格，如有会被自动替换成 _")
            self.tx_name.setFocusPolicy(Qt.StrongFocus)
            self.tx_name.setReadOnly(False)
            self.tx_desc.setPlaceholderText("可选项，建议160字数以内。")
        if self.min_width < 400:
            self.min_width = 400
        self.resize(self.min_width, 200)

    def btn_ok(self):
        new_name = self.tx_name.text()
        new_desc = self.tx_desc.toPlainText()
        if not self.infos:  # 在 work_id 新建文件夹
            if new_name:
                self.out.emit(("new", "", new_name, new_desc))
            else:
                return
        elif new_name != self.infos[1] or(new_desc and new_desc != self.infos[6]):
            if self.infos[2]:  # 文件
                self.out.emit(("file", self.infos[0], new_name, new_desc))
            else:
                self.out.emit(("folder", self.infos[0], new_name, new_desc))


class SetPwdDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, parent=None):
        super(SetPwdDialog, self).__init__(parent)
        self.infos = None
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
        self.setWindowIcon(QIcon("./icon/password.ico"))
        self.lb_oldpwd = QLabel()
        self.lb_oldpwd.setText("当前提取码：")
        self.lb_oldpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_oldpwd = QLineEdit()
        # 当前提取码 只读
        self.tx_oldpwd.setFocusPolicy(Qt.NoFocus)
        self.tx_oldpwd.setReadOnly(True)
        self.lb_newpwd = QLabel()
        self.lb_newpwd.setText("新的提取码：")
        self.lb_newpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_newpwd = QLineEdit()
        
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
        self.buttonBox.accepted.connect(self.set_tip)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.rejected.connect(self.set_tip)
        self.setMinimumWidth(280)

    def update_text(self):
        if self.infos:
            if self.infos[5]:
                self.tx_oldpwd.setText(str(self.infos[5]))
                self.tx_oldpwd.setPlaceholderText("")
            else:
                self.tx_oldpwd.setText("")
                self.tx_oldpwd.setPlaceholderText("无")

            if self.infos[2]:  # 文件  通过size列判断是否为文件
                self.setWindowTitle("修改文件提取码")
                self.tx_newpwd.setPlaceholderText("2-6位字符,关闭请留空")
                self.tx_newpwd.setMaxLength(6)  # 最长6个字符
            else:  # 文件夹
                self.setWindowTitle("修改文件夹名提取码")
                self.tx_newpwd.setPlaceholderText("2-12位字符,关闭请留空")
                self.tx_newpwd.setMaxLength(12)  # 最长12个字符

    def btn_ok(self):
        new_pwd = self.tx_newpwd.text()
        if new_pwd != self.infos[5]:
            self.new_infos.emit((self.infos[0], new_pwd, self.infos[2]))  # 最后一位用于标示文件还是文件夹


class MoveFileDialog(QDialog):
    '''移动文件对话框'''
    new_infos = pyqtSignal(object)

    def __init__(self, infos, all_dirs_dict, parent=None):
        super(MoveFileDialog, self).__init__(parent)
        self.infos = infos
        self.dirs = all_dirs_dict
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def initUI(self):
        for i in self.infos:
            if not i[2]:  # 非文件
                self.infos.remove(i)
        self.setWindowTitle("移动文件")
        self.setWindowIcon(QIcon("./icon/move.ico"))
        self.lb_name = QLabel()
        self.lb_name.setText("文件路径：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        names = " | ".join([i[1] for i in self.infos])
        names_tip = "\n".join([i[1] for i in self.infos])
        self.tx_name.setText(names)
        self.tx_name.setToolTip(names_tip)
        # 只读
        self.tx_name.setFocusPolicy(Qt.NoFocus)
        self.tx_name.setReadOnly(True)
        self.lb_new_path = QLabel()
        self.lb_new_path.setText("目标文件夹：")
        self.lb_new_path.setAlignment(
            Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter
        )
        self.tx_new_path = QComboBox()
        f_icon = QIcon("./icon/folder.gif")
        for f_name, fid in self.dirs.items():
            if len(f_name) > 50:  # 防止文件夹名字过长？
                f_name = f_name[:47] + "..."
            self.tx_new_path.addItem(f_icon, "id：{:>8}，name：{}".format(fid, f_name))

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
        self.new_infos.emit([(info[0], selected, info[1]) for info in self.infos])


class DeleteDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(DeleteDialog, self).__init__(parent)
        self.infos = infos
        self.out = []
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def set_file_icon(self, name):
        suffix = name.split(".")[-1]
        ico_path = "./icon/{}.gif".format(suffix)
        if os.path.isfile(ico_path):
            return QIcon(ico_path)
        else:
            return QIcon("./icon/file.ico")

    def initUI(self):
        self.setWindowTitle("确认删除")
        self.setWindowIcon(QIcon("./icon/delete.ico"))
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
                self.model.appendRow(QStandardItem(QIcon("./icon/folder.gif"), i[1]))
            self.out.append({'fid': i[0], 'is_file': True if i[2] else False, 'name': i[1]})  # id，文件标示, 文件名
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


class AboutDialog(QDialog):
    out = pyqtSignal(object)

    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, version):
        self.lb_name_text.setText("<font color=blue>"+version+"</font>")  # 更新版本

    def initUI(self):
        about = '''
本项目使用PyQt5实现图形界面，可以完成蓝奏云的大部分功能<br/>

得益于 API 的功能，可以间接突破单文件最大 100MB 的限制，同时增加了批量上传/下载的功能<br/>

Python 依赖见<a href="https://github.com/rachpt/lanzou-gui/blob/master/requirements.txt">requirements.txt</a>，<a href="https://github.com/rachpt/lanzou-gui/releases">releases</a> 有打包好了的 Windows 可执行程序，但可能不是最新的
        '''
        project_url = '''
主 repo&nbsp; ： <a href="https://github.com/rachpt/lanzou-gui">https://github.com/rachpt/lanzou-gui</a><br/>
镜像 repo ： <a href="https://gitee.com/rachpt/lanzou-gui">https://gitee.com/rachpt/lanzou-gui</a>
        '''
        self.setWindowTitle("关于 lanzou-gui")
        self.logo = QLabel()  # logo
        self.logo.setPixmap(QPixmap("./icon/logo2.gif"))
        self.logo.setStyleSheet("background-color:rgb(255,255,255);")
        self.logo.setAlignment(Qt.AlignCenter)
        self.lb_name = QLabel("版本")  # 版本
        self.lb_name_text = QLabel("")  # 版本
        self.lb_about = QLabel("About")  # about
        self.lb_about_text = QTextEdit(about)  # about
        self.lb_about_text.setFocusPolicy(Qt.NoFocus)
        self.lb_about_text.setReadOnly(True)
        # self.lb_about_text.setOpenExternalLinks(True)
        self.lb_author = QLabel("Author")  # author
        self.lb_author_mail = QLabel("rachpt@126.com")  # author
        self.lb_update = QLabel("更新地址")  # 更新
        self.lb_update_url = QLabel(project_url)
        self.lb_update_url.setOpenExternalLinks(True)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.logo, 1, 0, 2, 3)
        self.grid.addWidget(self.lb_name, 3, 0)
        self.grid.addWidget(self.lb_name_text, 3, 1)
        self.grid.addWidget(self.lb_about, 4, 0)
        self.grid.addWidget(self.lb_about_text, 4, 1, 3, 2)
        self.grid.addWidget(self.lb_author, 7, 0)
        self.grid.addWidget(self.lb_author_mail, 7, 1)
        self.grid.addWidget(self.lb_update, 8, 0)
        self.grid.addWidget(self.lb_update_url, 8, 1, 2, 2)
        self.grid.addWidget(self.buttonBox, 10, 2)
        self.setLayout(self.grid)
        self.setFixedSize(660, 300)


class SettingDialog(QDialog):
    infos = pyqtSignal(str, dict)

    def __init__(self, config_file, parent=None):
        super(SettingDialog, self).__init__(parent)
        self._config_file = config_file
        self.rar_tool = None
        self.download_threads = None
        self.max_size = None
        self.timeout = None
        self.guise_suffix = None
        self.rar_part_name = None
        self.path = None
        self.initUI()
        self.read_values()
        self.setStyleSheet(dialog_qss_style)

    def read_values(self):
        try:
            with open(self._config_file, "rb") as _file:
                configs = load(_file)
            settings = configs["settings"]
            self.rar_tool = settings["rar_tool"]
            self.download_threads = settings["download_threads"]
            self.max_size = settings["max_size"]
            self.timeout = settings["timeout"]
            self.guise_suffix = settings["guise_suffix"]
            self.rar_part_name = settings["rar_part_name"]
            self.path = configs["path"]
            self.show_infos()
        except Exception:
            pass

    def show_infos(self):
        self.rar_tool_var.setText(self.rar_tool)
        self.download_threads_var.setText(str(self.download_threads))
        self.max_size_var.setText(str(self.max_size))
        self.timeout_var.setText(str(self.timeout))
        self.guise_suffix_var.setText(str(self.guise_suffix))
        self.rar_part_name_var.setText(str(self.rar_part_name))
        self.path_var.setText(str(self.path))

    def initUI(self):
        self.setWindowTitle("设置")
        self.logo = QLabel()  # logo
        self.logo.setPixmap(QPixmap("./icon/logo2.gif"))
        self.logo.setStyleSheet("background-color:rgb(255,255,255);")
        self.logo.setAlignment(Qt.AlignCenter)
        self.rar_tool = QLabel("rar路径")  # rar路径
        self.rar_tool_var = QLineEdit()
        self.download_threads = QLabel("同时下载文件数")  # about
        self.download_threads_var = QLineEdit()
        self.max_size = QLabel("分卷大小(MB)")
        self.max_size_var = QLineEdit()
        self.timeout = QLabel("请求超时(秒)")
        self.timeout_var = QLineEdit()
        self.guise_suffix = QLabel("假后缀")
        self.guise_suffix_var = QLineEdit()
        self.rar_part_name = QLabel("rar分卷名")
        self.rar_part_name_var =QLineEdit()
        self.path = QLabel("下载保存路径")
        self.path_var = QLineEdit()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.form = QFormLayout()
        self.form.setSpacing(10)
        self.form.addRow(self.rar_tool, self.rar_tool_var)
        self.form.addRow(self.download_threads, self.download_threads_var)
        self.form.addRow(self.max_size, self.max_size_var)
        self.form.addRow(self.timeout, self.timeout_var)
        self.form.addRow(self.guise_suffix, self.guise_suffix_var)
        self.form.addRow(self.rar_part_name, self.rar_part_name_var)
        self.form.addRow(self.path, self.path_var)

        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.logo)
        self.vbox.addLayout(self.form)
        self.vbox.addWidget(self.buttonBox)
        self.setLayout(self.vbox)
        self.setMinimumWidth(500)
