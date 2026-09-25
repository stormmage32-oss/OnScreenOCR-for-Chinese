import os
import sys
import time
import logging
import threading
import hashlib
import math
from collections import OrderedDict
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
        # return_word_box makes the recognizer report where each character sits in
        # its line, which lets the pinyin overlay align labels with the real glyphs.
        init_attempts = [
            {"use_angle_cls": True, "lang": "ch", "use_gpu": False, "show_log": False, "enable_mkldnn": False,
             "return_word_box": True},
            {"use_angle_cls": True, "lang": "ch", "use_gpu": False, "show_log": False, "enable_mkldnn": False},
            {"use_angle_cls": True, "lang": "ch", "show_log": False, "enable_mkldnn": False},
            {"use_angle_cls": True, "lang": "ch"},
            {"lang": "ch"},
        ]
        last_error = None
        from paddle import inference
        create_predictor = inference.create_predictor
        inference.create_predictor = _create_predictor_hook(create_predictor)
        try:
            for kwargs in init_attempts:
                try:
                    OCR_ENGINE = PaddleOCR(**kwargs)
                    break
                except Exception as attempt_error:
                    last_error = attempt_error
                    OCR_ENGINE = None
        finally:
            inference.create_predictor = create_predictor
        if OCR_ENGINE is None:
            raise last_error
        _bound_rec_shapes(OCR_ENGINE.text_recognizer)
        dummy = np.zeros((64, 200, 3), dtype=np.uint8)
        try: OCR_ENGINE.ocr(dummy, cls=True)
        except TypeError: OCR_ENGINE.ocr(dummy)
        OCR_TYPE = 'paddle'
        logger.info("[OCR] PaddleOCR ready!")
        return True
    except Exception as e:
        logger.exception(f"[WARNING] PaddleOCR failed: {e}")
        return False

def _create_predictor_hook(create_predictor):
    """Wrap paddle.inference.create_predictor to run the angle classifier without oneDNN.

    Paddle enables oneDNN even with enable_mkldnn=False. With the detector,
    classifier and recognizer all on oneDNN and run one after another, memory
    grew ~7 MB per OCR pass; any two of them alone barely grow. Taking the
    tiny classifier off oneDNN removes the growth at no measurable speed cost.
    """
    def create(config):
        if 'cls' in os.path.basename(os.path.dirname(config.prog_file())):
            config.disable_mkldnn()
        return create_predictor(config)
    return create


def _bound_rec_shapes(rec):
    """Feed the recognizer only a handful of input shapes.

    Paddle Inference keeps memory for every input shape it sees (oneDNN is on
    even with enable_mkldnn=False). Batches of up to 6 crops padded to the
    widest one make nearly every batch a new shape, which leaked ~20 MB per OCR
    pass. One crop per batch, padded to a width from a short geometric series,
    leaves about a dozen shapes, and is faster since crops are padded less.
    """
    if getattr(rec, 'rec_algorithm', None) != 'SVTR_LCNet':
        return  # other models take other preprocessing paths
    resize = rec.resize_norm_img
    height = rec.rec_image_shape[1]

    def bucketed_resize(img, max_wh_ratio):
        width = 320
        while width < height * max_wh_ratio:
            width = int(width * 1.5)  # 320, 480, 720, 1080, 1620, ...
        return resize(img, width / height)

    rec.resize_norm_img = bucketed_resize
    rec.rec_batch_num = 1


_DET_BUCKET = 320  # detector input sides become multiples of this


def _pad_for_detector(image: np.ndarray) -> np.ndarray:
    """Pad the bottom/right so the detector sees one of a few input shapes.

    Like the recognizer, the detector keeps ~15 MB for every input shape, and
    each differently sized region selection is a new one. Padding only the
    bottom/right, with the border colour, keeps box coordinates and the
    detector's scale unchanged while limiting it to a handful of shapes.
    """
    args = getattr(OCR_ENGINE, 'args', None)
    if args is None or getattr(args, 'det_limit_type', None) != 'max':
        return image
    limit = args.det_limit_side_len
    h, w = image.shape[:2]
    scale = min(1.0, limit / max(h, w))

    def padded_side(side):
        bucket = min(limit, math.ceil(side * scale / _DET_BUCKET) * _DET_BUCKET)
        return max(side, math.ceil(bucket / scale))

    ph, pw = padded_side(h), padded_side(w)
    if (ph, pw) == (h, w):
        return image
    border = np.concatenate([image[0], image[-1], image[:, 0], image[:, -1]])
    padded = np.empty((ph, pw) + image.shape[2:], dtype=image.dtype)
    padded[...] = np.median(border, axis=0).astype(image.dtype)
    padded[:h, :w] = image
    return padded


