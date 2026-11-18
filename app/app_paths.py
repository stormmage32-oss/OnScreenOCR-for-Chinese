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


def use_short_qt_plugin_path():
    """Let Qt 5 find its plugins when the app sits in a non-ASCII folder.

    Qt 5 reads its plugin folder through the ANSI code page, so from a path such
    as "...\\Masaüstü\\..." it can't load the "windows" platform plugin and the app
    stops with "no Qt platform plugin could be initialized". Windows' 8.3 short
    name of the same folder is plain ASCII. Call before importing PyQt5.
    """
    if sys.platform != "win32":
        return
    import ctypes
    import importlib.util
    spec = importlib.util.find_spec("PyQt5")
    if spec is None or not spec.submodule_search_locations:
        return
    plugins = os.path.join(list(spec.submodule_search_locations)[0], "Qt5", "plugins")
    if plugins.isascii() or not os.path.isdir(plugins):
        return
    buf = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(plugins, buf, len(buf)) and buf.value.isascii():
        os.environ["QT_PLUGIN_PATH"] = buf.value
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(buf.value, "platforms")


def user_data_dir():
    root = os.environ.get("APPDATA")
    if not root:
        root = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    path = os.path.join(root, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def user_data_path(*parts):
    return os.path.join(user_data_dir(), *parts)
