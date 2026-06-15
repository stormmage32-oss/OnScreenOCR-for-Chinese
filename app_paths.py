import os
import sys

APP_NAME = "ChineseScreenOCR"


def bundled_path(*parts):
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, *parts)


def install_dir_path(*parts):
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, *parts)


def user_data_dir():
    root = os.environ.get("APPDATA")
    if not root:
        root = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    path = os.path.join(root, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def user_data_path(*parts):
    return os.path.join(user_data_dir(), *parts)
