import requests
from PyQt5.QtCore import QThread, QCoreApplication, pyqtSignal

class TranslationWorker(QThread):
    translated = pyqtSignal(str, bool)

    def __init__(self, text, api_key):
        # Owned by the application and deleted once finished, so it neither
        # leaks nor gets destroyed mid-request when its popup closes.
        super().__init__(QCoreApplication.instance())
        self.finished.connect(self.deleteLater)
        self.text = text
        self.api_key = api_key

    def run(self):
        try:
            url = "https://api-free.deepl.com/v2/translate"
            headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}
            data = {"text": [self.text], "target_lang": "EN-US"}
            resp = requests.post(url, headers=headers, json=data, timeout=5)
            resp.raise_for_status()
            res_json = resp.json()
            if "translations" in res_json and len(res_json["translations"]) > 0:
                self.translated.emit(res_json["translations"][0]["text"], True)
            else:
                self.translated.emit("No result obtained.", False)
        except Exception as e:
            self.translated.emit(str(e), False)
