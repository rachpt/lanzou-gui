import os
from pickle import dump, load
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QLine, QPoint
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel, QPixmap, QLinearGradient, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import (QAbstractItemView, QPushButton, QFileDialog, QLineEdit, QDialog, QLabel, QFormLayout,
                             QTableView, QTextEdit, QGridLayout, QListView, QDialogButtonBox, QVBoxLayout, QHBoxLayout,
                             QComboBox, QCheckBox,  QSizePolicy, QMainWindow)


def update_settings(config_file: str, up_info: dict, is_settings=False):
    """更新配置文件"""
    try:
        with open(config_file, "rb") as _file:
            _info = load(_file)
    except Exception:
        _info = {}
    if is_settings:
        try: _settings = _info["settings"]
        except Exception:
            _settings = {}
        _settings.update(up_info)
        _info.update(_settings)
    else:
        _info.update(up_info)
    with open(config_file, "wb") as _file:
        dump(_info, _file)

def set_file_icon(name):
    suffix = name.split(".")[-1]
    ico_path = "./src/{}.gif".format(suffix)
    if os.path.isfile(ico_path):
        return QIcon(ico_path)
    else:
        return QIcon("./src/file.ico")

btn_style = """
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
"""
others_style = """
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
#btn_chooseMutiFile, #btn_chooseDir {
    min-width: 90px;
    max-width: 90px;
}
"""
dialog_qss_style = others_style + btn_style
# https://thesmithfam.org/blog/2009/09/10/qt-stylesheets-tutorial/


class MyLineEdit(QLineEdit):
    """添加单击事件的输入框，用于设置下载路径"""

    clicked = pyqtSignal()

    def __init__(self, parent):
        super(MyLineEdit, self).__init__(parent)

    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.LeftButton:
            self.clicked.emit()


class MyTableView(QTableView):
    """加入拖拽功能的表格显示器"""
    drop_files = pyqtSignal(object)

    def __init__(self, parent):
        super(MyTableView, self).__init__(parent)

        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        m = event.mimeData()
        if m.hasUrls():
            for url in m.urls():
                if url.isLocalFile():
                    event.accept()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.source():
            QListView.dropEvent(self, event)
        else:
            m = event.mimeData()
            if m.hasUrls():
                urls = [url.toLocalFile() for url in m.urls() if url.isLocalFile()]
                if urls:
                    self.drop_files.emit(urls)
                    event.acceptProposedAction()


class MyListView(QListView):
    """加入拖拽功能的列表显示器"""
    drop_files = pyqtSignal(object)

    def __init__(self):
        QListView.__init__(self)

        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        m = event.mimeData()
        if m.hasUrls():
            for url in m.urls():
                if url.isLocalFile():
                    event.accept()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.source():
            QListView.dropEvent(self, event)
        else:
            m = event.mimeData()
            if m.hasUrls():
                urls = [url.toLocalFile() for url in m.urls() if url.isLocalFile()]
                if urls:
                    self.drop_files.emit(urls)
                    event.acceptProposedAction()


