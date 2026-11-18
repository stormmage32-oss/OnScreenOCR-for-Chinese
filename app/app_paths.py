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


def ascii_path(path):
    """The same existing path in plain ASCII when possible.

    Qt 5 and Paddle's C++ engine read file paths through the ANSI code page, so
    they fail inside folders such as "...\\Masaüstü\\...". Windows' 8.3 short name
    of the folder is ASCII. Returns the path unchanged when it is already ASCII
    or the drive has no short names.
    """
    if sys.platform != "win32" or path.isascii() or not os.path.exists(path):
        return path
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(path, buf, len(buf)) and buf.value.isascii():
        return buf.value
    return path


def use_short_qt_plugin_path():
    """Let Qt 5 find its plugins when the app sits in a non-ASCII folder.

    From a path such as "...\\Masaüstü\\..." Qt can't load the "windows" platform
    plugin and stops with "no Qt platform plugin could be initialized".
    Call before importing PyQt5.
    """
    import importlib.util
    spec = importlib.util.find_spec("PyQt5")
    if spec is None or not spec.submodule_search_locations:
        return
    plugins = os.path.join(list(spec.submodule_search_locations)[0], "Qt5", "plugins")
    short = ascii_path(plugins)
    if short != plugins:
        os.environ["QT_PLUGIN_PATH"] = short
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(short, "platforms")


def user_data_dir():
    root = os.environ.get("APPDATA")
    if not root:
        root = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    path = os.path.join(root, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def user_data_path(*parts):
    return os.path.join(user_data_dir(), *parts)
