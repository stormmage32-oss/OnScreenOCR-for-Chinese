import sys
import keyboard
import logging
from PyQt5 import sip
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
                             QFrame, QLabel, QPushButton, QLineEdit, QDialog, QAbstractButton,
                             QButtonGroup, QStackedWidget, QSizePolicy,
                             QMessageBox, QSystemTrayIcon, QMenu, QAction, QApplication)
from PyQt5.QtCore import (Qt, QObject, pyqtSignal, pyqtProperty, QThread, QTimer, QRect, QRectF,
                          QPropertyAnimation, QEasingCurve)
from PyQt5.QtGui import QFont, QFontMetrics, QIcon, QPainter, QColor, QCursor

from config import load_config, save_config
from ocr_engine import init_ocr, take_screenshot, OCRWorker, LiveScanWorker
from dictionary import segment_ocr_results
from ui_overlay import RegionSelector, OverlayWindow, PinyinOverlayWindow, LivePinyinOverlayWindow
from word_notebook import WordNotebookWindow, migrate_and_load_saved_words
from theme import (BASE_QSS, BG, SURFACE, BORDER, BORDER_HOVER, TEXT, MUTED, FAINT, ACCENT,
                   ACCENT_HOVER, ACCENT_PRESSED, DANGER, SUCCESS, app_icon_pixmap)
from screens import to_physical

logger = logging.getLogger("OCRApp")

class HotkeyListener(QObject):
    triggered = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_hotkey = ""

    def set_hotkey(self, key_str):
        if self.current_hotkey:
            try: keyboard.remove_hotkey(self.current_hotkey)
            except: pass
        self.current_hotkey = key_str
        if key_str:
            try: keyboard.add_hotkey(key_str, self.triggered.emit)
            except Exception as e: logger.error(f"Hotkey error: {e}")


# ---------------------------------------------------------------------------
# Look & feel
# ---------------------------------------------------------------------------

QSS = BASE_QSS + f"""
QMainWindow, QWidget#page {{ background: {BG}; }}
QScrollArea, QWidget#qt_scrollarea_viewport {{ background: {BG}; border: none; }}

QLabel#appTitle {{ font-size: 18px; font-weight: 600; }}
QLabel#section {{ color: {MUTED}; font-size: 12px; font-weight: 600; }}
QLabel#caption {{ color: {MUTED}; font-size: 11px; }}

QPushButton#tab {{ background: transparent; border: none; border-bottom: 2px solid transparent;
                  color: {MUTED}; font-size: 13px; padding: 6px 2px; margin-right: 18px; }}
QPushButton#tab:hover {{ color: {TEXT}; }}
QPushButton#tab:checked {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QFrame#tabLine {{ background: {BORDER}; border: none; max-height: 1px; min-height: 1px; }}

QPushButton#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}
QPushButton#card:hover {{ background: #FAFAFA; border-color: {BORDER_HOVER}; }}
QPushButton#card:pressed {{ background: #F2F2F2; }}
QPushButton#card:disabled {{ background: #FAFAFA; border-color: #EAEAEA; }}
QPushButton#cardPrimary {{ background: {ACCENT}; border: 1px solid {ACCENT}; border-radius: 6px; }}
QPushButton#cardPrimary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#cardPrimary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#cardPrimary:disabled {{ background: #DCDCDC; border-color: #DCDCDC; }}
QPushButton#cardActive {{ background: #FDF3F2; border: 1px solid #E8B4AE; border-radius: 6px; }}
QPushButton#cardActive:hover {{ border-color: {DANGER}; }}

QLabel#cardTitle {{ font-size: 13px; font-weight: 600; }}
QLabel#cardTitle:disabled {{ color: {FAINT}; }}
QLabel#cardKey {{ color: {MUTED}; font-size: 12px; }}
QLabel#cardKey:disabled {{ color: {FAINT}; }}
QPushButton#cardPrimary QLabel#cardTitle {{ color: #FFFFFF; }}
QPushButton#cardPrimary QLabel#cardKey {{ color: #CFE4F7; }}
QPushButton#cardPrimary QLabel#cardTitle:disabled,
QPushButton#cardPrimary QLabel#cardKey:disabled {{ color: #F5F5F5; }}
QPushButton#cardActive QLabel#cardTitle {{ color: {DANGER}; }}

QFrame#group {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}
QFrame#divider {{ background: #EDEDED; border: none; max-height: 1px; min-height: 1px; }}
QLabel#rowTitle {{ font-size: 13px; }}
QLabel#rowSub {{ color: {MUTED}; font-size: 11px; }}

QPushButton#keycap {{ background: {SURFACE}; border: 1px solid {BORDER}; border-bottom-color: #CFCFCF;
                     border-radius: 4px; color: {TEXT}; font-size: 12px; padding: 5px 12px; min-width: 90px; }}
QPushButton#keycap:hover {{ background: #F9F9F9; border-color: {BORDER_HOVER}; }}
QPushButton#keycap[empty="true"] {{ color: {FAINT}; }}

QFrame#statusBar {{ background: {SURFACE}; border: none; border-top: 1px solid {BORDER}; }}
QLabel#statusText {{ color: {MUTED}; font-size: 11px; }}
QLabel#statusText[state="ready"] {{ color: {SUCCESS}; }}
QLabel#statusText[state="error"] {{ color: {DANGER}; }}

QFrame#dlg {{ background: {SURFACE}; border: 1px solid {BORDER_HOVER}; border-radius: 8px; }}
QLabel#dlgTitle {{ font-size: 14px; font-weight: 600; }}
"""

