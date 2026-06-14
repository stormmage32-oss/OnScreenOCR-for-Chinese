from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication, QPushButton, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QPoint, QTimer, QPropertyAnimation
from PyQt5.QtGui import QFont

from dictionary import lookup_word, get_pinyin, get_derived_hsk_level, HSK_COLORS, HSK_LABELS, lookup_hsk, lookup_cedict
from translation import TranslationWorker
from word_notebook import save_word
from config import load_config

def _clamp_popup(popup, ref_widget=None):
    popup.adjustSize()
    if ref_widget:
        screen = QApplication.screenAt(ref_widget.mapToGlobal(QPoint(0, 0))) or QApplication.primaryScreen()
    else:
        screen = QApplication.screenAt(popup.pos()) or QApplication.primaryScreen()
    screen_rect = screen.geometry()
    
    g = popup.geometry()
    x, y, w, h = g.x(), g.y(), g.width(), g.height()
    margin = 8
    if x + w > screen_rect.right() - margin:
        x = screen_rect.right() - w - margin
    if x < screen_rect.left() + margin:
        x = screen_rect.left() + margin
    if y + h > screen_rect.bottom() - margin:
        y = screen_rect.bottom() - h - margin
    if y < screen_rect.top() + margin:
        y = screen_rect.top() + margin
    popup.move(x, y)

class CharCardWidget(QFrame):
    def __init__(self, ch: str, parent=None):
        super().__init__(parent)
        self.ch = ch
        info, src = lookup_word(ch)

        self.setStyleSheet(
            "QFrame{background:#FFF8F0;border:1px solid #D4C5B0;border-radius:10px;}"
            "QFrame:hover{background:#F5EFE6;border:1px solid #C08B5C;}"
        )
        self.setCursor(Qt.PointingHandCursor)
        fl = QVBoxLayout(self)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(2)

        char_lvl, _ = get_derived_hsk_level(ch)

        ch_lbl = QLabel(ch)
        f_size = 26 if len(ch) == 1 else 20 if len(ch) == 2 else 16
        ch_lbl.setFont(QFont("Microsoft YaHei", f_size, QFont.Bold))
        ch_lbl.setAlignment(Qt.AlignCenter)
        ch_lbl.setStyleSheet(f"color:{HSK_COLORS.get(char_lvl, '#4A3F35')};background:transparent;")
        fl.addWidget(ch_lbl)

        if char_lvl > 0:
            hsk_text = f"HSK {char_lvl}" if char_lvl != 7 else "HSK 7-9"
        else:
            hsk_text = "Non-HSK"
        card_badge = QLabel(hsk_text)
        card_badge.setFont(QFont("Arial", 8, QFont.Bold))
        card_badge.setAlignment(Qt.AlignCenter)
        card_badge_color = HSK_COLORS.get(char_lvl, '#45475a')
        card_badge.setStyleSheet(f"color:#FFF8F0;background:{card_badge_color};border-radius:4px;padding:1px 4px;font-size:9px;")
        fl.addWidget(card_badge, alignment=Qt.AlignCenter)

        py_str = info.get('pinyin', '') if info else ''
        if not py_str:
            py_str = get_pinyin(ch)
        if py_str:
            py_lbl = QLabel(py_str)
            py_lbl.setFont(QFont("Arial", 10))
            py_lbl.setAlignment(Qt.AlignCenter)
            py_lbl.setStyleSheet("color:#8B6914;background:transparent;")
            fl.addWidget(py_lbl)

        meanings = info.get('meanings', []) if info else []
        if meanings:
            m_text = ' / '.join(str(m) for m in meanings[:2])
            if len(m_text) > 38:
                m_text = m_text[:36] + '…'
            m_lbl = QLabel(m_text)
            m_lbl.setFont(QFont("Arial", 9))
            m_lbl.setWordWrap(True)
            m_lbl.setAlignment(Qt.AlignCenter)
            m_lbl.setStyleSheet("color:#6B5D4F;background:transparent;")
            fl.addWidget(m_lbl)
        else:
            m_lbl = QLabel("—")
            m_lbl.setFont(QFont("Arial", 9))
            m_lbl.setAlignment(Qt.AlignCenter)
            m_lbl.setStyleSheet("color:#9B8B7A;background:transparent;")
            fl.addWidget(m_lbl)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            e.accept()
            gpos = e.globalPos()
            QTimer.singleShot(30, lambda: self._open_char_popup(gpos))

    def _open_char_popup(self, global_pos):
        result = {'text': self.ch, 'confidence': 1.0, 'original_sentence': ''}
        popup = DetailPopup(result, parent=None)
        popup.adjustSize()
        px = global_pos.x() - popup.width() // 2
        py = global_pos.y() - popup.height() - 10
        popup.move(px, py)
        _clamp_popup(popup)
        popup.show()


