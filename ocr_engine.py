import os
import sys
import time
import logging
import threading
import numpy as np
import mss
from PyQt5.QtCore import QThread, pyqtSignal
from app_paths import bundled_path

logger = logging.getLogger("OCRApp")

OCR_ENGINE = None
OCR_TYPE = None  # 'paddle' | 'easyocr' | 'rapid' | None
# PaddleOCR is not safe to call from two threads at once (live mode + a manual scan).
_OCR_LOCK = threading.Lock()


def _contains_chinese(text: str) -> bool:
    """Keep this app focused on Chinese rather than browser/UI Latin text."""
    return any('\u3400' <= char <= '\u4dbf' or '\u4e00' <= char <= '\u9fff'
               for char in text)

def init_ocr() -> bool:
    global OCR_ENGINE, OCR_TYPE
    try:
        paddleocr_data_dir = bundled_path("paddleocr")
        if os.path.isdir(paddleocr_data_dir) and paddleocr_data_dir not in sys.path:
            sys.path.insert(0, paddleocr_data_dir)
        from paddleocr import PaddleOCR
        logger.info("[OCR] Trying PaddleOCR...")
        init_attempts = [
            {"use_angle_cls": True, "lang": "ch", "use_gpu": False, "show_log": False, "enable_mkldnn": False},
            {"use_angle_cls": True, "lang": "ch", "show_log": False, "enable_mkldnn": False},
            {"use_angle_cls": True, "lang": "ch"},
            {"lang": "ch"},
        ]
        last_error = None
        for kwargs in init_attempts:
            try:
                OCR_ENGINE = PaddleOCR(**kwargs)
                break
            except Exception as attempt_error:
                last_error = attempt_error
                OCR_ENGINE = None
        if OCR_ENGINE is None:
            raise last_error
        dummy = np.zeros((64, 200, 3), dtype=np.uint8)
        try: OCR_ENGINE.ocr(dummy, cls=True)
        except TypeError: OCR_ENGINE.ocr(dummy)
        OCR_TYPE = 'paddle'
        logger.info("[OCR] PaddleOCR ready!")
        return True
    except Exception as e:
        logger.exception(f"[WARNING] PaddleOCR failed: {e}")
        return False

def run_ocr(image: np.ndarray) -> list:
    if OCR_ENGINE is None:
        return []
    try:
        if OCR_TYPE == 'paddle':
            with _OCR_LOCK:
                return _parse_paddle(image)
    except Exception as e:
        logger.error(f"[OCR] Error: {e}")
    return []

def _parse_paddle(image):
    items = []
    try: raw = OCR_ENGINE.ocr(image, cls=True)
    except TypeError: raw = OCR_ENGINE.ocr(image)
    if not raw: return items
    lines = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
    if lines is None: return items
    for line in lines:
        try:
            if line is None: continue
            pts, (text, conf) = line
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if _contains_chinese(text):
                items.append({'text': text, 'confidence': float(conf),
                              'bbox': {'x': int(min(xs)), 'y': int(min(ys)),
                                       'w': int(max(xs)-min(xs)), 'h': int(max(ys)-min(ys))}})
        except Exception: pass
    return items

def take_screenshot(region=None) -> np.ndarray:
    with mss.mss() as sct:
        if region:
            mon = {'left': region[0], 'top': region[1],
                   'width': max(region[2], 1), 'height': max(region[3], 1)}
        else:
            mon = sct.monitors[0]
        shot = sct.grab(mon)
        img = np.array(shot)[:, :, :3][:, :, ::-1]
        return img.copy()

def run_ocr_oriented(image: np.ndarray, manga_mode=False) -> list:
    """Run OCR; in manga mode rotate for vertical text and map boxes back."""
    if not manga_mode:
        return run_ocr(image)
    res = run_ocr(np.ascontiguousarray(np.rot90(image, k=-1)))
    h = image.shape[0]
    for r in res:
        old_b = r['bbox']
        rx, ry = old_b['x'], old_b['y']
        rw, rh = old_b['w'], old_b['h']
        pts = [(rx, ry), (rx+rw, ry), (rx+rw, ry+rh), (rx, ry+rh)]
        xs = [pt_y for pt_x, pt_y in pts]
        ys = [h - 1 - pt_x for pt_x, pt_y in pts]
        r['bbox'] = {
            'x': int(min(xs)), 'y': int(min(ys)),
            'w': int(max(xs)-min(xs)), 'h': int(max(ys)-min(ys))
        }
    return res

class OCRWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, image, manga_mode=False):
        super().__init__()
        self.image = image
        self.manga_mode = manga_mode
        self._is_aborted = False

    def abort(self):
        self._is_aborted = True

    def run(self):
        try:
            if self._is_aborted: return
            res = run_ocr_oriented(self.image, self.manga_mode)
            if self._is_aborted: return
            self.finished.emit(res)
        except Exception as e:
            if not self._is_aborted:
                self.error.emit(str(e))


