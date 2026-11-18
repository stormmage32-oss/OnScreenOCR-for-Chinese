"""Colour themes (light, dark, sepia) and the widget styles built from them.

Everything reads colours from `P` at the moment it builds a style or paints,
so `set_theme()` followed by re-applying a window's stylesheet is enough to
switch a window that is already open. Windows opened later pick it up anyway.
"""
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QPalette

CJK_FONT = "Microsoft YaHei UI"

THEMES = {
    "light": dict(
        BG="#F3F3F3", SURFACE="#FFFFFF", SURFACE_HOVER="#F9F9F9", SURFACE_PRESSED="#F0F0F0",
        BORDER="#E0E0E0", BORDER_HOVER="#C4C4C4", BORDER_BOTTOM="#CFCFCF", DIVIDER="#EDEDED",
        INPUT_LINE="#8A8A8A", DISABLED_BG="#F9F9F9", DISABLED_FILL="#DCDCDC",
        TEXT="#1B1B1B", MUTED="#616161", FAINT="#A0A0A0",
        ACCENT="#0F6CBD", ACCENT_HOVER="#115EA3", ACCENT_PRESSED="#0C3B5E", ACCENT_TEXT="#0F6CBD",
        ON_ACCENT="#FFFFFF", ON_ACCENT_MUTED="#CFE4F7",
        DANGER="#C42B1C", DANGER_BG="#FDE7E9", ACTIVE_BG="#FDF3F2", ACTIVE_BORDER="#E8B4AE",
        SUCCESS="#0F7B0F", SUCCESS_BG="#EAF5EA", SUCCESS_BORDER="#BFE0BF", SUCCESS_TEXT="#1F4D1F",
        ROW_HOVER="#F5F5F5", ROW_SELECTED="#EAF2FB",
        SCROLL="#C8C8C8", SCROLL_HOVER="#A8A8A8",
        TOGGLE_OFF="#8A8A8A", KNOB_OFF="#5F5F5F", TRACK="#E6E6E6", TRACK_KNOB_BORDER="#D0D0D0",
        CHIP_BG="rgba(20,20,20,225)", CHIP_TEXT="#FFFFFF", CHIP_KEY_BG="#F0F0F0", CHIP_KEY_TEXT="#141414",
        SELECT_DIM="#D4C5B0", SELECT_LABEL_BG="rgba(250,244,235,220)", SELECT_LABEL_TEXT="#4A3F35",
        DARK=False,
    ),
    "dark": dict(
        BG="#202020", SURFACE="#2B2B2B", SURFACE_HOVER="#323232", SURFACE_PRESSED="#272727",
        BORDER="#3B3B3B", BORDER_HOVER="#4D4D4D", BORDER_BOTTOM="#454545", DIVIDER="#363636",
        INPUT_LINE="#8A8A8A", DISABLED_BG="#262626", DISABLED_FILL="#3A3A3A",
        TEXT="#EDEDED", MUTED="#ABABAB", FAINT="#727272",
        ACCENT="#2F7FCB", ACCENT_HOVER="#3A8CD8", ACCENT_PRESSED="#24639F", ACCENT_TEXT="#6CB6F2",
        ON_ACCENT="#FFFFFF", ON_ACCENT_MUTED="#CFE4F7",
        DANGER="#FF7A6B", DANGER_BG="#3D2523", ACTIVE_BG="#3A2523", ACTIVE_BORDER="#7A3A33",
        SUCCESS="#6CCB5F", SUCCESS_BG="#1F3320", SUCCESS_BORDER="#2F5A31", SUCCESS_TEXT="#B8E6B0",
        ROW_HOVER="#323232", ROW_SELECTED="#1E3A55",
        SCROLL="#4A4A4A", SCROLL_HOVER="#5E5E5E",
        TOGGLE_OFF="#9A9A9A", KNOB_OFF="#C8C8C8", TRACK="#1C1C1C", TRACK_KNOB_BORDER="#4D4D4D",
        CHIP_BG="rgba(20,20,20,225)", CHIP_TEXT="#FFFFFF", CHIP_KEY_BG="#F0F0F0", CHIP_KEY_TEXT="#141414",
        SELECT_DIM="#000000", SELECT_LABEL_BG="rgba(43,43,43,235)", SELECT_LABEL_TEXT="#EDEDED",
        DARK=True,
    ),
    "sepia": dict(
        BG="#F1E7D0", SURFACE="#FBF5E6", SURFACE_HOVER="#F6EEDA", SURFACE_PRESSED="#EFE4CA",
        BORDER="#E0D2B4", BORDER_HOVER="#C9B690", BORDER_BOTTOM="#D3C29F", DIVIDER="#EADFC5",
        INPUT_LINE="#9C8763", DISABLED_BG="#F3EBD8", DISABLED_FILL="#DCCFB3",
        TEXT="#3B2F22", MUTED="#6E5D48", FAINT="#A8977D",
        ACCENT="#97582B", ACCENT_HOVER="#84491F", ACCENT_PRESSED="#5E3315", ACCENT_TEXT="#8C4F24",
        ON_ACCENT="#FFFBF2", ON_ACCENT_MUTED="#F1D9BF",
        DANGER="#A8321F", DANGER_BG="#F6DED3", ACTIVE_BG="#F7E2D6", ACTIVE_BORDER="#D9A58F",
        SUCCESS="#4F7A28", SUCCESS_BG="#EAEBCF", SUCCESS_BORDER="#C9CF9C", SUCCESS_TEXT="#3C5A1F",
        ROW_HOVER="#F4EBD6", ROW_SELECTED="#F0DEC0",
        SCROLL="#D3C29F", SCROLL_HOVER="#BFA982",
        TOGGLE_OFF="#9C8763", KNOB_OFF="#6E5D48", TRACK="#EADFC5", TRACK_KNOB_BORDER="#D3C29F",
        CHIP_BG="rgba(59,47,34,230)", CHIP_TEXT="#FBF5E6", CHIP_KEY_BG="#FBF5E6", CHIP_KEY_TEXT="#3B2F22",
        SELECT_DIM="#C9B48F", SELECT_LABEL_BG="rgba(251,245,230,230)", SELECT_LABEL_TEXT="#3B2F22",
        DARK=False,
    ),
}
THEME_NAMES = (("light", "Light"), ("dark", "Dark"), ("sepia", "Sepia"))