def run_ocr(image: np.ndarray, rec_cache=None) -> list:
    """rec_cache: optional RecognitionCache reused across calls (live mode)."""
    if OCR_ENGINE is None:
        return []
    try:
        if OCR_TYPE == 'paddle':
            with _OCR_LOCK:
                return _parse_paddle(image, rec_cache)
    except Exception as e:
        logger.error(f"[OCR] Error: {e}")
    return []

class RecognitionCache:
    """Recognition results keyed by the exact pixels of a detected text line.

    Recognition is ~90% of an OCR pass. On a live screen most lines are
    unchanged between passes, so only new or changed lines are recognized.
    """
    def __init__(self, max_entries=1024):
        self._items = OrderedDict()
        self._max = max_entries

    @staticmethod
    def key(crop: np.ndarray) -> bytes:
        return hashlib.blake2b(crop.tobytes(), digest_size=16).digest() + repr(crop.shape).encode()

    def get(self, key):
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def put(self, key, value):
        self._items[key] = value
        while len(self._items) > self._max:
            self._items.popitem(last=False)


def _paddle_lines_cached(image, cache: RecognitionCache):
    """Same output as PaddleOCR.ocr(image)[0], recognizing only uncached lines."""
    import copy
    from tools.infer.predict_system import sorted_boxes  # on sys.path once paddleocr is imported
    from tools.infer.utility import get_rotate_crop_image, get_minarea_rect_crop
    engine = OCR_ENGINE
    dt_boxes, _ = engine.text_detector(image)
    if dt_boxes is None or len(dt_boxes) == 0:
        return []
    dt_boxes = sorted_boxes(dt_boxes)
    crop_fn = get_rotate_crop_image if engine.args.det_box_type == "quad" else get_minarea_rect_crop
    crops = [crop_fn(image, copy.deepcopy(box)) for box in dt_boxes]
    keys = [cache.key(crop) for crop in crops]
    results = [cache.get(k) for k in keys]
    missing = [i for i, r in enumerate(results) if r is None]
    if missing:
        todo = [crops[i] for i in missing]
        if engine.use_angle_cls:
            todo, _, _ = engine.text_classifier(todo)
        recognized, _ = engine.text_recognizer(todo)
        for i, rec in zip(missing, recognized):
            results[i] = rec
            cache.put(keys[i], rec)
    return [[box.tolist(), rec] for box, rec in zip(dt_boxes, results) if rec[1] >= engine.drop_score]


def _parse_paddle(image, rec_cache=None):
    items = []
    image = _pad_for_detector(image)
    if rec_cache is not None:
        try:
            lines = _paddle_lines_cached(image, rec_cache)
        except Exception as e:
            logger.warning(f"[OCR] Cached recognition unavailable, using full OCR: {e}")
            rec_cache = None
    if rec_cache is None:
        try: raw = OCR_ENGINE.ocr(image, cls=True)
        except TypeError: raw = OCR_ENGINE.ocr(image)
        if not raw: return items
        lines = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
    if lines is None: return items
    for line in lines:
        try:
            if line is None: continue
            pts, rec = line
            text, conf = rec[0], rec[1]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if _contains_chinese(text):
                item = {'text': text, 'confidence': float(conf),
                        'bbox': {'x': int(min(xs)), 'y': int(min(ys)),
                                 'w': int(max(xs)-min(xs)), 'h': int(max(ys)-min(ys))}}
                if len(rec) > 2 and rec[2]:
                    try: _add_glyph_geometry(item, image, pts, rec[2])
                    except Exception as e: logger.debug(f"[OCR] glyph geometry skipped: {e}")
                items.append(item)
        except Exception: pass
    return items


def _is_cjk(ch: str) -> bool:
    return '㐀' <= ch <= '䶿' or '一' <= ch <= '鿿'


