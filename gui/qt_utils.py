import cv2
from PySide6 import QtCore, QtGui


def bgr_to_qimage(frame_bgr):
    if frame_bgr is None:
        return None
    h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    qimg = QtGui.QImage(rgb.data, w, h, rgb.strides[0], QtGui.QImage.Format_RGB888)
    return qimg.copy()


def frame_to_pixmap(frame_bgr, target_size):
    qimg = bgr_to_qimage(frame_bgr)
    if qimg is None:
        return None
    pixmap = QtGui.QPixmap.fromImage(qimg)
    return pixmap.scaled(
        target_size,
        QtCore.Qt.KeepAspectRatio,
        QtCore.Qt.SmoothTransformation,
    )

def build_stylesheet():
    return """
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #f5f1e8, stop:1 #e6dcc7);
    }
    QWidget {
        font-family: "Poppins","Nunito","DejaVu Sans";
        font-size: 12px;
        color: #1f2326;
    }
    QLabel#Title {
        font-size: 22px;
        font-weight: 600;
        color: #1f2326;
    }
    QLabel#Subtitle {
        font-size: 12px;
        color: #5a5e5a;
    }
    QLabel[role="muted"] {
        color: #5a5e5a;
    }
    QLabel[chip="true"] {
        background: #e8dcc6;
        border-radius: 8px;
        padding: 4px 8px;
        color: #2d2a24;
    }
    QFrame[card="true"] {
        background: #fffaf2;
        border: 1px solid #e6dbc9;
        border-radius: 12px;
    }
    QLabel[role="preview"] {
        background: #1a1f21;
        border: 1px solid #2a2f31;
        border-radius: 12px;
    }
    QLineEdit {
        background: #fffaf2;
        border: 1px solid #e0d6c5;
        border-radius: 8px;
        padding: 6px 8px;
    }
    QTableWidget {
        background: #fffaf2;
        border: 1px solid #e0d6c5;
        border-radius: 10px;
        gridline-color: #eadfcd;
    }
    QHeaderView::section {
        background: #e8dcc6;
        padding: 6px;
        border: none;
        font-weight: 600;
    }
    QTabBar::tab {
        background: #e8dcc6;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        padding: 8px 16px;
        margin-right: 6px;
    }
    QTabBar::tab:selected {
        background: #fffaf2;
    }
    QTabWidget::pane {
        border: 1px solid #e0d6c5;
        border-radius: 12px;
        padding: 8px;
    }
    QLabel[role="section"] {
        font-size: 11px;
        font-weight: 600;
        color: #6a5f52;
    }
    QPushButton {
        background: #1f2a2c;
        color: #f7f3ea;
        border-radius: 10px;
        padding: 8px 14px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #27373a;
    }
    QPushButton:disabled {
        background: #b7b0a2;
        color: #706a5f;
    }
    QPushButton[kind="secondary"] {
        background: #d8c7a7;
        color: #2e2a24;
    }
    QPushButton[kind="secondary"]:hover {
        background: #c9b38b;
    }
    QPushButton[kind="danger"] {
        background: #b04a3a;
        color: #fff7f0;
    }
    QCheckBox {
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid #b9ad9a;
        background: #fffaf2;
    }
    QCheckBox::indicator:checked {
        background: #1f2a2c;
        border: 1px solid #1f2a2c;
    }
    """


def apply_theme(app):
    if app is None:
        return
    app.setStyleSheet(build_stylesheet())

