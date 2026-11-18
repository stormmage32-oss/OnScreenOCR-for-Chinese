import html

from PyQt5.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication,
                             QPushButton, QGraphicsOpacityEffect, QAbstractButton)
from PyQt5.QtCore import (Qt, QPoint, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty,
                          pyqtSignal)
from PyQt5.QtGui import QKeySequence, QPainter, QColor, QFont

from dictionary import lookup_word, get_pinyin, get_derived_hsk_level, HSK_COLORS, lookup_cedict
from translation import TranslationWorker
from word_notebook import save_word
from config import load_config
from theme import P, base_qss, hsk_color, CJK_FONT

POS_MAP = {'n': 'noun', 'v': 'verb', 'a': 'adj', 'ad': 'adv', 'nr': 'proper noun',
           'vn': 'verb/noun', 'an': 'adj/noun', 'l': 'idiom', 'e': 'interj',
           'b': 'conj', 'r': 'pronoun', 'g': 'morpheme', 'nz': 'proper noun',
           'mq': 'number', 'd': 'adv', 'p': 'prep', 'c': 'conj', 'm': 'number',
           'q': 'measure', 't': 'time', 'f': 'place', 's': 'place', 'u': 'aux'}

def popup_qss():
    return base_qss() + f"""
QFrame#card {{ background: {P.SURFACE}; border: 1px solid {P.BORDER_HOVER}; border-radius: 8px; }}
QLabel#tag {{ font-size: 11px; font-weight: 600; }}
QLabel#word {{ font-family: "{CJK_FONT}"; font-size: 32px; }}
QLabel#pinyin {{ color: {P.ACCENT_TEXT}; font-size: 16px; }}
QLabel#meaning {{ font-size: 17px; }}
QLabel#muted {{ color: {P.MUTED}; font-size: 13px; }}
QLabel#error {{ color: {P.DANGER}; font-size: 13px; }}
QLabel#sentence {{ color: {P.MUTED}; font-family: "{CJK_FONT}"; font-size: 12px; }}
QLabel#translation {{ font-size: 15px; }}
QLabel#meta {{ color: {P.FAINT}; font-size: 11px; }}
QFrame#divider {{ background: {P.DIVIDER}; border: none; max-height: 1px; min-height: 1px; }}
"""


def hover_qss():
    return f"""
QFrame#hoverCard {{ background: {P.SURFACE}; border: 1px solid {P.BORDER_HOVER}; border-radius: 6px; }}
QLabel {{ background: transparent; }}
QLabel#hWord {{ color: {P.TEXT}; font-family: "{CJK_FONT}"; font-size: 20px; }}
QLabel#hPinyin {{ color: {P.ACCENT_TEXT}; font-size: 14px; }}
QLabel#hMeaning {{ color: {P.TEXT}; font-size: 15px; }}
QLabel#hHint {{ color: {P.FAINT}; font-size: 11px; }}
QLabel#hHint[state="saved"] {{ color: {P.SUCCESS}; font-weight: 600; }}
QLabel#hHint[state="dup"] {{ color: {P.MUTED}; font-weight: 600; }}
"""


# ---------------------------------------------------------------- helpers

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


def word_entry(text):
    """(info, pinyin, meanings) for a word, falling back to pypinyin / CEDICT."""
    info, _ = lookup_word(text)
    info = info or {}
    py = info.get('pinyin', '') or get_pinyin(text)
    meanings = list(info.get('meanings', []))
    if not meanings:
        ced = lookup_cedict(text)
        if ced:
            meanings = list(ced.get('meanings', []))
    return info, py, meanings


def save_entry(text):
    """Save a word with its pinyin and meanings. Returns False if it was already saved."""
    _, py, meanings = word_entry(text)
    return save_word(text, py, '; '.join(meanings[:3]))


def save_key():
    return load_config().get('save_word_key', 's') or ''


def save_key_label():
    k = save_key()
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in k.split("+")) if k else ""