class AutoResizingTextEdit(QTextEdit):
    """添加单击事件的自动改变大小的文本输入框，用于显示描述与下载直链"""
    clicked = pyqtSignal()

    def __init__(self, parent = None):
        super(AutoResizingTextEdit, self).__init__(parent)

        # This seems to have no effect. I have expected that it will cause self.hasHeightForWidth()
        # to start returning True, but it hasn't - that's why I hardcoded it to True there anyway.
        # I still set it to True in size policy just in case - for consistency.
        size_policy = self.sizePolicy()
        size_policy.setHeightForWidth(True)
        size_policy.setVerticalPolicy(QSizePolicy.Preferred)
        self.setSizePolicy(size_policy)

        self.textChanged.connect(lambda: self.updateGeometry())

    def setMinimumLines(self, num_lines):
        """ Sets minimum widget height to a value corresponding to specified number of lines
            in the default font. """

        self.setMinimumSize(self.minimumSize().width(), self.lineCountToWidgetHeight(num_lines))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        margins = self.contentsMargins()

        if width >= margins.left() + margins.right():
            document_width = width - margins.left() - margins.right()
        else:
            # If specified width can't even fit the margin, there's no space left for the document
            document_width = 0

        # Cloning the whole document only to check its size at different width seems wasteful
        # but apparently it's the only and preferred way to do this in Qt >= 4. QTextDocument does not
        # provide any means to get height for specified width (as some QWidget subclasses do).
        # Neither does QTextEdit. In Qt3 Q3TextEdit had working implementation of heightForWidth()
        # but it was allegedly just a hack and was removed.
        #
        # The performance probably won't be a problem here because the application is meant to
        # work with a lot of small notes rather than few big ones. And there's usually only one
        # editor that needs to be dynamically resized - the one having focus.
        document = self.document().clone()
        document.setTextWidth(document_width)

        return margins.top() + document.size().height() + margins.bottom()

    def sizeHint(self):
        original_hint = super(AutoResizingTextEdit, self).sizeHint()
        return QSize(original_hint.width(), self.heightForWidth(original_hint.width()))

    
    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.LeftButton:
            if not self.toPlainText():
                self.clicked.emit()

    def lineCountToWidgetHeight(self, num_lines):
        """ Returns the number of pixels corresponding to the height of specified number of lines
            in the default font. """

        # ASSUMPTION: The document uses only the default font

        assert num_lines >= 0

        widget_margins  = self.contentsMargins()
        document_margin = self.document().documentMargin()
        font_metrics    = QFontMetrics(self.document().defaultFont())

        # font_metrics.lineSpacing() is ignored because it seems to be already included in font_metrics.height()
        return (
            widget_margins.top()                      +
            document_margin                           +
            max(num_lines, 1) * font_metrics.height() +
            self.document().documentMargin()          +
            widget_margins.bottom()
        )

        return QSize(original_hint.width(), minimum_height_hint)