# config key, display name, default, listener attribute
HOTKEYS = (
    ("pinyin_hotkey", "Pinyin overlay", "alt+p", "pinyin_hk_listener"),
    ("seamless_hotkey", "Seamless mode", "alt+shift+s", "seamless_hk_listener"),
    ("live_hotkey", "Live pinyin", "alt+l", "live_hk_listener"),
    ("live_region_hotkey", "Live pinyin in a region", "alt+shift+l", "live_region_hk_listener"),
    # Not global: only read while a scan result is open.
    ("save_word_key", "Save word", "s", None),
)
HOTKEY_NOTES = {"save_word_key": "Hover a word in a scan and press this key"}
HOTKEY_NAMES = {k: name for k, name, _, _ in HOTKEYS}


def format_hotkey(hk):
    if not hk:
        return ""
    return "+".join(p.strip().capitalize() if len(p.strip()) > 1 else p.strip().upper()
                    for p in hk.split("+"))


def _label(text, name, wrap=False):
    l = QLabel(text)
    l.setObjectName(name)
    if wrap:
        l.setWordWrap(True)
    return l


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    for child in w.findChildren(QWidget):
        child.style().unpolish(child)
        child.style().polish(child)


class ToggleSwitch(QAbstractButton):
    """Windows 11 style on/off switch."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 20)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self):
        return self._offset

    def _set_offset(self, v):
        self._offset = v
        self.update()

    offset = pyqtProperty(float, _get_offset, _set_offset)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = r.height() / 2
        on = self.isChecked()
        if on:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT if self.isEnabled() else "#C8C8C8"))
        else:
            p.setPen(QColor("#8A8A8A" if self.isEnabled() else "#C8C8C8"))
            p.setBrush(QColor(SURFACE))
        p.drawRoundedRect(r, rad, rad)
        d = 12
        x = 4 + (r.width() - d - 8) * self._offset
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF") if on else QColor("#5F5F5F"))
        p.drawEllipse(QRectF(x + 0.5, (self.height() - d) / 2, d, d))


class ActionCard(QPushButton):
    """A clickable tile: title on the left, its shortcut (or extra info) on the right."""

    def __init__(self, title, primary=False, height=60):
        super().__init__()
        self._base_name = "cardPrimary" if primary else "card"
        self.setObjectName(self._base_name)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(8)
        self.title = _label(title, "cardTitle")
        self.key = _label("", "cardKey")
        row.addWidget(self.title, 1)
        row.addWidget(self.key)
        for w in (self.title, self.key):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_shortcut(self, hk):
        self.key.setText(format_hotkey(hk))

    def set_title(self, title):
        self.title.setText(title)

    def set_active(self, active):
        name = "cardActive" if active else self._base_name
        if self.objectName() != name:
            self.setObjectName(name)
            _repolish(self)


class LoadingIndicator(QWidget):
    """Small "Loading..." label in the top-right corner of a screen while OCR runs.

    It never takes focus or mouse input, so a game in the foreground keeps both.
    """

    def __init__(self, screen_rect):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._dots = 3
        f = QFont("Segoe UI"); f.setPixelSize(14); f.setBold(True)
        self.setFont(f)
        self.setFixedSize(QFontMetrics(f).horizontalAdvance("Loading...") + 32, 34)
        self.move(screen_rect.right() - self.width() - 20, screen_rect.top() + 20)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(400)

    def _tick(self):
        self._dots = self._dots % 3 + 1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 20, 225))
        p.drawRoundedRect(QRectF(self.rect()), 6, 6)
        p.setPen(QColor("#FFFFFF"))
        # Left-aligned with a fixed width, so the box doesn't jump as the dots change.
        p.drawText(self.rect().adjusted(16, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   "Loading" + "." * self._dots)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chinese Screen OCR")
        self.setWindowIcon(QIcon(app_icon_pixmap(64)))
        self._fit_to_screen()
        self.setStyleSheet(QSS)
        self.ocr_ready = False; self.overlay = None; self.pinyin_overlay = None; self._worker = None
        self._active_screen_rect = None; self._ocr_mode = "normal"; self.seamless_overlay = None
        self.live_overlay = None; self._live_worker = None; self._capture_scale = 1.0
        self._progress = None; self.notebook = None
        self._live_sel = None; self._live_restore_window = False
        self.config = load_config()
        self._keycaps = {}
        self._build(); self._start_init()
        self._setup_hotkey()
        self._setup_tray()

    def _fit_to_screen(self):
        # At high display scaling the logical screen can be shorter than the
        # window; the content then scrolls instead of running off-screen.
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        avail = screen.availableGeometry().height() - 40 if screen else 680
        self.setFixedSize(460, max(320, min(680, avail)))

    # ------------------------------------------------------------------ build

    def _build(self):
        root = QWidget(); root.setObjectName("page")
        rv = QVBoxLayout(root); rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(0)
        self.setCentralWidget(root)

        header = QWidget(); header.setObjectName("page")
        hv = QVBoxLayout(header); hv.setContentsMargins(24, 20, 24, 0); hv.setSpacing(12)
        hv.addWidget(_label("Chinese Screen OCR", "appTitle"))
        tabs = QHBoxLayout(); tabs.setSpacing(0)
        self._pages = QStackedWidget()
        self._nav = QButtonGroup(self); self._nav.setExclusive(True)
        for i, name in enumerate(("Home", "Settings")):
            b = QPushButton(name); b.setObjectName("tab"); b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self._nav.addButton(b, i); tabs.addWidget(b)
        tabs.addStretch()
        self._nav.button(0).setChecked(True)
        self._nav.buttonClicked[int].connect(self._pages.setCurrentIndex)
        hv.addLayout(tabs)
        rv.addWidget(header)
        line = QFrame(); line.setObjectName("tabLine")
        rv.addWidget(line)

        self._pages.addWidget(self._scroll_page(self._build_home()))
        self._pages.addWidget(self._scroll_page(self._build_settings()))
        rv.addWidget(self._pages, 1)

        bar = QFrame(); bar.setObjectName("statusBar"); bar.setFixedHeight(30)
        bl = QHBoxLayout(bar); bl.setContentsMargins(24, 0, 24, 0)
        self.status = _label("", "statusText")
        bl.addWidget(self.status); bl.addStretch()
        rv.addWidget(bar)

        self._set_status("loading", "Loading OCR engine…")
        for key, *_ in HOTKEYS:
            self._refresh_hotkey(key)
        self._refresh_word_count()

    def _scroll_page(self, content):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _page(self):
        w = QWidget(); w.setObjectName("page")
        v = QVBoxLayout(w); v.setContentsMargins(24, 18, 24, 20); v.setSpacing(0)
        return w, v

    def _build_home(self):
        page, v = self._page()

        v.addWidget(_label("Scan", "section")); v.addSpacing(8)
        g = QGridLayout(); g.setSpacing(8)
        self.btn_r = ActionCard("Select region", primary=True)
        self.btn_r.setToolTip("Drag a box around the text.\n"
                              "Double-click while selecting to scan the whole screen. Esc cancels.")
        self.btn_r.clicked.connect(self._start_region)
        self.btn_seamless = ActionCard("Seamless mode")
        self.btn_seamless.setToolTip("Scan the screen the mouse is on and click words right on it.\n"
                              "Esc closes it.")
        self.btn_seamless.clicked.connect(self._start_seamless_from_button)
        g.addWidget(self.btn_r, 0, 0); g.addWidget(self.btn_seamless, 0, 1)
        v.addLayout(g)

        v.addSpacing(20)
        v.addWidget(_label("Live pinyin", "section")); v.addSpacing(8)
        g2 = QGridLayout(); g2.setSpacing(8)
        self.btn_live = ActionCard("Whole screen")
        self.btn_live.setToolTip("Keep showing pinyin over the screen while you play")
        self.btn_live.clicked.connect(self._toggle_live)
        self.btn_live_region = ActionCard("Selected region")
        self.btn_live_region.setToolTip("Draw a box; only that area is watched")
        self.btn_live_region.clicked.connect(self._toggle_live_region)
        g2.addWidget(self.btn_live, 0, 0); g2.addWidget(self.btn_live_region, 0, 1)
        v.addLayout(g2)

        v.addSpacing(20)
        v.addWidget(_label("Vocabulary", "section")); v.addSpacing(8)
        self.btn_n = ActionCard("Saved words")
        self.btn_n.clicked.connect(self._open_notebook)
        v.addWidget(self.btn_n)

        for b in (self.btn_r, self.btn_seamless, self.btn_live, self.btn_live_region):
            b.setEnabled(False)
        v.addStretch()
        return page

    def _build_settings(self):
        page, v = self._page()

        v.addWidget(_label("Reading", "section")); v.addSpacing(8)
        grp, gl = self._group()
        self.cb_manga = ToggleSwitch(self.config.get('manga_mode', False))
        self.cb_manga.toggled.connect(self._save_manga_mode)
        gl.addLayout(self._setting_row("Manga mode", "Read vertical text", self.cb_manga))
        gl.addWidget(self._divider())
        self.cb_deepl = ToggleSwitch(self.config.get('deepl_enabled', False))
        self.cb_deepl.toggled.connect(self._save_deepl_enabled)
        gl.addLayout(self._setting_row("DeepL translation",
                                       "Translate sentences on double-click or selection",
                                       self.cb_deepl))
        key_box = QHBoxLayout(); key_box.setContentsMargins(16, 0, 16, 14); key_box.setSpacing(8)
        self.le_deepl_key = QLineEdit(self.config.get('deepl_api_key', ''))
        self.le_deepl_key.setEchoMode(QLineEdit.Password)
        self.le_deepl_key.setPlaceholderText("DeepL API key (free)")
        self.le_deepl_key.setToolTip("Your key is saved only in this computer's app settings.")
        self.le_deepl_key.textChanged.connect(self._save_deepl_key)
        btn_eye = QPushButton("Show"); btn_eye.setObjectName("btn"); btn_eye.setFixedWidth(64)
        btn_eye.clicked.connect(lambda: self._toggle_key_visible(btn_eye))
        key_box.addWidget(self.le_deepl_key, 1); key_box.addWidget(btn_eye)
        gl.addLayout(key_box)
        gl.addWidget(self._divider())
        self.cb_deepl_always = ToggleSwitch(self.config.get('deepl_always', False))
        self.cb_deepl_always.toggled.connect(self._save_deepl_always)
        gl.addLayout(self._setting_row("Always translate",
                                       "Translate every word you click, not only on double-click",
                                       self.cb_deepl_always))
        self._update_deepl_key_enabled()
        v.addWidget(grp)

        v.addSpacing(20)
        v.addWidget(_label("Shortcuts", "section")); v.addSpacing(8)
        grp2, gl2 = self._group()
        for i, (key, name, _, _) in enumerate(HOTKEYS):
            if i:
                gl2.addWidget(self._divider())
            cap = QPushButton(); cap.setObjectName("keycap"); cap.setCursor(Qt.PointingHandCursor)
            cap.setToolTip("Click, then press the new shortcut")
            cap.clicked.connect(lambda _=False, k=key: self._read_hotkey(k))
            self._keycaps[key] = cap
            gl2.addLayout(self._setting_row(name, HOTKEY_NOTES.get(key), cap, compact=True))
        v.addWidget(grp2)
        v.addSpacing(6)
        v.addWidget(_label("Click a shortcut to change it.", "caption"))
        v.addStretch()
        return page

    def _group(self):
        f = QFrame(); f.setObjectName("group")
        l = QVBoxLayout(f); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(0)
        return f, l

    def _divider(self):
        d = QFrame(); d.setObjectName("divider")
        return d

    def _setting_row(self, title, subtitle, control, compact=False):
        row = QHBoxLayout()
        row.setContentsMargins(16, 8 if compact else 12, 12, 8 if compact else 12)
        row.setSpacing(12)
        col = QVBoxLayout(); col.setSpacing(1)
        col.addWidget(_label(title, "rowTitle"))
        if subtitle:
            col.addWidget(_label(subtitle, "rowSub", wrap=True))
        row.addLayout(col, 1)
        row.addWidget(control, 0, Qt.AlignVCenter)
        return row

    # ------------------------------------------------------------ ui helpers

    def _set_status(self, state, text):
        self.status.setText(text)
        self.status.setProperty("state", state)
        _repolish(self.status)

    def _refresh_word_count(self):
        try:
            n = len(migrate_and_load_saved_words())
        except Exception:
            n = 0
        self.btn_n.key.setText(f"{n} word" + ("" if n == 1 else "s"))

    def _refresh_hotkey(self, key):
        hk = self.config.get(key, "")
        cap = self._keycaps.get(key)
        if cap is not None:
            cap.setText(format_hotkey(hk) or "Not set")
            cap.setProperty("empty", "false" if hk else "true")
            _repolish(cap)
        cards = {"seamless_hotkey": self.btn_seamless, "live_hotkey": self.btn_live,
                 "live_region_hotkey": self.btn_live_region}
        if key in cards:
            cards[key].set_shortcut(hk)

    def _toggle_key_visible(self, btn):
        hidden = self.le_deepl_key.echoMode() == QLineEdit.Password
        self.le_deepl_key.setEchoMode(QLineEdit.Normal if hidden else QLineEdit.Password)
        btn.setText("Hide" if hidden else "Show")

    def _update_deepl_key_enabled(self):
        self.le_deepl_key.setEnabled(self.cb_deepl.isChecked())
        self.cb_deepl_always.setEnabled(self.cb_deepl.isChecked())

    def _save_manga_mode(self, state):
        self.config['manga_mode'] = bool(state)
        save_config(self.config)

    def _save_deepl_enabled(self, state):
        self.config['deepl_enabled'] = bool(state)
        save_config(self.config)
        self._update_deepl_key_enabled()

    def _save_deepl_always(self, state):
        self.config['deepl_always'] = bool(state)
        save_config(self.config)

    def _save_deepl_key(self, text):
        self.config['deepl_api_key'] = text.strip()
        save_config(self.config)

    def _start_init(self):
        class _T(QThread):
            done = pyqtSignal(bool)
            def run(self): self.done.emit(init_ocr())
        self._init_t = _T(); self._init_t.done.connect(self._on_ready); self._init_t.start()

    def _on_ready(self, ok: bool):
        self.ocr_ready = ok
        if ok:
            self._set_status("ready", "PaddleOCR ready")
            self.btn_r.setEnabled(True); self.btn_seamless.setEnabled(True); self.btn_live.setEnabled(True)
            self.btn_live_region.setEnabled(True)
        else:
            self._set_status("error", "OCR failed to load. See the log file in AppData.")
            QMessageBox.critical(self, "OCR Error", "Failed to load OCR. Check the log file in AppData.")

    def _set_buttons(self, enabled: bool):
        self.btn_r.setEnabled(enabled and self.ocr_ready)
        self.btn_seamless.setEnabled(enabled and self.ocr_ready)

    def _screen_rect_for_action(self):
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos)
        if screen is None and self.isVisible():
            screen = QApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen.geometry() if screen else QRect()

    def _start_region(self):
        self._set_buttons(False)
        self._ocr_mode = "normal"
        self._active_screen_rect = None
        self.hide(); QTimer.singleShot(250, self._show_sel)

    def _show_sel(self):
        self.sel = RegionSelector()
        self.sel.region_selected.connect(self._on_region)
        self.sel.cancelled.connect(self._on_cancelled)
        self.sel.show()

    def _on_cancelled(self):
        self.show(); self._set_buttons(True)

    def _on_region(self, x, y, w, h):
        selected = QRect(x, y, w, h)
        self._active_screen_rect = None
        for screen in QApplication.screens():
            if screen.geometry() == selected:
                self._active_screen_rect = selected
                break
        QTimer.singleShot(150, lambda: self._do_cap(x,y,w,h))

    def _do_cap(self, x, y, w, h):
        # x, y, w, h are Qt logical pixels; the screenshot needs physical pixels.
        physical, self._capture_scale = to_physical(QRect(x, y, w, h))
        try: img = take_screenshot(physical)
        except Exception as e:
            self._ocr_mode = "normal"
            self.show(); self._set_buttons(True)
            QMessageBox.critical(self,"Error",f"Failed to take screenshot:\n{e}"); return
        self._run_ocr(img)

    def _run_ocr(self, img):
        # Dialogs parented to the main window live as long as it does unless
        # deleted, so every transient one here is WA_DeleteOnClose.
        if self._progress is not None and not sip.isdeleted(self._progress):
            self._progress.close()  # an aborted scan's indicator is never closed by its worker
        # Shown after the screenshot was taken, so it never ends up in the OCR image.
        prog = LoadingIndicator(self._active_screen_rect or self._screen_rect_for_action())
        self._progress = prog
        prog.show()
        
        if self._worker is not None and self._worker.isRunning():
            self._worker.abort()
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except TypeError:
                pass
            self._worker.wait(500)
            
        manga_mode = self.config.get('manga_mode', False)
        w = OCRWorker(img, manga_mode); self._worker = w
        del img  # the worker hands it back in done(); don't keep it in this closure

        def done(r, img):
            prog.close()
            if self._ocr_mode == "pinyin":
                self._show_pinyin_overlay(r, img)
                return
            if self._ocr_mode == "seamless":
                self._show_seamless_overlay(img, r)
                return
            self.show(); self._set_buttons(True)
            if not r: QMessageBox.information(self,"Result","No text found."); return
            word_results = segment_ocr_results(r, img)
            if self.overlay is not None and not sip.isdeleted(self.overlay):
                self.overlay.close()
            self.overlay = OverlayWindow(img, word_results, main_win=self, screen_rect=self._active_screen_rect,
                                         scale=self._capture_scale)
            self.overlay.destroyed.connect(self._on_overlay_destroyed)
            self.overlay.show()
            if self._active_screen_rect:
                self.overlay.setGeometry(self._active_screen_rect)
                self.overlay.showMaximized()

        def err(m):
            prog.close()
            seamless = self._ocr_mode == "seamless"
            if not seamless: self.show()
            self._set_buttons(True)
            self._ocr_mode = "normal"
            if seamless:
                self._end_seamless()
                self.tray_icon.showMessage("Chinese Screen OCR", f"Seamless OCR failed: {m}", QSystemTrayIcon.Warning, 5000)
            else:
                QMessageBox.critical(self,"OCR Error", m)

        w.finished.connect(done); w.error.connect(err); w.start()

    def _on_overlay_destroyed(self, *_):
        # Drop the Python wrapper too: it still holds the screenshot pixmap. A
        # replaced overlay is destroyed after the new one is assigned, so check.
        if self.overlay is not None and sip.isdeleted(self.overlay):
            self.overlay = None

    def _setup_hotkey(self):
        self._remove_startup_hotkey_conflicts()
        self.pinyin_hk_listener = HotkeyListener()
        self.pinyin_hk_listener.triggered.connect(self._toggle_pinyin_overlay_from_hotkey)
        self.pinyin_hk_listener.set_hotkey(self.config.get('pinyin_hotkey', 'alt+p'))
        self.seamless_hk_listener = HotkeyListener()
        self.seamless_hk_listener.triggered.connect(self._toggle_seamless_from_hotkey)
        self.seamless_hk_listener.set_hotkey(self.config.get('seamless_hotkey', 'alt+shift+s'))
        self.seamless_esc_listener = HotkeyListener()
        self.seamless_esc_listener.triggered.connect(self._close_seamless)
        self.seamless_esc_listener.set_hotkey('esc')
        self.live_hk_listener = HotkeyListener()
        self.live_hk_listener.triggered.connect(self._toggle_live)
        self.live_hk_listener.set_hotkey(self.config.get('live_hotkey', 'alt+l'))
        self.live_region_hk_listener = HotkeyListener()
        self.live_region_hk_listener.triggered.connect(self._toggle_live_region)
        self.live_region_hk_listener.set_hotkey(self.config.get('live_region_hotkey', 'alt+shift+l'))

    def _remove_startup_hotkey_conflicts(self):
        """Migrate an existing config where two modes were assigned one key."""
        priority = ("live_hotkey", "live_region_hotkey", "seamless_hotkey", "pinyin_hotkey")
        used = set()
        changed = False
        for key in priority:
            hotkey = self.config.get(key, "").strip()
            if hotkey and hotkey.lower() in used:
                self.config[key] = ""
                self._refresh_hotkey(key)
                changed = True
            elif hotkey:
                used.add(hotkey.lower())
        if changed:
            save_config(self.config)
        
    def _toggle_pinyin_overlay_from_hotkey(self):
        if self.pinyin_overlay is not None:
            self.pinyin_overlay.close()
            self.pinyin_overlay = None
            self._set_buttons(True)
            return
        if self.ocr_ready and self.btn_seamless.isEnabled():
            self._start_pinyin_overlay()

    def _toggle_seamless_from_hotkey(self):
        if self.seamless_overlay is not None:
            self._close_seamless()
        elif self.ocr_ready and self.btn_seamless.isEnabled():
            self._seamless_restore = False
            self._start_seamless()

    def _start_seamless_from_button(self):
        self._seamless_restore = True
        self._start_seamless()

    def _end_seamless(self):
        """Seamless scan ended: bring the window back only if it was started from it."""
        self._set_buttons(True)
        if getattr(self, "_seamless_restore", False):
            self._seamless_restore = False
            self.show_and_raise()
        else:
            # Keep the main window hidden so focus returns to the game/app.
            self.hide()

    def _close_seamless(self):
        if self.seamless_overlay is not None:
            if self.seamless_overlay.isVisible():
                self.seamless_overlay.close()
            else:
                self.seamless_overlay = None
                self._set_buttons(True)

    def _start_seamless(self):
        self._set_buttons(False)
        self.hide()
        self._ocr_mode = "seamless"
        s = self._screen_rect_for_action()
        self._active_screen_rect = s
        QTimer.singleShot(150, lambda: self._do_cap(s.x(), s.y(), s.width(), s.height()))

    def _show_seamless_overlay(self, image, results):
        self._ocr_mode = "normal"
        if not results:
            self._end_seamless()
            self.tray_icon.showMessage("Chinese Screen OCR", "Seamless scan found no text.", QSystemTrayIcon.Information, 3000)
            return
        if self.seamless_overlay is not None:
            self.seamless_overlay.close()
        word_results = segment_ocr_results(results, image)
        overlay = OverlayWindow(image, word_results, main_win=None,
                                screen_rect=self._active_screen_rect, seamless=True,
                                scale=self._capture_scale)
        self.seamless_overlay = overlay

        def closed(*_):
            if self.seamless_overlay is overlay:
                self.seamless_overlay = None
                self._end_seamless()

        overlay.seamless_closed.connect(closed)
        # showFullScreen is intentional: merely using a frameless flag still
        # leaves a Windows title bar in some Qt/Windows combinations.
        overlay.showFullScreen()
        overlay.raise_()
        overlay.activateWindow()
        overlay.setFocus()

    def _start_pinyin_overlay(self):
        self._set_buttons(False)
        self.hide()
        self._ocr_mode = "pinyin"
        s = self._screen_rect_for_action()
        self._active_screen_rect = s
        QTimer.singleShot(150, lambda: self._do_cap(s.x(), s.y(), s.width(), s.height()))

    def _show_pinyin_overlay(self, results, image):
        self._ocr_mode = "normal"
        self._set_buttons(True)
        if not results:
            self.show()
            QMessageBox.information(self, "Result", "No text found.")
            return
        if self.pinyin_overlay is not None:
            self.pinyin_overlay.close()
        self.pinyin_overlay = PinyinOverlayWindow(results, self._active_screen_rect, image=image)
        self.pinyin_overlay.destroyed.connect(lambda *_: setattr(self, "pinyin_overlay", None))
        self.pinyin_overlay.show()

    def _toggle_live(self):
        if self._live_worker is not None:
            self._stop_live()
        elif self._live_sel is None and self.ocr_ready:
            self._start_live(self._screen_rect_for_action())

    def _toggle_live_region(self):
        if self._live_worker is not None:
            self._stop_live()
        elif self._live_sel is not None:
            self._on_live_region_cancelled()  # pressed again while selecting
        elif self.ocr_ready:
            self._live_restore_window = self.isVisible()
            sel = self._live_sel = RegionSelector()
            sel.region_selected.connect(self._on_live_region)
            sel.cancelled.connect(self._on_live_region_cancelled)
            self.hide()
            # Let the main window disappear before the screen is dimmed.
            QTimer.singleShot(250, lambda: sel.show() if sel is self._live_sel else None)

    def _end_live_region_select(self):
        sel, self._live_sel = self._live_sel, None
        if sel is not None:
            sel.close()

    def _on_live_region(self, x, y, w, h):
        self._end_live_region_select()
        self._start_live(QRect(x, y, w, h), region=True)

    def _on_live_region_cancelled(self):
        self._end_live_region_select()
        if self._live_restore_window:
            self.show_and_raise()

    def _start_live(self, rect, region=False):
        """rect: logical area to scan; region: user-selected rather than a whole screen."""
        self.live_overlay = LivePinyinOverlayWindow(rect, region=region)
        self.live_overlay.show()
        physical, _ = to_physical(rect)
        self._live_worker = LiveScanWorker(physical,
                                           manga_mode=self.config.get('manga_mode', False))
        self._live_worker.results_changed.connect(self._on_live_results)
        self._live_worker.start()
        self._set_live_labels(True)
        # Hide the main window so the game is what's underneath the labels.
        self.hide()

    def _set_live_labels(self, running):
        stop = "Stop Live Pinyin"
        if running:
            for card in (self.btn_live, self.btn_live_region):
                card.set_title("Stop live pinyin")
        else:
            self.btn_live.set_title("Whole screen")
            self.btn_live_region.set_title("Selected region")
        self.btn_live.set_active(running)
        self.btn_live_region.set_active(running)
        self.act_live.setText(stop if running else "Start Live Pinyin")
        self.act_live_region.setText(stop if running else "Live Pinyin in Selected Region")

    def _on_live_results(self):
        latest = self._live_worker.take_results() if self._live_worker is not None else None
        if latest is not None and self.live_overlay is not None:
            self.live_overlay.set_results(*latest)

    def _stop_live(self):
        worker, self._live_worker = self._live_worker, None
        if worker is not None:
            worker.results_changed.disconnect()
            worker.stop()
            worker.wait(5000)
        if self.live_overlay is not None:
            self.live_overlay.close()
            self.live_overlay = None
        self._set_live_labels(False)

    def _read_hotkey(self, config_key):
        name = HOTKEY_NAMES[config_key]
        attr = dict((k, a) for k, _, _, a in HOTKEYS)[config_key]
        listener = getattr(self, attr) if attr else None
        self.btn_r.setEnabled(False); self.btn_seamless.setEnabled(False)
        msg = QDialog(self, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        msg.setAttribute(Qt.WA_DeleteOnClose)
        msg.setAttribute(Qt.WA_TranslucentBackground)
        outer = QVBoxLayout(msg); outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(); card.setObjectName("dlg"); outer.addWidget(card)
        l = QVBoxLayout(card); l.setContentsMargins(24, 18, 24, 18); l.setSpacing(6)
        t = _label("Press the new shortcut", "dlgTitle"); t.setAlignment(Qt.AlignCenter)
        s = _label(f"{name}. Press Esc to cancel.", "rowSub"); s.setAlignment(Qt.AlignCenter)
        l.addWidget(t); l.addWidget(s)
        msg.setFixedWidth(300)
        msg.adjustSize()
        msg.move(self.geometry().center() - msg.rect().center())
        msg.show()
        
        class Reader(QThread):
            done = pyqtSignal(str)
            def run(self):
                hk = keyboard.read_hotkey(suppress=False)
                self.done.emit(hk)
        
        self.hk_reader = Reader()
        def on_done(hk):
            msg.close()
            self._set_buttons(True)
            if hk and hk.lower() not in ("esc", "escape"):
                self._clear_hotkey_conflicts(config_key, hk)
                self.config[config_key] = hk
                save_config(self.config)
                self._refresh_hotkey(config_key)
                if listener is not None:
                    listener.set_hotkey(hk)
        self.hk_reader.done.connect(on_done)
        self.hk_reader.start()

    def _clear_hotkey_conflicts(self, config_key, hotkey):
        """One physical shortcut must control exactly one OCR mode."""
        for key, _, _, attr in HOTKEYS:
            if key != config_key and self.config.get(key, "").lower() == hotkey.lower():
                if attr:
                    getattr(self, attr).set_hotkey("")
                self.config[key] = ""
                self._refresh_hotkey(key)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(app_icon_pixmap(32)))
        self.tray_icon.setToolTip("Chinese Screen OCR")

        menu = QMenu()
        menu.setStyleSheet(
            f"QMenu {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER_HOVER}; "
            "font-size: 12px; padding: 4px; }"
            "QMenu::item { padding: 6px 18px; border-radius: 4px; }"
            "QMenu::item:selected { background: #EDEDED; }"
            f"QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}"
        )
        act_show = QAction("Show Main Window", self)
        act_show.triggered.connect(self.show_and_raise)
        menu.addAction(act_show)

        act_scan = QAction("Quick Scan (Select Region)", self)
        act_scan.triggered.connect(self._start_region)
        menu.addAction(act_scan)

        self.act_live = QAction("Start Live Pinyin", self)
        self.act_live.triggered.connect(self._toggle_live)
        menu.addAction(self.act_live)

        self.act_live_region = QAction("Live Pinyin in Selected Region", self)
        self.act_live_region.triggered.connect(self._toggle_live_region)
        menu.addAction(self.act_live_region)

        act_notebook = QAction("Vocabulary Notebook", self)
        act_notebook.triggered.connect(self._open_notebook)
        menu.addAction(act_notebook)

        menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self._exit_app)
        menu.addAction(act_exit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def show_and_raise(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_and_raise()

    def _open_notebook(self):
        # Reuse the open notebook; a closed one deletes itself instead of
        # staying alive as a hidden child of this window.
        if self.notebook is None or sip.isdeleted(self.notebook):
            self.notebook = WordNotebookWindow(self)
            self.notebook.setAttribute(Qt.WA_DeleteOnClose)
            self.notebook.words_changed.connect(self._refresh_word_count)
        else:
            self.notebook.load_words()
        self.notebook.show()
        self.notebook.raise_()
        self.notebook.activateWindow()

    def showEvent(self, event):
        # Words can be saved from scan overlays while this window is hidden.
        super().showEvent(event)
        self._refresh_word_count()

    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            if not getattr(self, '_tray_notified', False):
                self.tray_icon.showMessage(
                    "Chinese Screen OCR",
                    "The application continues to run in the background. You can open it by clicking the system tray icon.",
                    QSystemTrayIcon.Information,
                    3000
                )
                self._tray_notified = True
        else:
            event.accept()

    def _exit_app(self):
        self._stop_live()
        if self.pinyin_overlay is not None:
            self.pinyin_overlay.close()
        if self.seamless_overlay is not None:
            self.seamless_overlay.close()
        self.tray_icon.hide()
        QApplication.quit()
