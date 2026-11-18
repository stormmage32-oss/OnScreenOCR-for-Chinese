import os
import json
import logging
import datetime
import html
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QPushButton,
                             QFrame, QLabel, QScrollArea, QListWidgetItem, QApplication, QStackedWidget,
                             QStyledItemDelegate, QStyle, QShortcut, QMessageBox)
from PyQt5.QtCore import Qt, QSize, QRect, QRectF, pyqtSignal
from PyQt5.QtGui import QFont, QFontMetrics, QPainter, QColor, QKeySequence
from theme import BASE_QSS, BG, SURFACE, BORDER, TEXT, MUTED, FAINT, ACCENT, CJK_FONT
from app_paths import install_dir_path, user_data_path

logger = logging.getLogger("OCRApp")

SAVE_FILE_JSON = user_data_path("saved_words.json")
SAVE_FILE_TXT = user_data_path("saved_words.txt")
LEGACY_SAVE_FILE_JSON = install_dir_path("saved_words.json")
LEGACY_SAVE_FILE_TXT = install_dir_path("saved_words.txt")

def migrate_and_load_saved_words():
    words = []
    load_json = SAVE_FILE_JSON if os.path.exists(SAVE_FILE_JSON) else LEGACY_SAVE_FILE_JSON
    if os.path.exists(load_json):
        try:
            with open(load_json, 'r', encoding='utf-8') as f:
                words = json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON saved words: {e}")
            
    load_txt = SAVE_FILE_TXT if os.path.exists(SAVE_FILE_TXT) else LEGACY_SAVE_FILE_TXT
    if os.path.exists(load_txt):
        try:
            migrated = False
            with open(load_txt, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 2:
                        word_txt = parts[0]
                        py_txt = parts[1]
                        meanings_txt = parts[2] if len(parts) >= 3 else ""
                        ts_txt = parts[3] if len(parts) >= 4 else datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        if not any(w['word'] == word_txt for w in words):
                            words.append({"word": word_txt, "pinyin": py_txt, "meanings": meanings_txt, "timestamp": ts_txt})
                            migrated = True
            
            if migrated:
                os.makedirs(os.path.dirname(SAVE_FILE_JSON), exist_ok=True)
                with open(SAVE_FILE_JSON, 'w', encoding='utf-8') as f:
                    json.dump(words, f, ensure_ascii=False, indent=2)
                logger.info("[MIGRATION] saved_words.txt migrated to json!")
                
            try:
                bak_path = SAVE_FILE_TXT + ".bak"
                if load_txt == SAVE_FILE_TXT and os.path.exists(bak_path):
                    os.remove(bak_path)
                if load_txt == SAVE_FILE_TXT:
                    os.rename(SAVE_FILE_TXT, bak_path)
            except Exception as re_err:
                logger.error(f"Error renaming txt: {re_err}")
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            
    return words

def save_word(text: str, py: str, meanings: str = ''):
    words = migrate_and_load_saved_words()
    if any(w['word'] == text for w in words):
        logger.info(f"Word '{text}' already saved.")
        return False
        
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if isinstance(meanings, list):
        meanings = " · ".join(meanings)
        
    words.append({"word": text, "pinyin": py, "meanings": meanings, "timestamp": ts})
    try:
        os.makedirs(os.path.dirname(SAVE_FILE_JSON), exist_ok=True)
        with open(SAVE_FILE_JSON, 'w', encoding='utf-8') as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving word: {e}")
        return False


# ---------------------------------------------------------------------------
# Notebook window
# ---------------------------------------------------------------------------

ROLE_INDEX = Qt.UserRole
ROLE_WORD = Qt.UserRole + 1
ROLE_PINYIN = Qt.UserRole + 2
ROLE_DATE = Qt.UserRole + 3

NOTEBOOK_QSS = BASE_QSS + f"""
QDialog {{ background: {BG}; }}
QLabel#title {{ font-size: 18px; font-weight: 600; }}
QLabel#count {{ color: {MUTED}; font-size: 12px; }}
QListWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; outline: none; padding: 4px; }}
QFrame#detail {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}
QLabel#word {{ font-family: "{CJK_FONT}"; font-size: 40px; }}
QLabel#pinyin {{ color: {ACCENT}; font-size: 17px; }}
QLabel#fieldLabel {{ color: {MUTED}; font-size: 11px; font-weight: 600; }}
QLabel#meaning {{ font-size: 13px; }}
QLabel#meta {{ color: {FAINT}; font-size: 11px; }}
QLabel#empty {{ color: {MUTED}; font-size: 13px; }}
QFrame#divider {{ background: #EDEDED; border: none; max-height: 1px; min-height: 1px; }}
"""


class WordItemDelegate(QStyledItemDelegate):
    """Two-line row: hanzi on top, pinyin below, saved date on the right."""

    ROW_H = 54

    def sizeHint(self, option, index):
        return QSize(0, self.ROW_H)

    def paint(self, p, option, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = option.rect.adjusted(0, 1, 0, -1)
        selected = option.state & QStyle.State_Selected
        hover = option.state & QStyle.State_MouseOver
        if selected or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#EAF2FB" if selected else "#F5F5F5"))
            p.drawRoundedRect(QRectF(r), 4, 4)
        if selected:
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(QRectF(r.left(), r.top() + 14, 3, r.height() - 28), 1.5, 1.5)

        left = r.left() + 14
        date = index.data(ROLE_DATE) or ""
        f_date = QFont("Segoe UI"); f_date.setPixelSize(11)
        fm_date = QFontMetrics(f_date)
        date_w = fm_date.horizontalAdvance(date) if date else 0
        text_w = r.width() - 28 - (date_w + 12 if date else 0)

        f_word = QFont(CJK_FONT); f_word.setPixelSize(16)
        fm = QFontMetrics(f_word)
        p.setFont(f_word); p.setPen(QColor(TEXT))
        p.drawText(QRect(left, r.top() + 7, text_w, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   fm.elidedText(index.data(ROLE_WORD) or "", Qt.ElideRight, text_w))

        f_py = QFont("Segoe UI"); f_py.setPixelSize(12)
        fm_py = QFontMetrics(f_py)
        p.setFont(f_py); p.setPen(QColor(MUTED))
        p.drawText(QRect(left, r.top() + 29, text_w, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   fm_py.elidedText(index.data(ROLE_PINYIN) or "", Qt.ElideRight, text_w))

        if date:
            p.setFont(f_date); p.setPen(QColor(FAINT))
            p.drawText(QRect(r.right() - 14 - date_w, r.top() + 7, date_w, 22),
                       Qt.AlignRight | Qt.AlignVCenter, date)
        p.restore()


def _split_meanings(text):
    text = (text or "").strip()
    if not text:
        return []
    for sep in (" · ", "/", ";"):
        if sep in text:
            return [m.strip() for m in text.split(sep) if m.strip()]
    return [text]


class WordNotebookWindow(QDialog):
    words_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Saved Words")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint
                            | Qt.WindowMinMaxButtonsHint)
        self.resize(820, 540)
        self.setMinimumSize(640, 420)
        self.setStyleSheet(NOTEBOOK_QSS)
        self.words_data = []
        self._init_ui()
        self.load_words()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(14)

        # Toolbar
        bar = QHBoxLayout(); bar.setSpacing(8)
        title = QLabel("Saved words"); title.setObjectName("title")
        self.lbl_count = QLabel(); self.lbl_count.setObjectName("count")
        bar.addWidget(title); bar.addSpacing(6)
        bar.addWidget(self.lbl_count, 0, Qt.AlignVCenter)
        bar.addStretch()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search hanzi, pinyin or meaning")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(240)
        self.search_input.textChanged.connect(self.filter_words)
        bar.addWidget(self.search_input)
        self.btn_export = QPushButton("Export to Anki"); self.btn_export.setObjectName("btn")
        self.btn_export.setToolTip("Save a CSV (hanzi, pinyin, meaning) you can import into Anki")
        self.btn_export.clicked.connect(self.export_anki)
        bar.addWidget(self.btn_export)
        self.btn_clear_all = QPushButton("Clear all"); self.btn_clear_all.setObjectName("btnDanger")
        self.btn_clear_all.clicked.connect(self.clear_all_words)
        bar.addWidget(self.btn_clear_all)
        root.addLayout(bar)

        body = QHBoxLayout(); body.setSpacing(12)

        self.list_stack = QStackedWidget()
        self.list_widget = QListWidget()
        self.list_widget.setItemDelegate(WordItemDelegate(self.list_widget))
        self.list_widget.setMouseTracking(True)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.lbl_empty = QLabel(); self.lbl_empty.setObjectName("empty")
        self.lbl_empty.setAlignment(Qt.AlignCenter); self.lbl_empty.setWordWrap(True)
        empty_box = QFrame(); empty_box.setObjectName("detail")
        el = QVBoxLayout(empty_box); el.setContentsMargins(24, 24, 24, 24); el.addWidget(self.lbl_empty)
        self.list_stack.addWidget(self.list_widget)
        self.list_stack.addWidget(empty_box)
        body.addWidget(self.list_stack, 5)

        self.right_frame = QFrame(); self.right_frame.setObjectName("detail")
        rl = QVBoxLayout(self.right_frame)
        rl.setContentsMargins(24, 20, 24, 18)
        rl.setSpacing(4)
        self.lbl_word = QLabel(); self.lbl_word.setObjectName("word")
        self.lbl_word.setWordWrap(True)
        self.lbl_word.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_pinyin = QLabel(); self.lbl_pinyin.setObjectName("pinyin")
        self.lbl_pinyin.setWordWrap(True)
        self.lbl_pinyin.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rl.addWidget(self.lbl_word)
        rl.addWidget(self.lbl_pinyin)
        rl.addSpacing(14)
        div = QFrame(); div.setObjectName("divider"); rl.addWidget(div)
        rl.addSpacing(12)
        lbl_m = QLabel("MEANING"); lbl_m.setObjectName("fieldLabel"); rl.addWidget(lbl_m)
        rl.addSpacing(4)
        self.lbl_meaning = QLabel(); self.lbl_meaning.setObjectName("meaning")
        self.lbl_meaning.setWordWrap(True)
        self.lbl_meaning.setTextFormat(Qt.RichText)
        self.lbl_meaning.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_meaning.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea, QScrollArea > QWidget > QWidget {{ background: {SURFACE}; }}")
        scroll.setWidget(self.lbl_meaning)
        rl.addWidget(scroll, 1)
        rl.addSpacing(8)
        foot = QHBoxLayout(); foot.setSpacing(8)
        self.lbl_meta = QLabel(); self.lbl_meta.setObjectName("meta")
        foot.addWidget(self.lbl_meta); foot.addStretch()
        self.btn_copy = QPushButton("Copy"); self.btn_copy.setObjectName("btn")
        self.btn_copy.setToolTip("Copy word, pinyin and meaning (Ctrl+C)")
        self.btn_copy.clicked.connect(self.copy_current_word)
        self.btn_delete = QPushButton("Delete"); self.btn_delete.setObjectName("btnDanger")
        self.btn_delete.setToolTip("Delete this word (Del)")
        self.btn_delete.clicked.connect(self.delete_current_word)
        foot.addWidget(self.btn_copy); foot.addWidget(self.btn_delete)
        rl.addLayout(foot)
        body.addWidget(self.right_frame, 6)

        root.addLayout(body, 1)

        QShortcut(QKeySequence.Delete, self.list_widget, self.delete_current_word)
        QShortcut(QKeySequence.Copy, self.list_widget, self.copy_current_word)
        QShortcut(QKeySequence.Find, self, self.search_input.setFocus)

    # ---------------------------------------------------------------- data

    def load_words(self):
        self.words_data = migrate_and_load_saved_words()
        self.filter_words(self.search_input.text())

    def _selected_index(self):
        items = self.list_widget.selectedItems()
        return items[0].data(ROLE_INDEX) if items else None

    def filter_words(self, text, keep_row=0):
        self.list_widget.clear()
        text = text.lower().strip()
        # Newest first.
        for i in range(len(self.words_data) - 1, -1, -1):
            w = self.words_data[i]
            word, py, mean = w.get('word', ''), w.get('pinyin', ''), w.get('meanings', '')
            if text and not (text in word.lower() or text in py.lower() or text in mean.lower()):
                continue
            item = QListWidgetItem()
            item.setData(ROLE_INDEX, i)
            item.setData(ROLE_WORD, word)
            item.setData(ROLE_PINYIN, py)
            item.setData(ROLE_DATE, (w.get('timestamp') or '')[:10])
            self.list_widget.addItem(item)

        total = len(self.words_data)
        shown = self.list_widget.count()
        self.lbl_count.setText(f"{shown} of {total}" if text else f"{total} word" + ("" if total == 1 else "s"))
        self.btn_export.setEnabled(total > 0)
        self.btn_clear_all.setEnabled(total > 0)

        if shown:
            self.list_stack.setCurrentIndex(0)
            self.list_widget.setCurrentRow(min(keep_row, shown - 1))
        else:
            self.list_stack.setCurrentIndex(1)
            self.lbl_empty.setText("No matches." if total else
                                   "No saved words yet.\n\nAfter a scan, click a word and save it. "
                                   "It will show up here.")
            self._show_word(None)

    def _show_word(self, w):
        has = w is not None
        self.right_frame.setVisible(has)
        if not has:
            return
        self.lbl_word.setText(w.get('word', ''))
        self.lbl_pinyin.setText(w.get('pinyin', ''))
        meanings = _split_meanings(w.get('meanings', ''))
        if meanings:
            rows = "".join(
                f"<tr><td style='color:{FAINT};padding:0 10px 6px 0;'>{n}</td>"
                f"<td style='padding-bottom:6px;'>{html.escape(m)}</td></tr>"
                for n, m in enumerate(meanings, 1))
            self.lbl_meaning.setText(f"<table cellspacing='0'>{rows}</table>")
        else:
            self.lbl_meaning.setText(f"<span style='color:{FAINT};'>No meaning saved.</span>")
        ts = w.get('timestamp', '')
        self.lbl_meta.setText(f"Saved {ts}" if ts else "")

    def on_selection_changed(self):
        idx = self._selected_index()
        if idx is not None:
            self._show_word(self.words_data[idx])

    def copy_current_word(self):
        idx = self._selected_index()
        if idx is not None:
            w = self.words_data[idx]
            QApplication.clipboard().setText(f"{w['word']} [{w['pinyin']}] : {w['meanings']}")

    def delete_current_word(self):
        idx = self._selected_index()
        if idx is None:
            return
        row = self.list_widget.currentRow()
        del self.words_data[idx]
        self._save_to_disk()
        self.filter_words(self.search_input.text(), keep_row=row)

    def clear_all_words(self):
        if not self.words_data:
            return
        n = len(self.words_data)
        ok = QMessageBox.question(self, "Clear all words",
                                  f"Delete all {n} saved words? This cannot be undone.",
                                  QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if ok != QMessageBox.Yes:
            return
        self.words_data.clear()
        self._save_to_disk()
        self.filter_words("")

    def _save_to_disk(self):
        try:
            os.makedirs(os.path.dirname(SAVE_FILE_JSON), exist_ok=True)
            with open(SAVE_FILE_JSON, 'w', encoding='utf-8') as f:
                json.dump(self.words_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving to disk: {e}")
        self.words_changed.emit()

    def export_anki(self):
        if not self.words_data: return
        export_path = user_data_path("anki_export.csv")
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                for w in self.words_data:
                    clean_meaning = w['meanings'].replace('"', '""')
                    f.write(f"\"{w['word']}\",\"{w['pinyin']}\",\"{clean_meaning}\"\n")

            import subprocess
            subprocess.Popen(f'explorer /select,"{export_path}"')
        except Exception as e:
            logger.error(f"Error exporting Anki CSV: {e}")
            QMessageBox.warning(self, "Export failed", str(e))
