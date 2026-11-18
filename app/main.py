import sys
import os
import logging

# Started without a console (pythonw.exe), stdout/stderr are None and any library
# that prints or draws a progress bar (PaddleOCR's model download) would crash.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

from app_paths import use_short_qt_plugin_path
use_short_qt_plugin_path()  # before PyQt5 is imported

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from app_paths import user_data_path

# Load Paddle's DLLs early so they win over any conflicting copies.
try: import paddle  # noqa: F401
except Exception: pass

if sys.platform == 'win32':
    import ctypes
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass
    import io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'
    os.environ['FLAGS_use_mkldnn'] = '0'
    os.environ['FLAGS_use_dnnl'] = '0'

LOG_FILE = user_data_path("ocr_app.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    # Paddle configures logging when it is imported above, which made this call a
    # no-op: nothing was ever written to the log file.
    force=True,
)
logger = logging.getLogger("OCRApp")


def _log_uncaught(exc_type, exc, tb):
    # Without a console an uncaught error would vanish; keep it in the log file.
    logger.critical("Uncaught exception", exc_info=(exc_type, exc, tb))


sys.excepthook = _log_uncaught

from ui_main import MainWindow

def main():
    # Use the exact Windows scale (125%, 150%, 175%...) instead of Qt 5's default
    # rounding to 1x/2x, which made the UI too small or larger than the screen.
    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