class _Palette:
    """Current theme's colours as attributes: P.BG, P.TEXT, ..."""
    name = "light"


P = _Palette()


def set_theme(name):
    """Switch the palette and the application's base QPalette (menus, message boxes, tooltips)."""
    if name not in THEMES:
        name = "light"
    P.name = name
    for k, v in THEMES[name].items():
        setattr(P, k, v)
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.setPalette(qpalette())
        app.setStyleSheet(app_qss())



def qcolor(value):
    """QColor from '#RRGGBB' or 'rgba(r,g,b,a)'."""
    if value.startswith("rgba("):
        r, g, b, a = (int(float(x)) for x in value[5:-1].split(","))
        return QColor(r, g, b, a)
    return QColor(value)


def hsk_color(hex_color):
    """HSK colours are mid-tones; lift them a little so they read on a dark surface."""
    c = QColor(hex_color)
    return c.lighter(150).name() if P.DARK else hex_color


def qpalette():
    pal = QPalette()
    roles = {
        QPalette.Window: P.BG, QPalette.WindowText: P.TEXT, QPalette.Base: P.SURFACE,
        QPalette.AlternateBase: P.SURFACE_HOVER, QPalette.Text: P.TEXT, QPalette.Button: P.SURFACE,
        QPalette.ButtonText: P.TEXT, QPalette.ToolTipBase: P.SURFACE, QPalette.ToolTipText: P.TEXT,
        QPalette.Highlight: P.ACCENT, QPalette.HighlightedText: P.ON_ACCENT,
        QPalette.PlaceholderText: P.FAINT, QPalette.Link: P.ACCENT_TEXT, QPalette.BrightText: P.DANGER,
        QPalette.Light: P.SURFACE_HOVER, QPalette.Midlight: P.BORDER, QPalette.Mid: P.BORDER_HOVER,
        QPalette.Dark: P.BORDER_BOTTOM, QPalette.Shadow: "#000000",
    }
    for role, value in roles.items():
        pal.setColor(role, QColor(value))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(P.FAINT))
    return pal


def app_qss():
    """Application-wide rules for widgets no window styles itself (menus, message boxes, tooltips)."""
    return f"""
QToolTip {{ background: {P.SURFACE}; color: {P.TEXT}; border: 1px solid {P.BORDER_HOVER};
           padding: 4px 6px; }}
QMenu {{ background: {P.SURFACE}; color: {P.TEXT}; border: 1px solid {P.BORDER_HOVER};
        font-size: 12px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {P.ROW_HOVER}; }}
QMenu::item:disabled {{ color: {P.FAINT}; }}
QMenu::separator {{ height: 1px; background: {P.BORDER}; margin: 4px 6px; }}
QMessageBox {{ background: {P.BG}; }}
QMessageBox QLabel {{ color: {P.TEXT}; }}
QMessageBox QPushButton {{ background: {P.SURFACE}; color: {P.TEXT}; border: 1px solid {P.BORDER};
                          border-bottom-color: {P.BORDER_BOTTOM}; border-radius: 4px;
                          padding: 5px 16px; min-width: 64px; }}
QMessageBox QPushButton:hover {{ background: {P.SURFACE_HOVER}; }}
QMessageBox QPushButton:default {{ background: {P.ACCENT}; color: {P.ON_ACCENT}; border-color: {P.ACCENT}; }}
"""


