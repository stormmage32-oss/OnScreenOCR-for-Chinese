import requests
from PyQt5.QtCore import QThread, QCoreApplication, pyqtSignal

# DeepL target languages offered in Settings: (code, name).
TARGET_LANGUAGES = (
    ("EN-US", "English (US)"), ("EN-GB", "English (UK)"), ("TR", "Turkish"),
    ("DE", "German"), ("FR", "French"), ("ES", "Spanish"), ("IT", "Italian"),
    ("PT-BR", "Portuguese (Brazil)"), ("PT-PT", "Portuguese (Portugal)"), ("NL", "Dutch"),
    ("PL", "Polish"), ("RU", "Russian"), ("UK", "Ukrainian"), ("JA", "Japanese"),
    ("KO", "Korean"), ("AR", "Arabic"), ("ID", "Indonesian"), ("SV", "Swedish"),
    ("DA", "Danish"), ("FI", "Finnish"), ("NB", "Norwegian"), ("CS", "Czech"),
    ("EL", "Greek"), ("HU", "Hungarian"), ("RO", "Romanian"), ("BG", "Bulgarian"),
    ("SK", "Slovak"), ("SL", "Slovenian"), ("ET", "Estonian"), ("LV", "Latvian"),
    ("LT", "Lithuanian"),
)


def is_free_key(api_key):
    return api_key.strip().endswith(":fx")


def api_url(api_key, path):
    """Free keys (ending in ':fx') use api-free.deepl.com; Pro keys use api.deepl.com."""
    host = "api-free.deepl.com" if is_free_key(api_key) else "api.deepl.com"
    return f"https://{host}/v2/{path}"


def _headers(api_key):
    return {"Authorization": f"DeepL-Auth-Key {api_key.strip()}"}


def friendly_error(exc):
    """Short, plain message for a failed DeepL request."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code == 403:
            return "DeepL did not accept this key. Check that you copied the whole key."
        if code == 456:
            return "This month's free DeepL limit is used up. It resets next month."
        if code == 429:
            return "Too many requests to DeepL. Try again in a moment."
        if code >= 500:
            return "DeepL is having problems right now. Try again later."
        return f"DeepL returned error {code}."
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return "Couldn't reach DeepL. Check your internet connection."
    return str(exc)


class TranslationWorker(QThread):
    translated = pyqtSignal(str, bool)

    def __init__(self, text, api_key, target_lang="EN-US"):
        # Owned by the application and deleted once finished, so it neither
        # leaks nor gets destroyed mid-request when its popup closes.
        super().__init__(QCoreApplication.instance())
        self.finished.connect(self.deleteLater)
        self.text = text
        self.api_key = api_key
        self.target_lang = target_lang or "EN-US"

    def run(self):
        try:
            # The source is always Chinese; saying so keeps DeepL from guessing
            # Japanese for short words written with shared characters.
            data = {"text": [self.text], "source_lang": "ZH", "target_lang": self.target_lang}
            resp = requests.post(api_url(self.api_key, "translate"), headers=_headers(self.api_key),
                                 json=data, timeout=5)
            resp.raise_for_status()
            res_json = resp.json()
            if "translations" in res_json and len(res_json["translations"]) > 0:
                self.translated.emit(res_json["translations"][0]["text"], True)
            else:
                self.translated.emit("No result obtained.", False)
        except Exception as e:
            self.translated.emit(friendly_error(e), False)


class UsageWorker(QThread):
    """Checks a key and reads this month's usage: done(ok, used, limit, message)."""
    done = pyqtSignal(bool, int, int, str)

    def __init__(self, api_key):
        super().__init__(QCoreApplication.instance())
        self.finished.connect(self.deleteLater)
        self.api_key = api_key

    def run(self):
        try:
            resp = requests.get(api_url(self.api_key, "usage"), headers=_headers(self.api_key), timeout=6)
            resp.raise_for_status()
            j = resp.json()
            self.done.emit(True, int(j.get("character_count", 0)), int(j.get("character_limit", 0)), "")
        except Exception as e:
            self.done.emit(False, 0, 0, friendly_error(e))
