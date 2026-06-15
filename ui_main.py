import sys
import keyboard
import logging
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QCheckBox, QLineEdit, QDialog,
                             QMessageBox, QProgressDialog, QSystemTrayIcon, QMenu, QAction, QApplication)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QBrush, QColor

from config import load_config, save_config
from ocr_engine import init_ocr, take_screenshot, OCRWorker
from dictionary import segment_ocr_results
from ui_overlay import RegionSelector, OverlayWindow
from word_notebook import WordNotebookWindow

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
        self.setFixedSize(480, 440)
        self.setStyleSheet("QMainWindow,QWidget{background:#FAF4EB;color:#4A3F35;}")
        self.ocr_ready = False; self.overlay = None; self._worker = None
        self.config = load_config()
        self._build(); self._start_init()
        self._setup_hotkey()
        self._setup_tray()

    def _build(self):
        root = QWidget(); self.setCentralWidget(root)
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

        self.btn_n = QPushButton("Vocabulary Notebook"); self.btn_n.setFixedHeight(44)
        self.btn_n.setStyleSheet(BTN_S)
        self.btn_n.clicked.connect(self._open_notebook); vb.addWidget(self.btn_n)
        vb.addSpacing(15)
        
        self.cb_manga = QCheckBox("Manga Mode (Vertical Text)")
        self.cb_manga.setStyleSheet("color:#4A3F35; font-size:13px;")
        self.cb_manga.setChecked(self.config.get('manga_mode', False))
        self.cb_manga.stateChanged.connect(self._save_manga_mode)
        vb.addWidget(self.cb_manga, alignment=Qt.AlignCenter)
        
        self.cb_deepl = QCheckBox("Enable DeepL Translation (EN)")
        self.cb_deepl.setStyleSheet("color:#4A3F35; font-size:13px;")
        self.cb_deepl.setChecked(self.config.get('deepl_enabled', False))
        self.cb_deepl.stateChanged.connect(self._save_deepl_enabled)
        vb.addWidget(self.cb_deepl, alignment=Qt.AlignCenter)
        
        dl_layout = QHBoxLayout()
        dl_lbl = QLabel("DeepL API Key:")
        dl_lbl.setStyleSheet("color:#8B7D6B;font-size:12px;")
        self.le_deepl_key = QLineEdit(self.config.get('deepl_api_key', ''))
        self.le_deepl_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
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
            self.btn_r.setEnabled(True); self.btn_f.setEnabled(True)
        else:
            self.status.setText("Failed to load OCR. Check the log file in AppData.")
            self.status.setStyleSheet("color:#C65911;background:#FCE4D6;border:1px solid #F4B084;"
                                      "border-radius:8px;padding:10px 16px;font-size:13px;")

    def _set_buttons(self, enabled: bool):
        self.btn_r.setEnabled(enabled and self.ocr_ready)
        self.btn_f.setEnabled(enabled and self.ocr_ready)

    def _start_region(self):
        self._set_buttons(False)
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
        screen = QApplication.primaryScreen()
        s = screen.geometry()
        self._on_region(s.x(), s.y(), s.width(), s.height())

    def _on_region(self, x, y, w, h):
        QTimer.singleShot(150, lambda: self._do_cap(x,y,w,h))

    def _do_cap(self, x, y, w, h):
        try: img = take_screenshot((x,y,w,h))
        except Exception as e:
            self.show(); self._set_buttons(True)
            QMessageBox.critical(self,"Error",f"Failed to take screenshot:\n{e}"); return
        self._run_ocr(img)

    def _run_ocr(self, img):
        prog = QProgressDialog("Processing OCR...", None, 0, 0, self)
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

        def done(r):
            prog.close(); self.show(); self._set_buttons(True)
            if not r: QMessageBox.information(self,"Result","No text found."); return
            word_results = segment_ocr_results(r)
            self.overlay = OverlayWindow(img, word_results, main_win=self)
            self.overlay.show()

        def err(m):
            prog.close(); self.show(); self._set_buttons(True)
            QMessageBox.critical(self,"OCR Error", m)

        w.finished.connect(done); w.error.connect(err); w.start()

    def _setup_hotkey(self):
        self.hk_listener = HotkeyListener()
        self.hk_listener.triggered.connect(self._start_full_from_hotkey)
        self.hk_listener.set_hotkey(self.config.get('hotkey', 'alt+s'))
        
    def _start_full_from_hotkey(self):
        if self.ocr_ready and self.btn_f.isEnabled():
            self._start_full()

    def _change_hotkey(self):
        self.btn_r.setEnabled(False); self.btn_f.setEnabled(False)
        msg = QDialog(self, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        msg.setStyleSheet("background:#FAF4EB; border:1px solid #C08B5C; border-radius:10px;")
        l = QVBoxLayout(msg)
        info = QLabel("Press new hotkey...\n(e.g., Ctrl+Shift+A)")
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
                self.config['hotkey'] = hk
                save_config(self.config)
                self.lbl_hk.setText(f"Full Screen Hotkey: [ {hk} ]")
                self.hk_listener.set_hotkey(hk)
        self.hk_reader.done.connect(on_done)
        self.hk_reader.start()

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
        self.notebook = WordNotebookWindow(self)
        self.notebook.show()

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
        self.tray_icon.hide()
        QApplication.quit()
