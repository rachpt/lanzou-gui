'''
重新封装的控件
'''

import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout, QPalette, QFontMetrics, QIcon, QStandardItem
from PyQt6.QtWidgets import (QApplication, QAbstractItemView, QStyle, QListView, QLineEdit, QTableView,
                             QPushButton, QStyledItemDelegate, QStyleOptionViewItem, QTextEdit, QSizePolicy)

from lanzou.debug import SRC_DIR


def set_file_icon(name):
    suffix = name.split(".")[-1]
    ico_path = SRC_DIR + f"{suffix}.gif"
    if os.path.isfile(ico_path):
        return QIcon(ico_path)
    else:
        return QIcon(SRC_DIR + "file.ico")


class QDoublePushButton(QPushButton):
    """加入了双击事件的按钮"""
    doubleClicked = pyqtSignal()
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        QPushButton.__init__(self, *args, **kwargs)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.clicked.emit)
        super().clicked.connect(self.checkDoubleClick)

    def checkDoubleClick(self):
        if self.timer.isActive():
            self.doubleClicked.emit()
            self.timer.stop()
        else:
            self.timer.start(250)


class MyLineEdit(QLineEdit):
    """添加单击事件的输入框，用于设置下载路径"""

    clicked = pyqtSignal()

    def __init__(self, parent):
        super(MyLineEdit, self).__init__(parent)

    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class MyListView(QListView):
    """加入拖拽功能的列表显示器"""
    drop_files = pyqtSignal(object)

    def __init__(self):
        QListView.__init__(self)

        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
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
    """添加单击事件的自动改变大小的文本输入框，用于显示描述与下载直链
    https://github.com/cameel/auto-resizing-text-edit
    https://gist.github.com/hahastudio/4345418
    """
    clicked = pyqtSignal()
    editingFinished = pyqtSignal()

    def __init__(self, parent=None):
        super(AutoResizingTextEdit, self).__init__(parent)

        # This seems to have no effect. I have expected that it will cause self.hasHeightForWidth()
        # to start returning True, but it hasn't - that's why I hardcoded it to True there anyway.
        # I still set it to True in size policy just in case - for consistency.
        size_policy = self.sizePolicy()
        size_policy.setHeightForWidth(True)
        size_policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        self.setSizePolicy(size_policy)
        self.textChanged.connect(self.updateGeometry)

        self._changed = False
        self.setTabChangesFocus(True)
        self.textChanged.connect(self._handle_text_changed)

    def setMinimumLines(self, num_lines):
        """ Sets minimum widget height to a value corresponding to specified number of lines
            in the default font. """

        self.setMinimumSize(self.minimumSize().width(), self.lineCountToWidgetHeight(num_lines))

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
        if QMouseEvent.button() == Qt.MouseButton.LeftButton:
            if not self.toPlainText():
                self.clicked.emit()

    def lineCountToWidgetHeight(self, num_lines):
        """ Returns the number of pixels corresponding to the height of specified number of lines
            in the default font. """

        # ASSUMPTION: The document uses only the default font

        assert num_lines >= 0

        widget_margins = self.contentsMargins()
        document_margin = self.document().documentMargin()
        font_metrics = QFontMetrics(self.document().defaultFont())

        # font_metrics.lineSpacing() is ignored because it seems to be already included in font_metrics.height()
        return (
            widget_margins.top() +
            document_margin +
            max(num_lines, 1) * font_metrics.height() +
            self.document().documentMargin() +
            widget_margins.bottom()
        )

    def focusOutEvent(self, event):
        if self._changed:
            self.editingFinished.emit()
        super(AutoResizingTextEdit, self).focusOutEvent(event)

    def _handle_text_changed(self):
        self._changed = True


class TableDelegate(QStyledItemDelegate):
    """Table 富文本"""
    def __init__(self, parent=None):
        super(TableDelegate, self).__init__(parent)
        self.doc = QTextDocument(self)

    def paint(self, painter, option, index):
        painter.save()
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        self.doc.setHtml(options.text)
        options.text = ""  # 原字符
        style = QApplication.style() if options.widget is None else options.widget.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()

        if option.state & QStyle.StateFlag.State_Selected:
            ctx.palette.setColor(QPalette.ColorRole.Text, option.palette.color(
                QPalette.ColorGroup.Active, QPalette.ColorRole.HighlightedText))
        else:
            ctx.palette.setColor(QPalette.ColorRole.Text, option.palette.color(
                QPalette.ColorGroup.Active, QPalette.ColorRole.Text))

        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, options)

        the_fuck_your_shit_up_constant = 3  # ￣へ￣ #
        margin = (option.rect.height() - options.fontMetrics.height()) // 2
        margin = margin - the_fuck_your_shit_up_constant
        text_rect.setTop(text_rect.top() + margin)

        painter.translate(text_rect.topLeft())
        painter.setClipRect(text_rect.translated(-text_rect.topLeft()))
        self.doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        self.doc.setHtml(options.text)
        self.doc.setTextWidth(options.rect.width())
        return QSize(self.doc.idealWidth(), self.doc.size().height())


class MyStandardItem(QStandardItem):
    def __lt__(self, other):
        if self.data(Qt.ItemDataRole.UserRole) and other.data(Qt.ItemDataRole.UserRole):
            return self.data(Qt.ItemDataRole.UserRole) < other.data(Qt.ItemDataRole.UserRole)
        else:  # 没有setData并设置UserRole，则使用默认的方式进行比较排序
            return self.text() < other.text()


class MyTableView(QTableView):
    """加入拖拽功能的表格显示器"""
    drop_files = pyqtSignal(object)

    def __init__(self, parent):
        super(MyTableView, self).__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
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
