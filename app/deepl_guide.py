"""Step-by-step guide to getting a free DeepL API key, in English or Turkish."""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
                             QAbstractButton)
from PyQt5.QtCore import Qt, QUrl, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve, QLocale
from PyQt5.QtGui import QPainter, QColor, QFont, QDesktopServices

from theme import BASE_QSS, BG, SURFACE, BORDER, TEXT, MUTED, ACCENT

SIGNUP_URL = "https://www.deepl.com/pro-api"
KEYS_URL = "https://www.deepl.com/your-account/keys"

# Each step: text, optional (button label, url).
GUIDE = {
    "en": {
        "window": "DeepL API key",
        "title": "Get a free DeepL API key",
        "free": "<b>It's free.</b> The DeepL API Free plan translates up to 500,000 characters "
                "a month at no cost. If you reach the limit, translation stops until the next "
                "month. You are never charged.",
        "steps": [
            ("Open the DeepL API page and choose the <b>DeepL API Free</b> plan, not Pro. "
             "This app only works with Free keys.", ("Open DeepL API page", SIGNUP_URL)),
            ("Sign up with your email. The API needs its own account, separate from the "
             "DeepL translator website. DeepL may ask for a card to confirm who you are; "
             "the Free plan does not charge it.", None),
            ("Once signed in, open <b>Account → API Keys</b> and copy your key. "
             "A free key ends in <b>:fx</b>.", ("Open my API keys", KEYS_URL)),
            ("Paste the key into the box under <b>DeepL translation</b> and turn "
             "the switch on.", None),
        ],
        "note": "Your key is saved only on this computer.",
        "close": "Close",
    },
    "tr": {
        "window": "DeepL API anahtarı",
        "title": "Ücretsiz DeepL API anahtarı alma",
        "free": "<b>Tamamen ücretsiz.</b> DeepL API Free planı ayda 500.000 karaktere kadar "
                "bedava çeviri yapar. Sınıra gelirseniz çeviri bir sonraki aya kadar durur. "
                "Sizden hiçbir ücret alınmaz.",
        "steps": [
            ("DeepL API sayfasını açın ve Pro değil, <b>DeepL API Free</b> planını seçin. "
             "Bu uygulama yalnızca Free anahtarlarla çalışır.", ("DeepL API sayfasını aç", SIGNUP_URL)),
            ("E-posta adresinizle kaydolun. API için DeepL çeviri sitesinden ayrı bir hesap "
             "gerekir. DeepL kimliğinizi doğrulamak için kart bilgisi isteyebilir; Free planda "
             "karttan para çekilmez.", None),
            ("Giriş yaptıktan sonra <b>Account → API Keys</b> bölümünü açın ve anahtarınızı "
             "kopyalayın. Ücretsiz anahtarın sonu <b>:fx</b> ile biter.",
             ("API anahtarlarımı aç", KEYS_URL)),
            ("Anahtarı <b>DeepL translation</b> altındaki kutuya yapıştırın ve "
             "düğmeyi açın.", None),
        ],
        "note": "Anahtarınız yalnızca bu bilgisayarda saklanır.",
        "close": "Kapat",
    },
}

QSS = BASE_QSS + f"""
QDialog {{ background: {BG}; }}
QLabel#guideTitle {{ font-size: 16px; font-weight: 600; }}
QFrame#freeBox {{ background: #EAF5EA; border: 1px solid #BFE0BF; border-radius: 6px; }}
QLabel#freeText {{ color: #1F4D1F; font-size: 12px; }}
QFrame#stepCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}
QLabel#stepNum {{ background: {ACCENT}; color: #FFFFFF; border-radius: 11px;
                 font-size: 11px; font-weight: 600; }}
QLabel#stepText {{ font-size: 12px; }}
QLabel#note {{ color: {MUTED}; font-size: 11px; }}
"""

# Remembered for the rest of the session once the user picks a language.
_last_lang = None


def _default_lang():
    if _last_lang:
        return _last_lang
    return "tr" if QLocale.system().language() == QLocale.Turkish else "en"