class LoginDialog(QDialog):
    """登录对话框"""

    clicked_ok = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._user = ""
        self._pwd = ""
        self._cookie = {}
        self.initUI()
        self.setStyleSheet(dialog_qss_style)
        self.setMinimumWidth(350)
        # 信号
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.cookie_ed.textChanged.connect(self.set_cookie)

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
        if self._cookie:
            _text = str(";".join([str(k) +'='+ str(v) for k,v in self._cookie.items()]))
            self.cookie_ed.setPlainText(_text)
        else:
            self.cookie_ed.setPlainText("")

    def initUI(self):
        self.setWindowTitle("登录蓝奏云")
        self.setWindowIcon(QIcon("./src/login.ico"))
        logo = QLabel()
        logo.setPixmap(QPixmap("./src/logo3.gif"))
        logo.setStyleSheet("background-color:rgb(0,153,255);")
        logo.setAlignment(Qt.AlignCenter)
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
        notice = "如果由于滑动验证，无法使用用户名与密码登录，则需要输入cookie，自行使用浏览器获取，\n" \
            "cookie会保持在本地，下次使用。其格式如下：\n\n key1=value1; key2=value2"
        self.cookie_ed.setPlaceholderText(notice)
        self.cookie_lb.setBuddy(self.cookie_ed)

        self.show_input_cookie_btn = QPushButton("显示Cookie输入框")
        self.show_input_cookie_btn.setToolTip(notice)
        self.show_input_cookie_btn.setStyleSheet("QPushButton {min-width: 110px;max-width: 110px;}")
        self.show_input_cookie_btn.clicked.connect(self.change_show_input_cookie)
        self.ok_btn = QPushButton("登录")
        self.ok_btn.clicked.connect(self.change_ok_btn)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.change_cancel_btn)

        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.addRow(self.name_lb, self.name_ed)
        self.form.addRow(self.pwd_lb, self.pwd_ed)

        hbox = QHBoxLayout()
        hbox.addWidget(self.show_input_cookie_btn)
        hbox.addStretch(1)
        hbox.addWidget(self.ok_btn)
        hbox.addWidget(self.cancel_btn)
        vbox = QVBoxLayout()
        vbox.addWidget(logo)
        vbox.addStretch(1)
        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        self.default_var()

    def change_show_input_cookie(self):
        self.form.addRow(self.cookie_lb, self.cookie_ed)
        pass

    def set_user(self, user):
        self._user = user

    def set_pwd(self, pwd):
        self._pwd = pwd

    def set_cookie(self):
        cookies = self.cookie_ed.toPlainText()
        try:
            self._cookie = {kv.split("=")[0].strip(" "): kv.split("=")[1].strip(" ") for kv in cookies.split(";")}
        except Exception:
            self._cookie = None

    def change_cancel_btn(self):
        self.default_var()
        self.close()

    def change_ok_btn(self):
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
        self.initUI()
        self.set_size()
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, folder_name, files):
        self.setWindowTitle("上传文件至 ➩ " + str(folder_name))
        if files:
            self.selected = files
            self.show_selected()
        self.exec()

    def initUI(self):
        self.setWindowTitle("上传文件")
        self.setWindowIcon(QIcon("./src/upload.ico"))
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./src/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)

        # btn 1
        self.btn_chooseDir = QPushButton("选择文件夹", self)
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setIcon(QIcon("./src/folder.gif"))

        # btn 2
        self.btn_chooseMutiFile = QPushButton("选择多文件", self)
        self.btn_chooseDir.setObjectName("btn_chooseMutiFile")
        self.btn_chooseMutiFile.setObjectName("btn_chooseMutiFile")
        self.btn_chooseMutiFile.setIcon(QIcon("./src/file.ico"))

        # btn 3
        self.btn_deleteSelect = QPushButton("移除", self)
        self.btn_deleteSelect.setObjectName("btn_deleteSelect")
        self.btn_deleteSelect.setIcon(QIcon("./src/delete.ico"))
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
        hbox_head.addWidget(self.btn_chooseMutiFile)
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
        self.btn_chooseMutiFile.clicked.connect(self.slot_btn_chooseMutiFile)
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
            self.resize(120+w*7, h*30)
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
                self.model.appendRow(QStandardItem(QIcon("./src/file.ico"), item))
            else:
                self.model.appendRow(QStandardItem(QIcon("./src/folder.gif"), item))
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
        self.show_selected()

    def slot_btn_chooseMutiFile(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择多文件", self.cwd, "All Files (*)")
        if len(files) == 0:
            return
        for _file in files:
            if _file not in self.selected:
                self.selected.append(_file)
        self.show_selected()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:  # delete
            self.slot_btn_deleteSelect()

class InfoDialog(QDialog):
    """文件信息对话框"""

    get_dl_link = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.infos = None
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def update_ui(self):
        self.tx_dl_link.setPlaceholderText("单击获取")
        self.tx_name.setText(self.infos[1])
        if self.infos[2]:
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

        if self.infos[2]:
            self.tx_size.setText(self.infos[2])
            self.lb_size.setVisible(True)
            self.tx_size.setVisible(True)
        else:
            self.tx_size.setVisible(False)
            self.lb_size.setVisible(False)

        if self.infos[3]:
            self.lb_time.setVisible(True)
            self.tx_time.setVisible(True)
            self.tx_time.setText(self.infos[3])
        else:
            self.lb_time.setVisible(False)
            self.tx_time.setVisible(False)

        if self.infos[4]:
            self.lb_dl_count.setVisible(True)
            self.tx_dl_count.setVisible(True)
            self.tx_dl_count.setText(str(self.infos[4]))
        else:
            self.tx_dl_count.setVisible(False)
            self.lb_dl_count.setVisible(False)

        if self.infos[5]:
            self.tx_pwd.setText(self.infos[5])
            self.tx_pwd.setPlaceholderText("")
        else:
            self.tx_pwd.setText("")
            self.tx_pwd.setPlaceholderText("无")
        
        if self.infos[6]:
            self.tx_desc.setText(self.infos[6])
            self.tx_desc.setPlaceholderText("")
        else:
            self.tx_desc.setText("")
            self.tx_desc.setPlaceholderText("无")

        self.tx_share_url.setText(self.infos[7])

    def set_values(self, infos):
        self.infos = infos
        self.update_ui()
        self.exec()

    def call_get_dl_link(self):
        url = self.tx_share_url.text()
        pwd = self.tx_pwd.text()
        self.get_dl_link.emit(url, pwd)
        self.tx_dl_link.setPlaceholderText("后台获取中，请稍后！")

    def initUI(self):
        self.setWindowIcon(QIcon("./src/share.ico"))
        self.setWindowTitle("文件信息")
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.rejected.connect(self.reject)

        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./src/q9.gif"))
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("background-color:rgb(255,204,51);")

        self.lb_name = QLabel()
        self.lb_name.setText("文件名：")
        self.tx_name = QLineEdit()
        self.tx_name.setReadOnly(True)

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

        self.lb_desc = QLabel()
        self.lb_desc.setText("文件描述：")
        self.tx_desc = AutoResizingTextEdit()
        self.tx_desc.setReadOnly(True)

        self.lb_dl_link = QLabel()
        self.lb_dl_link.setText("下载直链：")
        self.tx_dl_link = AutoResizingTextEdit(self)
        self.tx_dl_link.setPlaceholderText("单击获取")
        self.tx_dl_link.clicked.connect(self.call_get_dl_link)
        self.tx_dl_link.setReadOnly(True)

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
        form.addRow(self.lb_desc, self.tx_desc)
        form.addRow(self.lb_dl_link, self.tx_dl_link)
        vbox.addLayout(form)
        vbox.addStretch(1)
        vbox.addWidget(self.buttonBox)

        self.setLayout(vbox)


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
        self.setWindowIcon(QIcon("./src/desc.ico"))
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
        if self.infos:
            self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("")  # 去除新建文件夹影响
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)  # 去除新建文件夹影响
            self.setWindowTitle("修改文件夹名与描述")
            self.tx_name.setText(str(self.infos[1]))
            if self.infos[6]:
                self.tx_desc.setText(str(self.infos[6]))
                self.tx_desc.setToolTip('原描述：' + str(self.infos[6]))
            else:
                self.tx_desc.setText("无")
                self.tx_desc.setToolTip('')
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
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("请先输入文件名！")
            self.tx_name.textChanged.connect(self.slot_new_ok_btn)
            self.tx_name.setPlaceholderText("不支持空格，如有会被自动替换成 _")
            self.tx_name.setFocusPolicy(Qt.StrongFocus)
            self.tx_name.setReadOnly(False)
            self.tx_desc.setPlaceholderText("可选项，建议160字数以内。")
        if self.min_width < 400:
            self.min_width = 400
        self.resize(self.min_width, 200)

    def slot_new_ok_btn(self):
        """新建文件夹槽函数"""
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("")

    def btn_ok(self):
        new_name = self.tx_name.text()
        new_desc = self.tx_desc.toPlainText()
        if not self.infos:  # 在 work_id 新建文件夹
            if new_name:
                self.out.emit(("new", "", new_name, new_desc))
            else:
                return
        elif new_name != self.infos[1] or new_desc != self.infos[6]:
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
        self.setWindowIcon(QIcon("./src/password.ico"))
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
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

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
        self.setWindowIcon(QIcon("./src/move.ico"))
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
        f_icon = QIcon("./src/folder.gif")
        for f_name, fid in self.dirs.items():
            if len(f_name) > 50:  # 防止文件夹名字过长？
                f_name = f_name[:47] + "..."
            self.tx_new_path.addItem(f_icon, "id：{:>8}，name：{}".format(fid, f_name))

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

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

    def initUI(self):
        self.setWindowTitle("确认删除")
        self.setWindowIcon(QIcon("./src/delete.ico"))
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
                self.model.appendRow(QStandardItem(set_file_icon(i[1]), i[1]))
            else:
                self.model.appendRow(QStandardItem(QIcon("./src/folder.gif"), i[1]))
            self.out.append({'fid': i[0], 'is_file': True if i[2] else False, 'name': i[1]})  # id，文件标示, 文件名
            count += 1
            if max_len < len(i[1]):  # 使用最大文件名长度
                max_len = len(i[1])
        self.list_view.setModel(self.model)

        self.lb_name = QLabel("尝试删除以下{}个文件(夹)：".format(count))
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

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
        self.lb_name_text.setText(f"{version}  (点击检查更新)")  # 更新版本

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
        about = f'本项目使用PyQt5实现图形界面，可以完成蓝奏云的大部分功能<br/> \
    得益于 <a href="{self._api_url}">API</a> 的功能，可以间接突破单文件最大 100MB 的限制，同时增加了批量上传/下载的功能<br/> \
Python 依赖见<a href="{self._github }/blob/master/requirements.txt">requirements.txt</a>，\
<a href="{self._github}/releases">releases</a> 有打包好了的 Windows 可执行程序，但可能不是最新的'
        project_url = f'<a href="{self._home_page}">主页</a> | <a href="{self._github}">repo</a> | \
                        <a href="{self._gitee}">mirror repo</a>'
        self.logo = QLabel()  # logo
        self.logo.setPixmap(QPixmap("./src/logo2.gif"))
        self.logo.setStyleSheet("background-color:rgb(255,255,255);")
        self.logo.setAlignment(Qt.AlignCenter)
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
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.setStyleSheet(btn_style)

        self.line = QLine(QPoint(), QPoint(550, 0))
        self.lb_line = QLabel()
        self.lb_line.setText('<html><hr /></html>')

        vbox = QVBoxLayout()
        vbox.addWidget(self.logo)
        vbox.addStretch(1)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.setFormAlignment(Qt.AlignLeft)
        self.form.setHorizontalSpacing(40)
        self.form.setVerticalSpacing(15)
        self.form.addRow(self.lb_name, self.lb_name_text)
        self.form.addRow(self.lb_update, self.lb_update_url)
        self.form.addRow(self.lb_author, self.lb_author_mail)
        self.form.addRow(self.lb_about, self.lb_about_text)
        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addWidget(self.lb_line)
        donate = QLabel()
        donate.setText("<b>捐助我</b>&nbsp;如果你愿意")
        donate.setAlignment(Qt.AlignCenter)
        hbox = QHBoxLayout()
        hbox.addStretch(2)
        for it in ["wechat", "alipay", "qqpay"]:
            lb = QLabel()
            lb.setPixmap(QPixmap(f"./src/{it}.jpg"))
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
            pen = QPen(Qt.red, 3)
            painter.setPen(pen)
            painter.drawLine(self.line)

class SettingDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, config_file: str, default_settings: dict, parent=None):
        super(SettingDialog, self).__init__(parent)
        self.cwd = os.getcwd()
        self._config_file = config_file
        self._default_settings = default_settings
        self.rar_tool = None
        self.download_threads = None
        self.max_size = None
        self.timeout = None
        self.guise_suffix = None
        self.rar_part_name = None
        self.dl_path = None
        self.time_fmt = False
        self.to_tary = False
        self.watch_clipboard = False
        self.initUI()
        self.set_values()
        self.setStyleSheet(dialog_qss_style)

    def open_dialog(self):
        """"打开前先更新一下显示界面"""
        self.set_values()
        self.exec()

    def read_values(self):
        """读取配置信息"""
        try:
            with open(self._config_file, "rb") as _file:
                configs = load(_file)
            settings = configs["settings"]
        except Exception:
            settings = self._default_settings
        return settings

    def show_values(self):
        """控件显示值"""
        self.download_threads_var.setText(str(self.download_threads))
        self.max_size_var.setText(str(self.max_size))
        self.timeout_var.setText(str(self.timeout))
        self.dl_path_var.setText(str(self.dl_path))
        self.time_fmt_box.setChecked(self.time_fmt)
        self.to_tray_box.setChecked(self.to_tray)
        self.watch_clipboard_box.setChecked(self.watch_clipboard)

    def set_values(self, reset=False):
        """设置控件对应变量初始值"""
        settings = self._default_settings if reset else self.read_values()
        self.download_threads = settings["download_threads"]
        self.max_size = settings["max_size"]
        self.timeout = settings["timeout"]
        self.dl_path = settings["dl_path"]
        self.time_fmt = settings["time_fmt"]
        self.to_tray = settings["to_tray"] if "to_tray" in settings else False
        self.watch_clipboard = settings["watch_clipboard"] if "watch_clipboard" in settings else False
        self.show_values()

    def get_values(self) -> dict:
        """读取控件值"""
        self.download_threads = int(self.download_threads_var.text())
        self.max_size = int(self.max_size_var.text())
        self.timeout = int(self.timeout_var.text())
        self.dl_path = str(self.dl_path_var.text())
        return {"download_threads": self.download_threads, "to_tray": self.to_tray,
                "max_size": self.max_size, "dl_path": self.dl_path, "watch_clipboard": self.watch_clipboard,
                "timeout": self.timeout, "time_fmt": self.time_fmt}

    def initUI(self):
        self.setWindowTitle("设置")
        logo = QLabel()  # logo
        logo.setPixmap(QPixmap("./src/logo2.gif"))
        logo.setStyleSheet("background-color:rgb(255,255,255);")
        logo.setAlignment(Qt.AlignCenter)
        self.download_threads_lb = QLabel("同时下载文件数")  # about
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
        self.dl_path_lb = QLabel("下载保存路径")
        self.dl_path_var = MyLineEdit(self)
        self.dl_path_var.clicked.connect(self.set_download_path)
        self.time_fmt_box = QCheckBox("使用[年-月-日]时间格式")
        self.to_tray_box = QCheckBox("关闭到系统托盘")
        self.watch_clipboard_box = QCheckBox("监听系统剪切板")
        self.time_fmt_box.toggle()
        self.time_fmt_box.stateChanged.connect(self.change_time_fmt)
        self.to_tray_box.stateChanged.connect(self.change_to_tray)
        self.watch_clipboard_box.stateChanged.connect(self.change_watch_clipboard)

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
        vbox.addLayout(hbox)
        vbox.addStretch(1)
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

    def set_download_path(self):
        """设置下载路径"""
        dl_path = QFileDialog.getExistingDirectory(self, "选择文件下载保存文件夹", self.cwd)
        dl_path = os.path.normpath(dl_path)  # windows backslash
        if dl_path == self.dl_path or dl_path == ".":
            return
        self.dl_path_var.setText(dl_path)
        self.dl_path = dl_path

    def slot_save(self):
        """保存槽函数"""
        update_settings(self._config_file, self.get_values(), is_settings=True)
        self.saved.emit()
        self.close()


class RecFolderDialog(QDialog):
    out = pyqtSignal(object)

    def __init__(self, files, parent=None):
        super(RecFolderDialog, self).__init__(parent)
        self.files = files
        self.initUI()
        self.setStyleSheet(others_style)

    def initUI(self):
        self.setWindowTitle("查看回收站文件夹内容")
        self.form = QVBoxLayout()
        for item in iter(self.files):
            ico = QPushButton(set_file_icon(item.name), item.name)
            ico.setStyleSheet("QPushButton {border:none; background:transparent; color:black;}")
            ico.adjustSize()
            it = QLabel(f"<font color='#CCCCCC'>({item.size})</font>")
            hbox = QHBoxLayout()
            hbox.addWidget(ico)
            hbox.addStretch(1)
            hbox.addWidget(it)
            self.form.addLayout(hbox)

        self.form.setSpacing(10)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.setStyleSheet(btn_style)
        self.buttonBox.rejected.connect(self.reject)

        vbox = QVBoxLayout()
        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addWidget(self.buttonBox)
        self.setLayout(vbox)
