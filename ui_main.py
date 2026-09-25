import sys
import keyboard
import logging
from PyQt5 import sip
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
                             QLabel, QPushButton, QCheckBox, QLineEdit, QDialog,
                             QMessageBox, QProgressDialog, QSystemTrayIcon, QMenu, QAction, QApplication)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer, QRect
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QBrush, QColor, QCursor

from config import load_config, save_config
from ocr_engine import init_ocr, take_screenshot, OCRWorker, LiveScanWorker
from dictionary import segment_ocr_results
from ui_overlay import RegionSelector, OverlayWindow, PinyinOverlayWindow, LivePinyinOverlayWindow
from word_notebook import WordNotebookWindow
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

BTN_P = ("QPushButton{background:#C08B5C;color:#FFF8F0;border:none;border-radius:10px;"
         "font-size:13px;font-weight:bold;padding:0px;}"
         "QPushButton:hover{background:#D69B6C;}"
         "QPushButton:disabled{background:#EADCC9;color:#B0A090;}")

BTN_S = ("QPushButton{background:#EADCC9;color:#4A3F35;border:1px solid #C4B29B;"
         "border-radius:10px;font-size:12px;padding:0px;}"
         "QPushButton:hover{background:#DDCBB6;}"
         "QPushButton:disabled{background:#E8DCCC;color:#B0A090;border:1px solid #D8C8B5;}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chinese Screen OCR")
        self._fit_to_screen()
        self.setStyleSheet("QMainWindow,QWidget{background:#FAF4EB;color:#4A3F35;}")
        self.ocr_ready = False; self.overlay = None; self.pinyin_overlay = None; self._worker = None
        self._active_screen_rect = None; self._ocr_mode = "normal"; self.seamless_overlay = None
        self.live_overlay = None; self._live_worker = None; self._capture_scale = 1.0
        self._progress = None; self.notebook = None
        self.config = load_config()
        self._build(); self._start_init()
        self._setup_hotkey()
        self._setup_tray()

    def _fit_to_screen(self):
        # At high display scaling the logical screen can be shorter than the
        # window; the content then scrolls instead of running off-screen.
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        avail = screen.availableGeometry().height() - 40 if screen else 620
        self.setFixedSize(520, max(300, min(620, avail)))

    def _build(self):
        root = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(root); self.setCentralWidget(scroll)
        vb = QVBoxLayout(root); vb.setContentsMargins(48,40,48,40)
        vb.setSpacing(0); vb.setAlignment(Qt.AlignCenter)
        t = QLabel("Chinese Screen OCR"); t.setFont(QFont("Arial",22,QFont.Bold))
        t.setStyleSheet("color:#4A3F35;"); t.setAlignment(Qt.AlignCenter); vb.addWidget(t)
        s = QLabel("Pleco-style screen reader"); s.setFont(QFont("Arial",11))
        s.setStyleSheet("color:#8B7D6B;"); s.setAlignment(Qt.AlignCenter); vb.addWidget(s)
        vb.addSpacing(24)
        self.status = QLabel("Loading OCR engine...")
        self.status.setAlignment(Qt.AlignCenter); self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#8B6914;background:#F5ECD2;border:1px solid #D2B48C;"
                                  "border-radius:8px;padding:10px 16px;font-size:13px;")
        vb.addWidget(self.status); vb.addSpacing(20)
        
        self.btn_r = QPushButton("Select Region && Scan"); self.btn_r.setFixedHeight(52)
        self.btn_r.setEnabled(False); self.btn_r.setStyleSheet(BTN_P)
        self.btn_r.clicked.connect(self._start_region); vb.addWidget(self.btn_r)
        vb.addSpacing(10)
        
        self.btn_f = QPushButton("Scan Full Screen"); self.btn_f.setFixedHeight(44)
        self.btn_f.setEnabled(False); self.btn_f.setStyleSheet(BTN_S)
        self.btn_f.clicked.connect(self._start_full); vb.addWidget(self.btn_f)
        vb.addSpacing(10)

        self.btn_live = QPushButton("Start Live Pinyin (Game Mode)"); self.btn_live.setFixedHeight(44)
        self.btn_live.setEnabled(False); self.btn_live.setStyleSheet(BTN_S)
        self.btn_live.clicked.connect(self._toggle_live); vb.addWidget(self.btn_live)
        vb.addSpacing(10)

        self.btn_n = QPushButton("Vocabulary Notebook"); self.btn_n.setFixedHeight(44)
        self.btn_n.setStyleSheet(BTN_S)
        self.btn_n.clicked.connect(self._open_notebook); vb.addWidget(self.btn_n)
        vb.addSpacing(15)
        
        self.cb_manga = QCheckBox("Manga Mode (Vertical Text)")
        self.cb_manga.setStyleSheet("color:#4A3F35; font-size:13px;")
        self.cb_manga.setChecked(self.config.get('manga_mode', False))
        self.cb_manga.stateChanged.connect(self._save_manga_mode)
        vb.addWidget(self.cb_manga, alignment=Qt.AlignCenter)
        
        self.cb_deepl = QCheckBox("Enable DeepL Translation (double-click / selection)")
        self.cb_deepl.setStyleSheet("color:#4A3F35; font-size:13px;")
        self.cb_deepl.setChecked(self.config.get('deepl_enabled', False))
        self.cb_deepl.stateChanged.connect(self._save_deepl_enabled)
        vb.addWidget(self.cb_deepl, alignment=Qt.AlignCenter)
        
        dl_layout = QHBoxLayout()
        dl_lbl = QLabel("DeepL API Key (Free):")
        dl_lbl.setStyleSheet("color:#8B7D6B;font-size:12px;")
        self.le_deepl_key = QLineEdit(self.config.get('deepl_api_key', ''))
        self.le_deepl_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.le_deepl_key.setPlaceholderText("Paste your DeepL API key here")
        self.le_deepl_key.setToolTip("Your key is saved only in this computer's app settings.")
        self.le_deepl_key.setStyleSheet("background:#FFF8F0;border:1px solid #D4C5B0;border-radius:4px;padding:2px;")
        self.le_deepl_key.textChanged.connect(self._save_deepl_key)
        dl_layout.addWidget(dl_lbl)
        dl_layout.addWidget(self.le_deepl_key)
        vb.addLayout(dl_layout)
        vb.addSpacing(15)
        
        hl = QHBoxLayout()
        hl.addStretch()
        self.lbl_hk = QLabel(f"Full Screen Hotkey: [ {self.config.get('hotkey', 'alt+s')} ]")
        self.lbl_hk.setStyleSheet("color:#8B7D6B;font-size:12px;")
        hl.addWidget(self.lbl_hk)
        btn_hk = QPushButton("Change")
        btn_hk.setStyleSheet(BTN_S)
        btn_hk.setFixedSize(70, 24)
        btn_hk.clicked.connect(self._change_hotkey)
        hl.addWidget(btn_hk)
        hl.addStretch()
        vb.addLayout(hl)

        phl = QHBoxLayout()
        phl.addStretch()
        self.lbl_phk = QLabel(f"Pinyin Overlay Hotkey: [ {self.config.get('pinyin_hotkey', 'alt+p')} ]")
        self.lbl_phk.setStyleSheet("color:#8B7D6B;font-size:12px;")
        phl.addWidget(self.lbl_phk)
        btn_phk = QPushButton("Change")
        btn_phk.setStyleSheet(BTN_S)
        btn_phk.setFixedSize(70, 24)
        btn_phk.clicked.connect(self._change_pinyin_hotkey)
        phl.addWidget(btn_phk)
        phl.addStretch()
        vb.addLayout(phl)

        shl = QHBoxLayout()
        shl.addStretch()
        self.lbl_shk = QLabel(f"SEAMLESS Mode Hotkey: [ {self.config.get('seamless_hotkey', 'alt+shift+s')} ]")
        self.lbl_shk.setStyleSheet("color:#8B7D6B;font-size:12px;")
        shl.addWidget(self.lbl_shk)
        btn_shk = QPushButton("Change")
        btn_shk.setStyleSheet(BTN_S)
        btn_shk.setFixedSize(70, 24)
        btn_shk.clicked.connect(self._change_seamless_hotkey)
        shl.addWidget(btn_shk)
        shl.addStretch()
        vb.addLayout(shl)

        lhl = QHBoxLayout()
        lhl.addStretch()
        self.lbl_lhk = QLabel(f"Live Pinyin Hotkey: [ {self.config.get('live_hotkey', 'alt+l')} ]")
        self.lbl_lhk.setStyleSheet("color:#8B7D6B;font-size:12px;")
        lhl.addWidget(self.lbl_lhk)
        btn_lhk = QPushButton("Change")
        btn_lhk.setStyleSheet(BTN_S)
        btn_lhk.setFixedSize(70, 24)
        btn_lhk.clicked.connect(self._change_live_hotkey)
        lhl.addWidget(btn_lhk)
        lhl.addStretch()
        vb.addLayout(lhl)

        vb.addStretch()
        hint = QLabel("Hint: double click in selection screen = full screen  |  ESC = cancel")
        hint.setStyleSheet("color:#9B8B7A;font-size:11px;"); hint.setAlignment(Qt.AlignCenter)
        vb.addWidget(hint)

    def _save_manga_mode(self, state):
        self.config['manga_mode'] = bool(state)
        save_config(self.config)

    def _save_deepl_enabled(self, state):
        self.config['deepl_enabled'] = bool(state)
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
            name = 'PaddleOCR'
            self.status.setText(f"  {name} ready - Ready to read Chinese!")
            self.status.setStyleSheet("color:#375623;background:#E2EFDA;border:1px solid #A9D18E;"
                                      "border-radius:8px;padding:10px 16px;font-size:13px;")
            self.btn_r.setEnabled(True); self.btn_f.setEnabled(True); self.btn_live.setEnabled(True)
        else:
            self.status.setText("Failed to load OCR. Check the log file in AppData.")
            self.status.setStyleSheet("color:#C65911;background:#FCE4D6;border:1px solid #F4B084;"
                                      "border-radius:8px;padding:10px 16px;font-size:13px;")

    def _set_buttons(self, enabled: bool):
        self.btn_r.setEnabled(enabled and self.ocr_ready)
        self.btn_f.setEnabled(enabled and self.ocr_ready)

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

    def _start_full(self):
        self._set_buttons(False)
        s = self._screen_rect_for_action()
        self._active_screen_rect = s
        self._ocr_mode = "normal"
        self._on_region(s.x(), s.y(), s.width(), s.height())

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
            self._progress.close()  # an aborted scan's dialog is never closed by its worker
        prog = QProgressDialog("Processing OCR...", None, 0, 0, self)
        prog.setAttribute(Qt.WA_DeleteOnClose)
        self._progress = prog
        prog.setWindowModality(Qt.ApplicationModal)
        prog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        prog.setStyleSheet("QProgressDialog{background:#FAF4EB;border:1px solid #D4C5B0;border-radius:10px;}"
                           "QLabel{color:#4A3F35;padding:20px;font-size:13px;}"); prog.show()
        
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
            word_results = segment_ocr_results(r)
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
                self.tray_icon.showMessage("Chinese Screen OCR", f"SEAMLESS OCR failed: {m}", QSystemTrayIcon.Warning, 5000)
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
        self.hk_listener = HotkeyListener()
        self.hk_listener.triggered.connect(self._start_full_from_hotkey)
        self.hk_listener.set_hotkey(self.config.get('hotkey', 'alt+s'))
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

    def _remove_startup_hotkey_conflicts(self):
        """Migrate an existing config where two modes were assigned one key."""
        bindings = (
            ("live_hotkey", self.lbl_lhk, "Live Pinyin Hotkey"),
            ("seamless_hotkey", self.lbl_shk, "SEAMLESS Mode Hotkey"),
            ("pinyin_hotkey", self.lbl_phk, "Pinyin Overlay Hotkey"),
            ("hotkey", self.lbl_hk, "Full Screen Hotkey"),
        )
        used = set()
        changed = False
        for key, label, prefix in bindings:
            hotkey = self.config.get(key, "").strip()
            if hotkey and hotkey.lower() in used:
                self.config[key] = ""
                label.setText(f"{prefix}: [ disabled ]")
                changed = True
            elif hotkey:
                used.add(hotkey.lower())
        if changed:
            save_config(self.config)
        
    def _start_full_from_hotkey(self):
        if self.ocr_ready and self.btn_f.isEnabled():
            self._start_full()

    def _toggle_pinyin_overlay_from_hotkey(self):
        if self.pinyin_overlay is not None:
            self.pinyin_overlay.close()
            self.pinyin_overlay = None
            self._set_buttons(True)
            return
        if self.ocr_ready and self.btn_f.isEnabled():
            self._start_pinyin_overlay()

    def _toggle_seamless_from_hotkey(self):
        if self.seamless_overlay is not None:
            self._close_seamless()
        elif self.ocr_ready and self.btn_f.isEnabled():
            self._start_seamless()

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
            self._set_buttons(True)
            self.tray_icon.showMessage("Chinese Screen OCR", "SEAMLESS scan found no text.", QSystemTrayIcon.Information, 3000)
            return
        if self.seamless_overlay is not None:
            self.seamless_overlay.close()
        word_results = segment_ocr_results(results)
        overlay = OverlayWindow(image, word_results, main_win=None,
                                screen_rect=self._active_screen_rect, seamless=True,
                                scale=self._capture_scale)
        self.seamless_overlay = overlay

        def closed(*_):
            if self.seamless_overlay is overlay:
                self.seamless_overlay = None
                self._set_buttons(True)
                # Deliberately keep the main window hidden so focus returns to the game/app.
                self.hide()

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
        elif self.ocr_ready:
            self._start_live()

    def _start_live(self):
        s = self._screen_rect_for_action()
        self.live_overlay = LivePinyinOverlayWindow(s)
        self.live_overlay.show()
        physical, _ = to_physical(s)
        self._live_worker = LiveScanWorker(physical,
                                           manga_mode=self.config.get('manga_mode', False))
        self._live_worker.results_changed.connect(self._on_live_results)
        self._live_worker.start()
        self.btn_live.setText("Stop Live Pinyin")
        self.act_live.setText("Stop Live Pinyin")
        # Hide the main window so the game is what's underneath the labels.
        self.hide()

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
        self.btn_live.setText("Start Live Pinyin (Game Mode)")
        self.act_live.setText("Start Live Pinyin")

    def _change_hotkey(self):
        self._read_hotkey(
            title="Press new full screen hotkey...\n(e.g., Ctrl+Shift+A)",
            config_key="hotkey",
            label=self.lbl_hk,
            label_prefix="Full Screen Hotkey",
            listener=self.hk_listener,
        )

    def _change_pinyin_hotkey(self):
        self._read_hotkey(
            title="Press new pinyin overlay hotkey...\n(e.g., Ctrl+Shift+P)",
            config_key="pinyin_hotkey",
            label=self.lbl_phk,
            label_prefix="Pinyin Overlay Hotkey",
            listener=self.pinyin_hk_listener,
        )

    def _change_seamless_hotkey(self):
        self._read_hotkey(
            title="Press new SEAMLESS mode hotkey...\n(e.g., Ctrl+Shift+S)",
            config_key="seamless_hotkey",
            label=self.lbl_shk,
            label_prefix="SEAMLESS Mode Hotkey",
            listener=self.seamless_hk_listener,
        )

    def _change_live_hotkey(self):
        self._read_hotkey(
            title="Press new live pinyin hotkey...\n(e.g., Ctrl+Shift+L)",
            config_key="live_hotkey",
            label=self.lbl_lhk,
            label_prefix="Live Pinyin Hotkey",
            listener=self.live_hk_listener,
        )

    def _read_hotkey(self, title, config_key, label, label_prefix, listener):
        self.btn_r.setEnabled(False); self.btn_f.setEnabled(False)
        msg = QDialog(self, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        msg.setAttribute(Qt.WA_DeleteOnClose)
        msg.setStyleSheet("background:#FAF4EB; border:1px solid #C08B5C; border-radius:10px;")
        l = QVBoxLayout(msg)
        info = QLabel(title)
        info.setStyleSheet("color:#4A3F35; font-size:14px; padding:20px;")
        info.setAlignment(Qt.AlignCenter)
        l.addWidget(info)
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
            if hk:
                self._clear_hotkey_conflicts(config_key, hk)
                self.config[config_key] = hk
                save_config(self.config)
                label.setText(f"{label_prefix}: [ {hk} ]")
                listener.set_hotkey(hk)
        self.hk_reader.done.connect(on_done)
        self.hk_reader.start()

    def _clear_hotkey_conflicts(self, config_key, hotkey):
        """One physical shortcut must control exactly one OCR mode."""
        bindings = {
            "hotkey": (self.hk_listener, self.lbl_hk, "Full Screen Hotkey"),
            "pinyin_hotkey": (self.pinyin_hk_listener, self.lbl_phk, "Pinyin Overlay Hotkey"),
            "seamless_hotkey": (self.seamless_hk_listener, self.lbl_shk, "SEAMLESS Mode Hotkey"),
            "live_hotkey": (self.live_hk_listener, self.lbl_lhk, "Live Pinyin Hotkey"),
        }
        for key, (listener, label, prefix) in bindings.items():
            if key != config_key and self.config.get(key, "").lower() == hotkey.lower():
                listener.set_hotkey("")
                self.config[key] = ""
                label.setText(f"{prefix}: [ disabled ]")

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#C08B5C")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 32, 32, 8, 8)
        painter.setPen(QColor("#FAF4EB"))
        font = QFont("Microsoft YaHei", 18, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "中")
        painter.end()
        
        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("Chinese Screen OCR")

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: #FAF4EB; color: #4A3F35; border: 1px solid #D4C5B0; font-size: 12px; }"
            "QMenu::item:selected { background: #EADCC9; color: #4A3F35; }"
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
        else:
            self.notebook.load_words()
        self.notebook.show()
        self.notebook.raise_()
        self.notebook.activateWindow()

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