def _patch(gray: np.ndarray, bbox: dict):
    """Inner part of a text box; the inset keeps pinyin drawn just above it out."""
    h, w = gray.shape[:2]
    ix, iy = max(1, bbox['w'] // 10), max(2, bbox['h'] // 6)
    x1 = max(0, bbox['x'] + ix); y1 = max(0, bbox['y'] + iy)
    x2 = min(w, bbox['x'] + bbox['w'] - ix); y2 = min(h, bbox['y'] + bbox['h'] - iy)
    if x2 <= x1 or y2 <= y1:
        return None
    return gray[y1:y2, x1:x2]


def _pixels_changed(a, b, ratio=0.06) -> bool:
    if a is None or b is None or a.shape != b.shape or a.size == 0:
        return True
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return np.count_nonzero(diff > 40) > a.size * ratio


def _overlaps(a: dict, b: dict) -> bool:
    ix = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
    iy = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
    if ix <= 0 or iy <= 0:
        return False
    smaller = min(a['w'] * a['h'], b['w'] * b['h']) or 1
    return ix * iy > smaller * 0.3


class LiveScanWorker(QThread):
    """Continuously OCRs a screen region and tracks which texts are still visible.

    Cheap pixel checks run every tick so a label disappears as soon as its
    characters leave the screen; the slow OCR pass runs in the background
    whenever the screen changed since the previous pass.
    """
    results_changed = pyqtSignal(list, object)  # items, current frame (RGB ndarray)

    TICK_SECONDS = 0.15
    MAX_MISSES = 3  # OCR passes an unchanged item may be missed before it is dropped

    def __init__(self, region, manga_mode=False, min_ocr_interval=0.3):
        super().__init__()
        x, y, w, h = region
        self.monitor = {'left': x, 'top': y, 'width': max(w, 1), 'height': max(h, 1)}
        self.manga_mode = manga_mode
        self.min_ocr_interval = min_ocr_interval
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        tracked = []
        future = None
        ocr_gray = None
        last_ocr_small = None
        last_ocr_time = 0.0
        try:
            with mss.mss() as sct:
                while not self._stop.is_set():
                    started = time.monotonic()
                    frame = np.array(sct.grab(self.monitor))[:, :, :3][:, :, ::-1].copy()
                    gray = frame[:, :, 1]
                    changed = False

                    # 1) Drop labels whose characters are no longer on screen.
                    kept = [t for t in tracked if not _pixels_changed(t['patch'], _patch(gray, t['bbox']))]
                    if len(kept) != len(tracked):
                        tracked = kept
                        changed = True

                    # 2) Merge a finished OCR pass.
                    if future is not None and future.done():
                        try:
                            found = future.result()
                        except Exception as e:
                            logger.error(f"[LIVE] OCR error: {e}")
                            found = []
                        tracked = self._merge(tracked, found, ocr_gray, gray)
                        future = None
                        changed = True

                    # 3) Start a new OCR pass if the screen changed since the last one.
                    small = gray[::8, ::8]
                    if (future is None and started - last_ocr_time >= self.min_ocr_interval
                            and (last_ocr_small is None or _pixels_changed(last_ocr_small, small, ratio=0.002))):
                        ocr_gray = gray
                        last_ocr_small = small
                        last_ocr_time = started
                        future = executor.submit(run_ocr_oriented, frame, self.manga_mode)

                    if changed:
                        items = [{k: t[k] for k in ('text', 'confidence', 'bbox')} for t in tracked]
                        self.results_changed.emit(items, frame)

                    self._stop.wait(max(0.0, self.TICK_SECONDS - (time.monotonic() - started)))
        except Exception as e:
            logger.exception(f"[LIVE] Scanner stopped: {e}")
        finally:
            executor.shutdown(wait=True)

    def _merge(self, tracked, found, ocr_gray, gray):
        fresh = []
        for r in found:
            patch = _patch(gray, r['bbox'])
            # The screen may have moved on while OCR was running; the next pass will catch up.
            if patch is None or _pixels_changed(_patch(ocr_gray, r['bbox']), patch):
                continue
            fresh.append(dict(r, patch=patch.copy(), misses=0))
        for old in tracked:
            if any(_overlaps(old['bbox'], f['bbox']) for f in fresh):
                continue
            # Still pixel-identical but OCR missed it this time: keep it briefly to avoid flicker.
            if old['misses'] + 1 < self.MAX_MISSES:
                fresh.append(dict(old, misses=old['misses'] + 1))
        return fresh
