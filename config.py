import os, json
from PyQt5.QtCore import QObject, pyqtSignal
import keyboard
import logging

logger = logging.getLogger("OCRApp")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    defaults = {"hotkey": "alt+s", "manga_mode": False, "deepl_enabled": False, "deepl_api_key": ""}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                for k, v in defaults.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
        except: pass
    return defaults

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f)

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