class DetailPopup(QDialog):
    def __init__(self, result: dict, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        text = result['text']
        conf = result.get('confidence', 0)
        info, src = lookup_word(text)
        if info is None: info = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(); card.setObjectName("card")
        card.setStyleSheet("QFrame#card{background:#FAF4EB;border:1px solid #D4C5B0;border-radius:14px;}")
        cl = QVBoxLayout(card); cl.setContentsMargins(18, 16, 18, 16); cl.setSpacing(10)

        hsk_level, is_derived = get_derived_hsk_level(text)
        hsk_color = HSK_COLORS.get(hsk_level, '#45475a')
        
        if hsk_level > 0:
            hsk_label = HSK_LABELS.get(hsk_level, 'Non-HSK')
            if is_derived and len(text) > 1:
                hsk_label += ' (Character)'
        else:
            hsk_label = 'Non-HSK'

        badge = QLabel(hsk_label)
        badge.setFont(QFont("Arial", 10, QFont.Bold))
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"color:#FFF8F0;background:{hsk_color};border-radius:10px;"
                            f"padding:3px 12px;font-size:11px;font-weight:bold;")
        cl.addWidget(badge, alignment=Qt.AlignCenter)

        words = result.get('words', [])
        if not words or len(words) == 1:
            components = list(text)
        else:
            components = words

        if len(components) >= 2:
            comp_row = QHBoxLayout()
            comp_row.setSpacing(8)
            for comp in components:
                if any('\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf' for ch in comp):
                    comp_row.addWidget(CharCardWidget(comp))
            cl.addLayout(comp_row)

            sep = QFrame(); sep.setFixedHeight(1)
            sep.setStyleSheet("background:#E0D5C5;margin:2px 0;"); cl.addWidget(sep)

        main_row = QHBoxLayout()
        main_row.setAlignment(Qt.AlignCenter)

        lbl = QLabel(text)
        lbl.setFont(QFont("Microsoft YaHei", 30, QFont.Bold))
        lbl.setStyleSheet("color:#4A3F35;background:transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        main_row.addWidget(lbl)
        cl.addLayout(main_row)

        py = info.get('pinyin', '') if info else ''
        if not py: py = get_pinyin(text)
        if py:
            pl = QLabel(py)
            pl.setFont(QFont("Arial", 14))
            pl.setStyleSheet("color:#8B6914;background:transparent;")
            pl.setAlignment(Qt.AlignCenter)
            cl.addWidget(pl)

        meanings = info.get('meanings', []) if info else []
        if not meanings:
            ced = lookup_cedict(text)
            if ced: meanings = ced.get('meanings', [])
        if meanings:
            meanings_frame = QFrame()
            meanings_frame.setStyleSheet("background:#F0E8DC;border-radius:8px;padding:4px;")
            mfl = QVBoxLayout(meanings_frame)
            mfl.setContentsMargins(10, 8, 10, 8)
            mfl.setSpacing(3)
            for i, m in enumerate(meanings[:5]):
                ml = QLabel(f"{i+1}. {m}")
                ml.setFont(QFont("Arial", 11))
                ml.setWordWrap(True)
                ml.setStyleSheet("color:#4A3F35;background:transparent;")
                mfl.addWidget(ml)
            cl.addWidget(meanings_frame)
        else:
            cjk_chars = [c for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf']
            hint_parts = []
            for c in cjk_chars:
                c_info, _ = lookup_word(c)
                if c_info and c_info.get('meanings'):
                    hint_parts.append(f"{c}={c_info['meanings'][0]}")
            if hint_parts:
                hint_lbl = QLabel('  ·  '.join(hint_parts))
                hint_lbl.setFont(QFont("Arial", 10))
                hint_lbl.setWordWrap(True)
                hint_lbl.setStyleSheet("color:#8B7D6B;background:transparent;font-style:italic;")
                hint_lbl.setAlignment(Qt.AlignCenter)
                cl.addWidget(hint_lbl)
            else:
                no_def = QLabel("No meaning found")
                no_def.setFont(QFont("Arial", 10))
                no_def.setStyleSheet("color:#9B8B7A;background:transparent;font-style:italic;")
                no_def.setAlignment(Qt.AlignCenter)
                cl.addWidget(no_def)

        pos_list = info.get('pos', []) if info else []
        if pos_list:
            POS_MAP = {'n':'noun','v':'verb','a':'adj','ad':'adv','nr':'proper noun',
                       'vn':'verb/noun','an':'adj/noun','l':'idiom','e':'interj',
                       'b':'conj','r':'pronoun','g':'morpheme','nz':'proper noun',
                       'mq':'number','d':'adv','p':'prep','c':'conj','m':'number',
                       'q':'measure','t':'time','f':'place','s':'place','u':'aux'}
            pos_texts = [POS_MAP.get(p, p) for p in pos_list[:4]]
            pos_lbl = QLabel(' · '.join(pos_texts))
            pos_lbl.setFont(QFont("Arial", 9))
            pos_lbl.setStyleSheet("color:#8B7D6B;background:transparent;font-style:italic;")
            pos_lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(pos_lbl)

        orig = result.get('original_sentence', '')
        if orig and orig != text:
            sep2 = QFrame(); sep2.setFixedHeight(1)
            sep2.setStyleSheet("background:#E0D5C5;"); cl.addWidget(sep2)
            ctx = QLabel(f"Sentence: {orig}")
            ctx.setFont(QFont("Microsoft YaHei", 9))
            ctx.setWordWrap(True)
            ctx.setStyleSheet("color:#8B7D6B;background:transparent;")
            cl.addWidget(ctx)

        config = load_config()

        if config.get('deepl_enabled') and config.get('deepl_api_key'):
            self.tl_lbl = QLabel("DeepL: Translating...")
            self.tl_lbl.setFont(QFont("Arial", 10))
            self.tl_lbl.setWordWrap(True)
            self.tl_lbl.setStyleSheet("color:#6B8E4E;background:transparent;font-style:italic;")
            cl.addWidget(self.tl_lbl)

            target_text = orig if (orig and orig != text) else text
            self.worker = TranslationWorker(target_text, config.get('deepl_api_key'))
            self.worker.finished.connect(self._on_translation_done)
            self.worker.start()

        cl.addWidget(QLabel(f"Accuracy: {int(conf*100)}%",
                            styleSheet="color:#9B8B7A;background:transparent;font-size:10px;"))

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("Copy")
        btn_copy.setStyleSheet("QPushButton{background:#E8DCCC;color:#4A3F35;border:none;border-radius:7px;"
                               "padding:6px 18px;font-size:12px;}QPushButton:hover{background:#D4C5B0;}")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(text))
        btn_row.addWidget(btn_copy)

        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("QPushButton{background:#6B8E4E;color:#FFF8F0;border:none;border-radius:7px;"
                               "padding:6px 18px;font-size:12px;font-weight:bold;}"
                               "QPushButton:hover{background:#7DA05E;}")
        def do_save():
            meanings_str = '; '.join(meanings[:3]) if meanings else ''
            save_word(text, py, meanings_str)
            btn_save.setText("Saved ✓")
            btn_save.setStyleSheet("QPushButton{background:#E8DCCC;color:#6B8E4E;border:none;border-radius:7px;"
                                   "padding:6px 18px;font-size:12px;font-weight:bold;}")
            btn_save.setEnabled(False)
        btn_save.clicked.connect(do_save)
        btn_row.addWidget(btn_save)
        cl.addLayout(btn_row)

        outer.addWidget(card)
        self.adjustSize()

    def _on_translation_done(self, result_text, success):
        if success:
            self.tl_lbl.setText(f"DeepL: {result_text}")
        else:
            self.tl_lbl.setText(f"DeepL Error: {result_text}")
            self.tl_lbl.setStyleSheet("color:#C65911;background:transparent;font-style:italic;")
        self.adjustSize()

    def mousePressEvent(self, e):
        if not self.childAt(e.pos()):
            self.close()

class HoverTooltip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(150)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)

    def show_for(self, text: str, global_pos: QPoint):
        if self.layout():
            QWidget().setLayout(self.layout())

        info, src = lookup_word(text)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("hoverCard")
        card.setStyleSheet(
            "QFrame#hoverCard{"
            "  background: rgba(250, 244, 235, 0.95);"
            "  border: 1px solid rgba(212, 197, 176, 0.8);"
            "  border-radius: 10px;"
            "}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        char_lbl = QLabel(text)
        char_lbl.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        char_color = '#4A3F35'
        char_lbl.setStyleSheet(f"color:{char_color};background:transparent;")
        top_row.addWidget(char_lbl)

        py = info.get('pinyin', '') if info else ''
        if not py: py = get_pinyin(text)
        if py:
            py_lbl = QLabel(py)
            py_lbl.setFont(QFont("Arial", 12))
            py_lbl.setStyleSheet("color:#8B6914;background:transparent;")
            top_row.addWidget(py_lbl)
        
        cl.addLayout(top_row)

        meanings = info.get('meanings', []) if info else []
        if not meanings:
            ced = lookup_cedict(text)
            if ced: meanings = ced.get('meanings', [])
            
        if meanings:
            m_text = ' / '.join(str(m) for m in meanings[:2])
            if len(m_text) > 40: m_text = m_text[:38] + '…'
            m_lbl = QLabel(m_text)
            m_lbl.setFont(QFont("Arial", 10))
            m_lbl.setWordWrap(True)
            m_lbl.setStyleSheet("color:#6B5D4F;background:transparent;")
            cl.addWidget(m_lbl)

        outer.addWidget(card)
        self.adjustSize()
        
        px = global_pos.x() - self.width() // 2
        py = global_pos.y() - self.height() - 5
        self.move(px, py)
        _clamp_popup(self)
        
        self.show()
        self._fade_anim.start()

    def dismiss(self):
        self._fade_anim.stop()
        self.hide()
