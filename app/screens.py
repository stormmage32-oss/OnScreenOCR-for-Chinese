"""Map between Qt's logical (DPI-scaled) coordinates and physical screen pixels.

With Windows display scaling above 100%, Qt reports screens and widgets in
logical pixels (a 2560x1440 monitor at 150% is 1707x960), while screenshots and
OCR boxes are in physical pixels. Every capture goes through to_physical() and
every OCR result is brought back with scale_results() before it is drawn.
"""
import sys
import copy
import ctypes
from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication

# Defined once: ctypes caches POINTER(type) forever, so a structure class
# created per call would leak one cache entry every time.
if sys.platform == 'win32':
    from ctypes import wintypes

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                    ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD),
                    ('szDevice', wintypes.WCHAR * 32)]

    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                         ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    _user32 = ctypes.WinDLL('user32')
    _user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                            MONITORENUMPROC, wintypes.LPARAM]
    _user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]


def _native_monitor_rects() -> dict:
    """Physical rect of every monitor, keyed by device name (\\\\.\\DISPLAY1)."""
    if sys.platform != 'win32':
        return {}
    user32 = _user32
    rects = {}

    def callback(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcMonitor
            rects[info.szDevice] = (r.left, r.top, r.right - r.left, r.bottom - r.top)
        return True

    try:
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    except Exception:
        return {}
    return rects


def physical_geometry(screen) -> tuple:
    """(x, y, w, h) of a QScreen in physical pixels."""
    rect = _native_monitor_rects().get(screen.name())
    if rect:
        return rect
    g, dpr = screen.geometry(), screen.devicePixelRatio()
    return g.x(), g.y(), round(g.width() * dpr), round(g.height() * dpr)


def to_physical(rect: QRect):
    """Logical global rect -> ((x, y, w, h) in physical pixels, physical px per logical px)."""
    screen = QApplication.screenAt(rect.center()) or QApplication.primaryScreen()
    g = screen.geometry()
    px, py, pw, ph = physical_geometry(screen)
    sx = pw / max(1, g.width())
    sy = ph / max(1, g.height())
    x = px + round((rect.x() - g.x()) * sx)
    y = py + round((rect.y() - g.y()) * sy)
    w = min(round(rect.width() * sx), px + pw - x)
    h = min(round(rect.height() * sy), py + ph - y)
    return (x, y, max(1, w), max(1, h)), sx


def scale_results(results: list, factor: float) -> list:
    """Copy OCR results with every coordinate multiplied by factor."""
    if abs(factor - 1.0) < 1e-6:
        return results
    scaled = []
    for res in results:
        r = copy.copy(res)
        b = res['bbox']
        r['bbox'] = {k: int(round(b[k] * factor)) for k in ('x', 'y', 'w', 'h')}
        if 'text_top' in res:
            r['text_top'] = int(round(res['text_top'] * factor))
            r['text_h'] = max(1, int(round(res['text_h'] * factor)))
        if 'chars' in res:
            r['chars'] = [dict(c, x=int(round(c['x'] * factor)), w=max(1, int(round(c['w'] * factor))))
                          for c in res['chars']]
        scaled.append(r)
    return scaled
