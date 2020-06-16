import os
from pickle import dump, load

KEY = 89

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