def _add_glyph_geometry(item, image, pts, word_info):
    """Attach per-character positions and the real ink band of the line.

    The detector box is padded (and stretched by superscripts such as "[2]"),
    so labels placed from it float too high and drift sideways. The CTC
    recognizer knows which column each character fired in, and the image tells
    us where the Chinese glyphs' ink actually starts and ends vertically.
    """
    col_num, word_list, word_col_list, _ = word_info
    if not col_num:
        return
    x0 = min(pts[0][0], pts[3][0]); x1 = max(pts[1][0], pts[2][0])
    cell = (x1 - x0) / col_num
    text = item['text']
    pairs = [(c, col) for word, cols in zip(word_list, word_col_list) for c, col in zip(word, cols)]
    centers = [None] * len(text)
    k = 0
    for i, ch in enumerate(text):
        if k < len(pairs) and pairs[k][0] == ch:
            centers[i] = x0 + (pairs[k][1] + 0.5) * cell
            k += 1
    cjk = [(i, centers[i]) for i, ch in enumerate(text) if _is_cjk(ch) and centers[i] is not None]
    if not cjk:
        return

    # Character pitch from neighbouring Chinese characters.
    steps = [b[1] - a[1] for a, b in zip(cjk, cjk[1:]) if b[0] == a[0] + 1 and b[1] > a[1]]
    b = item['bbox']
    pitch = float(np.median(steps)) if steps else b['h'] * 0.75

    # Ink band measured only under the Chinese characters.
    img_h, img_w = image.shape[:2]
    y1 = max(0, b['y']); y2 = min(img_h, b['y'] + b['h'])
    top, height = b['y'] + b['h'] * 0.15, b['h'] * 0.7
    if y2 - y1 >= 6:
        cols = np.zeros(img_w, dtype=bool)
        for _, cx in cjk:
            cols[max(0, int(cx - pitch / 2)):min(img_w, int(cx + pitch / 2))] = True
        crop = image[y1:y2][:, cols].astype(np.int16)
        if crop.size:
            border = np.concatenate([crop[0], crop[-1]])
            bg = np.median(border, axis=0)
            profile = (np.abs(crop - bg).sum(axis=2) > 90).mean(axis=1)
            rows = np.nonzero(profile >= profile.max() * 0.15)[0] if profile.max() > 0.02 else []
            if len(rows) and rows[-1] - rows[0] + 1 >= b['h'] * 0.3:
                top, height = y1 + rows[0], rows[-1] - rows[0] + 1
                if not steps:
                    pitch = height * 1.05
    item['text_top'] = int(top)
    item['text_h'] = int(height)
    item['chars'] = [{'ch': text[i], 'x': int(round(cx - pitch / 2)), 'w': max(1, int(round(pitch)))}
                     for i, cx in cjk]

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

def run_ocr_oriented(image: np.ndarray, manga_mode=False, rec_cache=None) -> list:
    """Run OCR; in manga mode rotate for vertical text and map boxes back."""
    if not manga_mode:
        return run_ocr(image, rec_cache)
    res = run_ocr(np.ascontiguousarray(np.rot90(image, k=-1)), rec_cache)
    h = image.shape[0]
    for r in res:
        # Glyph geometry is measured in the rotated image; fall back to the box.
        for key in ('chars', 'text_top', 'text_h'):
            r.pop(key, None)
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
    finished = pyqtSignal(list, object)  # results, the image they were read from
    error = pyqtSignal(str)

    def __init__(self, image, manga_mode=False):
        super().__init__()
        self.image = image
        self.manga_mode = manga_mode
        self._is_aborted = False

    def abort(self):
        self._is_aborted = True

    def run(self):
        # Hand the screenshot over with the result; the worker outlives the scan
        # and would otherwise keep a full-screen image alive until the next one.
        image, self.image = self.image, None
        try:
            if self._is_aborted: return
            res = run_ocr_oriented(image, self.manga_mode)
            if self._is_aborted: return
            self.finished.emit(res, image)
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
    results_changed = pyqtSignal()  # fetch the update with take_results()

    TICK_SECONDS = 0.15
    MAX_MISSES = 3  # OCR passes an unchanged item may be missed before it is dropped

    def __init__(self, region, manga_mode=False, min_ocr_interval=0.3):
        super().__init__()
        x, y, w, h = region
        self.monitor = {'left': x, 'top': y, 'width': max(w, 1), 'height': max(h, 1)}
        self.manga_mode = manga_mode
        self.min_ocr_interval = min_ocr_interval
        self._stop = threading.Event()
        self._latest = None
        self._latest_lock = threading.Lock()

    def stop(self):
        self._stop.set()

    def take_results(self):
        """(items, current frame as RGB ndarray) of the newest update, or None."""
        with self._latest_lock:
            latest, self._latest = self._latest, None
        return latest

    def _publish(self, items, rgb):
        # Only the newest frame is kept, and a signal is queued only when none is
        # pending, so a busy GUI thread cannot pile up full-screen frames.
        with self._latest_lock:
            pending = self._latest is not None
            self._latest = (items, rgb)
        if not pending:
            self.results_changed.emit()

    def run(self):
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        rec_cache = RecognitionCache()
        tracked = []
        future = None
        ocr_gray = None
        last_ocr_small = None
        last_ocr_time = 0.0
        try:
            with mss.mss() as sct:
                while not self._stop.is_set():
                    started = time.monotonic()
                    bgra = np.array(sct.grab(self.monitor))
                    gray = bgra[:, :, 1]  # green channel: same index in BGRA and RGB
                    rgb = None  # full RGB copy only when OCR or the overlay needs it
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
                        rgb = bgra[:, :, 2::-1].copy()
                        future = executor.submit(run_ocr_oriented, rgb, self.manga_mode, rec_cache)

                    if changed:
                        if rgb is None:
                            rgb = bgra[:, :, 2::-1].copy()
                        items = [{k: v for k, v in t.items() if k not in ('patch', 'misses')} for t in tracked]
                        self._publish(items, rgb)

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
