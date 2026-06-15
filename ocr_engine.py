import os
import sys
import logging
import numpy as np
import mss
from PyQt5.QtCore import QThread, pyqtSignal
from app_paths import bundled_path

logger = logging.getLogger("OCRApp")

OCR_ENGINE = None
OCR_TYPE = None  # 'paddle' | 'easyocr' | 'rapid' | None

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
            img = self.image
            if self.manga_mode:
                img = np.rot90(img, k=-1)
            
            res = run_ocr(img)
            
            if self._is_aborted: return
            
            if self.manga_mode and res:
                h, w = self.image.shape[:2]
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
            
            if self._is_aborted: return
            self.finished.emit(res)
        except Exception as e:
            if not self._is_aborted:
                self.error.emit(str(e))