def matches_save_key(event):
    """True if a Qt key event is the configured 'save word' key."""
    k = save_key()
    if not k or event.isAutoRepeat():
        return False
    want = QKeySequence("+".join(p.strip().capitalize() for p in k.split("+")))
    if want.isEmpty():
        return False
    mods = int(event.modifiers()) & int(Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
    return want[0] == (event.key() | mods)


def _label(text, name, wrap=False):
    l = QLabel(text)
    l.setObjectName(name)
    l.setWordWrap(wrap)
    return l


def _hsk_tag(text):
    level, derived = get_derived_hsk_level(text)
    if level <= 0:
        return None, None
    name = "HSK 7-9" if level == 7 else f"HSK {level}"
    if derived and len(text) > 1:
        name += " (by character)"
    return name, hsk_color(HSK_COLORS.get(level, P.MUTED))


# ---------------------------------------------------------------- detail popup

class DetailPopup(QDialog):
    def __init__(self, result: dict, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(popup_qss())
        self.text = text = result['text']
        conf = result.get('confidence', 0)
        info, py, meanings = word_entry(text)
        self._py, self._translation, self.tl_lbl = py, None, None
        # Phrases with no dictionary entry show their DeepL translation as the meaning.
        self._tl_is_meaning = False
        config = load_config()
        can_translate = bool(config.get('deepl_enabled') and config.get('deepl_api_key'))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(); card.setObjectName("card")
        card.setFixedWidth(380)
        cl = QVBoxLayout(card); cl.setContentsMargins(20, 16, 20, 16); cl.setSpacing(2)

        # HSK level and part of speech on one small line
        tags = []
        hsk_name, hsk_color = _hsk_tag(text)
        if hsk_name:
            tags.append(f"<span style='color:{hsk_color};'>{hsk_name}</span>")
        pos_list = info.get('pos', [])
        if pos_list:
            pos = " · ".join(POS_MAP.get(p, p) for p in pos_list[:3])
            tags.append(f"<span style='color:{P.MUTED};font-weight:400;'>{html.escape(pos)}</span>")
        if tags:
            cl.addWidget(_label("&nbsp;&nbsp;·&nbsp;&nbsp;".join(tags), "tag"))
            cl.addSpacing(2)

        w = _label(text, "word", wrap=True)
        w.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cl.addWidget(w)
        if py:
            p = _label(py, "pinyin", wrap=True)
            p.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cl.addWidget(p)

        cl.addSpacing(10)
        cl.addWidget(self._divider())
        cl.addSpacing(10)

        if meanings:
            rows = "".join(
                f"<tr><td style='color:{P.FAINT};padding:0 10px 6px 0;'>{n}</td>"
                f"<td style='padding-bottom:6px;'>{html.escape(str(m))}</td></tr>"
                for n, m in enumerate(meanings[:5], 1))
            m = _label(f"<table cellspacing='0'>{rows}</table>", "meaning", wrap=True)
            m.setTextFormat(Qt.RichText)
            m.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cl.addWidget(m)
        elif can_translate:
            self._tl_is_meaning = True
            self.tl_lbl = _label("Translating…", "muted", wrap=True)
            cl.addWidget(self.tl_lbl)
        else:
            cl.addWidget(_label("Not in the dictionary. Turn on DeepL translation in Settings "
                                "to translate it.", "muted", wrap=True))

        orig = result.get('original_sentence', '')
        if orig and orig != text:
            cl.addSpacing(10)
            s = _label(orig, "sentence", wrap=True)
            s.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cl.addWidget(s)

        if meanings and can_translate and (result.get('translate_requested') or config.get('deepl_always')):
            cl.addSpacing(10)
            self.tl_lbl = _label("Translating…", "muted", wrap=True)
            cl.addWidget(self.tl_lbl)
        if self.tl_lbl is not None:
            self.worker = TranslationWorker(text, config.get('deepl_api_key'),
                                            config.get('deepl_target_lang', 'EN-US'))
            self.worker.translated.connect(self._on_translation_done)
            self.worker.start()

        cl.addSpacing(14)
        foot = QHBoxLayout(); foot.setSpacing(8)
        if conf:
            foot.addWidget(_label(f"OCR {int(conf * 100)}%", "meta"))
        foot.addStretch()
        btn_copy = QPushButton("Copy"); btn_copy.setObjectName("btn")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(text))
        foot.addWidget(btn_copy)
        key = save_key_label()
        self.btn_save = QPushButton(f"Save  ({key})" if key else "Save")
        self.btn_save.setObjectName("btnAccent")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save)
        foot.addWidget(self.btn_save)
        cl.addLayout(foot)

        outer.addWidget(card)
        self.adjustSize()

    @staticmethod
    def _divider():
        d = QFrame(); d.setObjectName("divider")
        return d

    def _save(self):
        if not self.btn_save.isEnabled():
            return
        if self._tl_is_meaning and self._translation:
            # No dictionary entry: keep the translation as the saved meaning.
            saved = save_word(self.text, self._py, self._translation)
        else:
            saved = save_entry(self.text)
        self.btn_save.setText("Saved" if saved else "Already saved")
        self.btn_save.setEnabled(False)

    def keyPressEvent(self, e):
        if matches_save_key(e):
            self._save()
            return
        super().keyPressEvent(e)

    def _on_translation_done(self, result_text, success):
        if self.tl_lbl is None:
            return
        if success:
            self._translation = result_text
            self.tl_lbl.setObjectName("meaning" if self._tl_is_meaning else "translation")
            self.tl_lbl.setTextFormat(Qt.RichText)
            self.tl_lbl.setText(f"<span style='color:{P.FAINT};font-size:11px;'>DeepL</span><br>"
                                f"{html.escape(result_text)}")
        else:
            self.tl_lbl.setText(f"DeepL error: {result_text}")
            self.tl_lbl.setObjectName("error")
        self.tl_lbl.style().unpolish(self.tl_lbl); self.tl_lbl.style().polish(self.tl_lbl)
        self.adjustSize()

    def mousePressEvent(self, e):
        if not self.childAt(e.pos()):
            self.close()


