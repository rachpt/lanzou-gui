'''
QSS 样式
'''

from lanzou.debug import BG_IMG
from platform import system as platform


jobs_btn_redo_style = '''
QPushButton {
    color: white;
    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 #38d,
        stop: 0.1 #93e, stop: 0.49 #77c, stop: 0.5 #16b, stop: 1 #07c);
    border-width: 1px;
    border-color: #339;
    border-style: solid;
    border-radius: 7;
    padding: 3px;
    font-size: 13px;
    padding-left: 5px;
    padding-right: 5px;
    min-width: 20px;
    min-height: 14px;
    max-height: 14px;
}
'''

jobs_btn_completed_style = '''
QPushButton {
    color: white;
    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 #18d,
        stop: 0.1 #9ae, stop: 0.49 #97c, stop: 0.5 #16b, stop: 1 #77c);
    border-width: 1px;
    border-color: #339;
    border-style: solid;
    border-radius: 7;
    padding: 3px;
    font-size: 13px;
    padding-left: 5px;
    padding-right: 5px;
    min-width: 20px;
    min-height: 14px;
    max-height: 14px;
}
'''

jobs_btn_delete_style = '''
QPushButton {
    color: white;
    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 #f00,
        stop: 0.25 #008080, stop: 0.49 #97c, stop: 0.5 #16b, stop: 1 #f00);
    border-width: 1px;
    border-color: #339;
    border-style: solid;
    border-radius: 7;
    padding: 3px;
    font-size: 13px;
    padding-left: 5px;
    padding-right: 5px;
    min-width: 20px;
    min-height: 14px;
    max-height: 14px;
}
'''

jobs_btn_processing_style = '''
QPushButton {
    color: white;
    background-color: QLinearGradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 rgba(9, 41, 4, 255), stop:0.085 rgba(2, 79, 0, 255), stop:0.19 rgba(50, 147, 22, 255), stop:0.275 rgba(236, 191, 49, 255), stop:0.39 rgba(243, 61, 34, 255), stop:0.555 rgba(135, 81, 60, 255), stop:0.667 rgba(121, 75, 255, 255), stop:0.825 rgba(164, 255, 244, 255), stop:0.885 rgba(104, 222, 71, 255), stop:1 rgba(93, 128, 0, 255));
    border-width: 1px;
    border-color: #339;
    border-style: solid;
    border-radius: 7;
    padding: 3px;
    font-size: 13px;
    padding-left: 5px;
    padding-right: 5px;
    min-width: 20px;
    min-height: 14px;
    max-height: 14px;
}
'''

jobs_btn_queue_style = '''
QPushButton {
    color: white;
    background-color: QLinearGradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 rgba(124, 252, 0, 255), stop:0.085 rgba(186, 85, 211, 255), stop:0.19 rgba(148, 0, 211, 255), stop:0.275 rgba(255,20,147, 255), stop:0.39 rgba(112,128,144, 255), stop:0.555 rgba(112,128,144, 255), stop:0.667 rgba(255,20,147, 255), stop:0.825 rgba(148, 0, 211, 255), stop:0.885 rgba(186, 85, 211, 255), stop:1 rgba(124, 252, 0, 255));
    border-width: 1px;
    border-color: #339;
    border-style: solid;
    border-radius: 7;
    padding: 3px;
    font-size: 13px;
    padding-left: 5px;
    padding-right: 5px;
    min-width: 20px;
    min-height: 14px;
    max-height: 14px;
}
'''

qssStyle = '''
QPushButton {
    background-color: rgba(255, 130, 71, 100);
}
#table_share, #table_jobs, #table_disk, #table_rec {
    background-color: rgba(255, 255, 255, 150);
}
QTabWidget::pane {
    border: 1px;
    /* background:transparent;  # 完全透明 */
    background-color: rgba(255, 255, 255, 90);
}
QTabWidget::tab-bar {
    background:transparent;
    subcontrol-position:center;
}
QTabBar::tab {
    min-width:150px;
    min-height:30px;
    background:transparent;
}
QTabBar::tab:selected {
    color: rgb(153, 50, 204);
    background:transparent;
    font-weight:bold;
}
QTabBar::tab:!selected {
    color: rgb(28, 28, 28);
    background:transparent;
}
QTabBar::tab:hover {
    color: rgb(0, 0, 205);
    background:transparent;
}
#tabWidget QTabBar{
    background-color: #AEEEEE;
}
/*提取界面文字颜色*/
#label_share_url {
    color: rgb(255,255,60);
}
#label_dl_path {
    color: rgb(255,255,60);
}
/*网盘界面文字颜色*/
#label_disk_loc {
    color: rgb(0,0,0);
    font-weight:bold;
}
#disk_tab {
    background-color: rgba(255, 255, 255, 120);
}
/*状态栏隐藏控件分隔符*/
#statusbar {
    font-size: 14px;
    color: white;
}
#msg_label, #msg_movie_lb {
    font-size: 14px;
    color: white;
    background:transparent;
}
QStatusBar::item {
    border: None;
}
/*菜单栏*/
#menubar {
    background-color: transparent;
}
QMenuBar::item {
    color:pink;
    margin-top:4px;
    spacing: 3px;
    padding: 1px 10px;
    background: transparent;
    border-radius: 4px;
}
/* when selected using mouse or keyboard */
QMenuBar::item:selected {
    color: white;
    background: #a8a8a8;
}
QMenuBar::item:pressed {
    color: lightgreen;
    background: #888888;
}
'''

if platform() == 'Darwin':  # MacOS 不使用自定义样式
    qssStyle = ''
else:
    qssStyle = qssStyle + f"""
    #MainWindow {{
        border-image:url({BG_IMG});
    }}"""


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
#btn_chooseMultiFile, #btn_chooseDir {
    min-width: 90px;
    max-width: 90px;
}
"""

dialog_qss_style = others_style + btn_style
# https://thesmithfam.org/blog/2009/09/10/qt-stylesheets-tutorial/
