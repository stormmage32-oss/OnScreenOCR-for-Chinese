"""Shared colours and widget styles for the app's windows."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont

BG = "#F3F3F3"          # window background (Windows 11 mica-ish grey)
SURFACE = "#FFFFFF"
BORDER = "#E0E0E0"
BORDER_HOVER = "#C4C4C4"
TEXT = "#1B1B1B"
MUTED = "#616161"
FAINT = "#A0A0A0"
ACCENT = "#0F6CBD"      # Windows accent blue
ACCENT_HOVER = "#115EA3"
ACCENT_PRESSED = "#0C3B5E"
DANGER = "#C42B1C"
SUCCESS = "#0F7B0F"
CJK_FONT = "Microsoft YaHei UI"

BASE_QSS = f"""
QLabel {{ background: transparent; color: {TEXT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px 2px 2px 0; }}
QScrollBar::handle:vertical {{ background: #C8C8C8; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: #A8A8A8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QLineEdit {{ background: {SURFACE}; border: 1px solid {BORDER}; border-bottom: 1px solid #8A8A8A;
            border-radius: 4px; padding: 6px 9px; color: {TEXT}; font-size: 12px;
            selection-background-color: {ACCENT}; }}
QLineEdit:focus {{ border-bottom: 2px solid {ACCENT}; }}
QLineEdit:disabled {{ color: {FAINT}; background: #F9F9F9; border-bottom-color: {BORDER}; }}

QPushButton#btn {{ background: {SURFACE}; border: 1px solid {BORDER}; border-bottom-color: #CFCFCF;
                  border-radius: 4px; color: {TEXT}; font-size: 12px; padding: 6px 14px; }}
QPushButton#btn:hover {{ background: #F9F9F9; }}
QPushButton#btn:pressed {{ background: #F0F0F0; color: {MUTED}; }}
QPushButton#btn:disabled {{ color: {FAINT}; }}
QPushButton#btnAccent {{ background: {ACCENT}; border: 1px solid {ACCENT}; border-radius: 4px;
                        color: #FFFFFF; font-size: 12px; padding: 6px 14px; }}
QPushButton#btnAccent:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#btnAccent:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#btnAccent:disabled {{ background: #E0E0E0; border-color: #E0E0E0; color: {FAINT}; }}
QPushButton#btnDanger {{ background: transparent; border: 1px solid transparent; border-radius: 4px;
                        color: {DANGER}; font-size: 12px; padding: 6px 10px; }}
QPushButton#btnDanger:hover {{ background: #FDE7E9; }}
QPushButton#btnDanger:disabled {{ color: {FAINT}; }}
"""


def app_icon_pixmap(size=32):
    """Plain app icon: dark rounded square with 'OCR'. Used for window and tray."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#202020"))
    p.drawRoundedRect(0, 0, size, size, size * 0.2, size * 0.2)
    p.setPen(QColor("#FFFFFF"))
    f = QFont("Segoe UI")
    f.setPixelSize(max(8, int(size * 0.34)))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "OCR")
    p.end()
    return pm