def base_qss():
    return f"""
QLabel {{ background: transparent; color: {P.TEXT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px 2px 2px 0; }}
QScrollBar::handle:vertical {{ background: {P.SCROLL}; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {P.SCROLL_HOVER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0 2px 2px 2px; }}
QScrollBar::handle:horizontal {{ background: {P.SCROLL}; border-radius: 3px; min-width: 32px; }}
QScrollBar::handle:horizontal:hover {{ background: {P.SCROLL_HOVER}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
QAbstractScrollArea::corner {{ background: transparent; }}

QLineEdit {{ background: {P.SURFACE}; border: 1px solid {P.BORDER}; border-bottom: 1px solid {P.INPUT_LINE};
            border-radius: 4px; padding: 6px 9px; color: {P.TEXT}; font-size: 12px;
            selection-background-color: {P.ACCENT}; selection-color: {P.ON_ACCENT}; }}
QLineEdit:focus {{ border-bottom: 2px solid {P.ACCENT}; }}
QLineEdit:disabled {{ color: {P.FAINT}; background: {P.DISABLED_BG}; border-bottom-color: {P.BORDER}; }}

QComboBox {{ background: {P.SURFACE}; border: 1px solid {P.BORDER}; border-bottom-color: {P.BORDER_BOTTOM};
            border-radius: 4px; color: {P.TEXT}; font-size: 12px; padding: 5px 10px; }}
QComboBox:hover {{ background: {P.SURFACE_HOVER}; border-color: {P.BORDER_HOVER}; }}
QComboBox:disabled {{ color: {P.FAINT}; background: {P.DISABLED_BG}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {P.SURFACE}; color: {P.TEXT}; border: 1px solid {P.BORDER_HOVER};
                              selection-background-color: {P.ROW_SELECTED}; selection-color: {P.TEXT};
                              outline: none; padding: 2px; }}

QPushButton#btn {{ background: {P.SURFACE}; border: 1px solid {P.BORDER}; border-bottom-color: {P.BORDER_BOTTOM};
                  border-radius: 4px; color: {P.TEXT}; font-size: 12px; padding: 6px 14px; }}
QPushButton#btn:hover {{ background: {P.SURFACE_HOVER}; }}
QPushButton#btn:pressed {{ background: {P.SURFACE_PRESSED}; color: {P.MUTED}; }}
QPushButton#btn:disabled {{ color: {P.FAINT}; }}
QPushButton#btnAccent {{ background: {P.ACCENT}; border: 1px solid {P.ACCENT}; border-radius: 4px;
                        color: {P.ON_ACCENT}; font-size: 12px; padding: 6px 14px; }}
QPushButton#btnAccent:hover {{ background: {P.ACCENT_HOVER}; }}
QPushButton#btnAccent:pressed {{ background: {P.ACCENT_PRESSED}; }}
QPushButton#btnAccent:disabled {{ background: {P.DISABLED_FILL}; border-color: {P.DISABLED_FILL}; color: {P.FAINT}; }}
QPushButton#btnDanger {{ background: transparent; border: 1px solid transparent; border-radius: 4px;
                        color: {P.DANGER}; font-size: 12px; padding: 6px 10px; }}
QPushButton#btnDanger:hover {{ background: {P.DANGER_BG}; }}
QPushButton#btnDanger:disabled {{ color: {P.FAINT}; }}
"""


def style_title_bar(widget):
    """Match the Windows title bar to the theme (dark title bar, sepia caption colour).

    Windows 10 1809+ knows the dark flag; caption colours need Windows 11.
    Older systems ignore both, which is fine.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        hwnd = int(widget.winId())

        def setattr_(attr, value):
            v = ctypes.c_uint(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        def colorref(hex_color):
            c = QColor(hex_color)
            return c.red() | (c.green() << 8) | (c.blue() << 16)

        DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR = 20, 35, 36
        DWMWA_COLOR_DEFAULT = 0xFFFFFFFF
        setattr_(DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if P.DARK else 0)
        if P.name == "sepia":
            setattr_(DWMWA_CAPTION_COLOR, colorref(P.BG))
            setattr_(DWMWA_TEXT_COLOR, colorref(P.TEXT))
        else:
            setattr_(DWMWA_CAPTION_COLOR, DWMWA_COLOR_DEFAULT)
            setattr_(DWMWA_TEXT_COLOR, DWMWA_COLOR_DEFAULT)
    except Exception:
        pass


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


set_theme("light")  # until main.py applies the saved theme