# ---------------------------------------------------------------- hover card

class HoverTooltip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(hover_qss())
        self._hint = None
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(120)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)

    def show_for(self, text: str, global_pos: QPoint):
        if self.layout():
            QWidget().setLayout(self.layout())

        _, py, meanings = word_entry(text)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(); card.setObjectName("hoverCard")
        card.setMaximumWidth(340)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 9, 12, 9)
        cl.setSpacing(2)

        top = QHBoxLayout(); top.setSpacing(10)
        top.addWidget(_label(text, "hWord"))
        if py:
            top.addWidget(_label(py, "hPinyin"), 0, Qt.AlignVCenter)
        top.addStretch()
        cl.addLayout(top)

        if meanings:
            m_text = ' / '.join(str(m) for m in meanings[:2])
            if len(m_text) > 60:
                m_text = m_text[:58] + '…'
            cl.addWidget(_label(m_text, "hMeaning", wrap=True))

        key = save_key_label()
        self._hint = _label(f"{key} to save" if key else "", "hHint")
        self._hint.setVisible(bool(key))
        cl.addSpacing(2)
        cl.addWidget(self._hint)

        outer.addWidget(card)
        self.adjustSize()

        px = global_pos.x() - self.width() // 2
        py_ = global_pos.y() - self.height() - 6
        self.move(px, py_)
        _clamp_popup(self)

        self.show()
        self._fade_anim.start()

    def mark_saved(self, saved: bool):
        """Turn the hint line into feedback after the save key was pressed."""
        if self._hint is None:
            return
        self._hint.setText("Saved to notebook" if saved else "Already in notebook")
        self._hint.setProperty("state", "saved" if saved else "dup")
        self._hint.setVisible(True)
        self._hint.style().unpolish(self._hint); self._hint.style().polish(self._hint)
        self.adjustSize()

    def dismiss(self):
        self._fade_anim.stop()
        self.hide()


# ---------------------------------------------------------------- segmented slider

class SegmentedSlider(QAbstractButton):
    """Pill with two or more labels and a knob that slides to the chosen one."""
    index_changed = pyqtSignal(int)

    def __init__(self, labels, index=0, segment_w=40, parent=None):
        super().__init__(parent)
        self._labels = list(labels)
        self._index = index
        self._pos = float(index)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(4 + segment_w * len(self._labels), 28)
        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get_pos(self):
        return self._pos

    def _set_pos(self, v):
        self._pos = v
        self.update()

    knob_pos = pyqtProperty(float, _get_pos, _set_pos)

    def index(self):
        return self._index

    def set_index(self, i, animate=True):
        if i == self._index:
            return
        self._index = i
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(float(i))
            self._anim.start()
        else:
            self._set_pos(float(i))
        self.index_changed.emit(i)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.pos()):
            seg = (self.width() - 4) / len(self._labels)
            self.set_index(max(0, min(len(self._labels) - 1, int((e.pos().x() - 2) // seg))))
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Left, Qt.Key_Right):
            step = -1 if e.key() == Qt.Key_Left else 1
            self.set_index(max(0, min(len(self._labels) - 1, self._index + step)))
            return
        super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QColor(P.BORDER))
        p.setBrush(QColor(P.TRACK))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        seg = (r.width() - 4) / len(self._labels)
        knob = QRectF(r.left() + 2 + seg * self._pos, r.top() + 2, seg, r.height() - 4)
        p.setPen(QColor(P.TRACK_KNOB_BORDER))
        p.setBrush(QColor(P.SURFACE))
        p.drawRoundedRect(knob, knob.height() / 2, knob.height() / 2)
        f = QFont("Segoe UI"); f.setPixelSize(11)
        for i, text in enumerate(self._labels):
            active = i == self._index
            f.setBold(active); p.setFont(f)
            p.setPen(QColor(P.TEXT if active else P.MUTED))
            p.drawText(QRectF(r.left() + 2 + seg * i, r.top(), seg, r.height()), Qt.AlignCenter, text)
