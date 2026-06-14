import os
import json
import logging
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, 
                             QPushButton, QFrame, QLabel, QScrollArea, QWidget, QListWidgetItem, QApplication)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

logger = logging.getLogger("OCRApp")

SAVE_FILE_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_words.json")
SAVE_FILE_TXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_words.txt")

def migrate_and_load_saved_words():
    words = []
    if os.path.exists(SAVE_FILE_JSON):
        try:
            with open(SAVE_FILE_JSON, 'r', encoding='utf-8') as f:
                words = json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON saved words: {e}")
            
    if os.path.exists(SAVE_FILE_TXT):
        try:
            migrated = False
            with open(SAVE_FILE_TXT, 'r', encoding='utf-8') as f:
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
                with open(SAVE_FILE_JSON, 'w', encoding='utf-8') as f:
                    json.dump(words, f, ensure_ascii=False, indent=2)
                logger.info("[MIGRATION] saved_words.txt migrated to json!")
                
            try:
                bak_path = SAVE_FILE_TXT + ".bak"
                if os.path.exists(bak_path):
                    os.remove(bak_path)
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
        with open(SAVE_FILE_JSON, 'w', encoding='utf-8') as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving word: {e}")
        return False

class WordNotebookWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("My Vocabulary Notebook")
        self.resize(750, 500)
        self.setStyleSheet(
            "QDialog { background: #FAF4EB; color: #4A3F35; }"
            "QLineEdit { background: #FAF4EB; color: #4A3F35; border: 1px solid #D4C5B0; border-radius: 6px; padding: 6px 10px; font-size: 13px; }"
            "QListWidget { background: #FAF4EB; color: #4A3F35; border: 1px solid #D4C5B0; border-radius: 8px; padding: 5px; font-size: 13px; }"
            "QListWidget::item { border-bottom: 1px solid #EADCC9; padding: 8px; border-radius: 4px; }"
            "QListWidget::item:selected { background: #EADCC9; color: #4A3F35; }"
            "QListWidget::item:hover { background: #F4EFE6; }"
            "QPushButton { background: #EADCC9; color: #4A3F35; border: 1px solid #C4B29B; border-radius: 6px; padding: 6px 12px; font-size: 12px; }"
            "QPushButton:hover { background: #DDCBB6; }"
        )
        self.words_data = []
        self._init_ui()
        self.load_words()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Word, Pinyin or Meaning...")
        self.search_input.textChanged.connect(self.filter_words)
        left_layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.list_widget)

        left_buttons = QHBoxLayout()
        self.btn_export = QPushButton("Export to Anki")
        self.btn_export.setStyleSheet("QPushButton { background: #6B8E4E; color: #FFF8F0; font-weight: bold; border: none; } QPushButton:hover { background: #7DA05E; }")
        self.btn_export.clicked.connect(self.export_anki)
        left_buttons.addWidget(self.btn_export)

        self.btn_clear_all = QPushButton("Clear All")
        self.btn_clear_all.setStyleSheet("QPushButton { background: #A8554F; color: #FFF8F0; font-weight: bold; border: none; } QPushButton:hover { background: #B9665F; }")
        self.btn_clear_all.clicked.connect(self.clear_all_words)
        left_buttons.addWidget(self.btn_clear_all)

        left_layout.addLayout(left_buttons)
        main_layout.addLayout(left_layout, stretch=2)

        self.right_frame = QFrame()
        self.right_frame.setStyleSheet("QFrame { background: #F4EFE6; border: 1px solid #D4C5B0; border-radius: 10px; }")
        right_layout = QVBoxLayout(self.right_frame)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        self.lbl_word = QLabel("Word")
        self.lbl_word.setFont(QFont("Microsoft YaHei", 28, QFont.Bold))
        self.lbl_word.setStyleSheet("color: #4A3F35; border: none; background: transparent;")
        self.lbl_word.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.lbl_word)

        self.lbl_pinyin = QLabel("Pinyin")
        self.lbl_pinyin.setFont(QFont("Arial", 14, QFont.Bold))
        self.lbl_pinyin.setStyleSheet("color: #8B6914; border: none; background: transparent;")
        self.lbl_pinyin.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.lbl_pinyin)

        self.lbl_meaning = QLabel("Meaning")
        self.lbl_meaning.setFont(QFont("Arial", 12))
        self.lbl_meaning.setStyleSheet("color: #4A3F35; border: none; background: transparent;")
        self.lbl_meaning.setAlignment(Qt.AlignCenter)
        self.lbl_meaning.setWordWrap(True)
        right_layout.addWidget(self.lbl_meaning)

        right_layout.addStretch()

        self.btn_copy = QPushButton("Copy Text")
        self.btn_copy.clicked.connect(self.copy_current_word)
        right_layout.addWidget(self.btn_copy)

        self.btn_delete = QPushButton("Delete This Word")
        self.btn_delete.setStyleSheet("QPushButton { background: #D98880; color: #FFF; border: none; } QPushButton:hover { background: #E6B0AA; }")
        self.btn_delete.clicked.connect(self.delete_current_word)
        right_layout.addWidget(self.btn_delete)

        main_layout.addWidget(self.right_frame, stretch=3)

    def load_words(self):
        self.words_data = migrate_and_load_saved_words()
        self.filter_words(self.search_input.text())

    def filter_words(self, text):
        self.list_widget.clear()
        text = text.lower()
        for i, w in enumerate(self.words_data):
            if text in w['word'].lower() or text in w['pinyin'].lower() or text in w['meanings'].lower():
                item = QListWidgetItem(f"{w['word']}  ({w['pinyin']})")
                item.setData(Qt.UserRole, i)
                self.list_widget.addItem(item)
        
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self.lbl_word.setText("-")
            self.lbl_pinyin.setText("-")
            self.lbl_meaning.setText("Not Found")

    def on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        idx = items[0].data(Qt.UserRole)
        w = self.words_data[idx]
        self.lbl_word.setText(w['word'])
        self.lbl_pinyin.setText(w['pinyin'])
        self.lbl_meaning.setText(w['meanings'])

    def copy_current_word(self):
        items = self.list_widget.selectedItems()
        if items:
            idx = items[0].data(Qt.UserRole)
            w = self.words_data[idx]
            QApplication.clipboard().setText(f"{w['word']} [{w['pinyin']}] : {w['meanings']}")

    def delete_current_word(self):
        items = self.list_widget.selectedItems()
        if items:
            idx = items[0].data(Qt.UserRole)
            del self.words_data[idx]
            self._save_to_disk()
            self.filter_words(self.search_input.text())

    def clear_all_words(self):
        self.words_data.clear()
        self._save_to_disk()
        self.filter_words("")

    def _save_to_disk(self):
        try:
            with open(SAVE_FILE_JSON, 'w', encoding='utf-8') as f:
                json.dump(self.words_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving to disk: {e}")

    def export_anki(self):
        if not self.words_data: return
        export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anki_export.csv")
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                for w in self.words_data:
                    clean_meaning = w['meanings'].replace('"', '""')
                    f.write(f"\"{w['word']}\",\"{w['pinyin']}\",\"{clean_meaning}\"\n")
            
            import subprocess
            subprocess.Popen(f'explorer /select,"{export_path}"')
        except Exception as e:
            logger.error(f"Error exporting Anki CSV: {e}")