class LangSlider(QAbstractButton):
    """Two-position EN / TR slider. Checked means Turkish."""

    def __init__(self, turkish=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(turkish)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(84, 28)
        self.setToolTip("English / Türkçe")
        self._offset = 1.0 if turkish else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
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
        p.setPen(QColor(BORDER))
        p.setBrush(QColor("#E6E6E6"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        half = (r.width() - 4) / 2
        knob = QRectF(r.left() + 2 + half * self._offset, r.top() + 2, half, r.height() - 4)
        p.setPen(QColor("#D0D0D0"))
        p.setBrush(QColor(SURFACE))
        p.drawRoundedRect(knob, knob.height() / 2, knob.height() / 2)
        f = QFont("Segoe UI"); f.setPixelSize(11)
        for i, text in enumerate(("EN", "TR")):
            active = (i == 1) == self.isChecked()
            f.setBold(active); p.setFont(f)
            p.setPen(QColor(TEXT if active else MUTED))
            p.drawText(QRectF(r.left() + 2 + half * i, r.top(), half, r.height()), Qt.AlignCenter, text)


class DeepLGuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(QSS)
        self.setFixedWidth(440)

        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(22, 18, 22, 18)
        self._v.setSpacing(0)

        head = QHBoxLayout(); head.setSpacing(12)
        self._title = QLabel(); self._title.setObjectName("guideTitle")
        self._lang = LangSlider(_default_lang() == "tr")
        self._lang.toggled.connect(self._on_lang)
        head.addWidget(self._title, 1); head.addWidget(self._lang, 0, Qt.AlignVCenter)
        self._v.addLayout(head)
        self._v.addSpacing(14)

        # Rebuilt on every language change.
        self._body = QVBoxLayout(); self._body.setSpacing(8)
        self._v.addLayout(self._body)
        self._v.addSpacing(14)

        foot = QHBoxLayout()
        self._note = QLabel(); self._note.setObjectName("note")
        self._close = QPushButton(); self._close.setObjectName("btnAccent")
        self._close.clicked.connect(self.close)
        foot.addWidget(self._note, 1); foot.addWidget(self._close)
        self._v.addLayout(foot)

        self._fill("tr" if self._lang.isChecked() else "en")

    def _on_lang(self, turkish):
        global _last_lang
        _last_lang = "tr" if turkish else "en"
        self._fill(_last_lang)

    def _clear_body(self):
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w:
                # Hide now: deleteLater alone leaves it painted until the event loop runs.
                w.hide(); w.setParent(None); w.deleteLater()

    def _fill(self, lang):
        g = GUIDE[lang]
        self.setWindowTitle(g["window"])
        self._title.setText(g["title"])
        self._note.setText(g["note"])
        self._close.setText(g["close"])
        self._clear_body()

        free = QFrame(); free.setObjectName("freeBox")
        fl = QHBoxLayout(free); fl.setContentsMargins(12, 10, 12, 10)
        ft = QLabel(g["free"]); ft.setObjectName("freeText"); ft.setWordWrap(True)
        fl.addWidget(ft)
        self._body.addWidget(free)

        for i, (text, link) in enumerate(g["steps"], 1):
            card = QFrame(); card.setObjectName("stepCard")
            row = QHBoxLayout(card); row.setContentsMargins(12, 10, 12, 10); row.setSpacing(10)
            num = QLabel(str(i)); num.setObjectName("stepNum")
            num.setFixedSize(22, 22); num.setAlignment(Qt.AlignCenter)
            row.addWidget(num, 0, Qt.AlignTop)
            col = QVBoxLayout(); col.setSpacing(8)
            t = QLabel(text); t.setObjectName("stepText"); t.setWordWrap(True)
            col.addWidget(t)
            if link:
                label, url = link
                b = QPushButton(label + "  ↗"); b.setObjectName("btn")
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
                col.addWidget(b, 0, Qt.AlignLeft)
            row.addLayout(col, 1)
            self._body.addWidget(card)

        self.adjustSize()
