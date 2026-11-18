import os
import logging
import warnings
import re
import numpy as np
from functools import lru_cache
from app_paths import bundled_path

logger = logging.getLogger("OCRApp")

# Suppress setuptools pkg_resources warnings in older libraries like jieba
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")
import jieba

try:
    from hsk_dict import HSK_DICT
    logger.info(f"[HSK] Dictionary loaded: {len(HSK_DICT)} words")
except Exception as e:
    HSK_DICT = {}
    logger.error(f"[HSK] Failed to load dictionary: {e}")

# Load CC-CEDICT for full character/word coverage
CEDICT = {}  # simplified -> [{'pinyin': str, 'meanings': list}]

def _load_local_cedict(file_path):
    line_re = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.*)/$")
    with open(file_path, "r", encoding="utf-8") as cedict_file:
        for raw_line in cedict_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = line_re.match(line)
            if not match:
                continue
            _traditional, simplified, pinyin, meanings_text = match.groups()
            meanings = [meaning for meaning in meanings_text.split("/") if meaning]
            CEDICT.setdefault(simplified, []).append({
                "pinyin": pinyin,
                "meanings": meanings
            })

try:
    _local_cedict = bundled_path("cedict_ts.u8")
    try:
        from cedict_utils.cedict import CedictParser
    except Exception:
        CedictParser = None

    if os.path.exists(_local_cedict) and CedictParser is None:
        logger.info(f"[CEDICT] Loading local file without cedict_utils: {_local_cedict}")
        _load_local_cedict(_local_cedict)
    elif os.path.exists(_local_cedict):
        logger.info(f"[CEDICT] Loading local updated file: {_local_cedict}")
        _parser = CedictParser(file_path=_local_cedict)
        _entries = _parser.parse()
        for _e in _entries:
            _k = _e.simplified
            if _k not in CEDICT:
                CEDICT[_k] = []
            CEDICT[_k].append({'pinyin': _e.pinyin, 'meanings': _e.meanings})
    elif CedictParser is not None:
        logger.info("[CEDICT] Using default package file...")
        _parser = CedictParser()
        _entries = _parser.parse()
        for _e in _entries:
            _k = _e.simplified
            if _k not in CEDICT:
                CEDICT[_k] = []
            CEDICT[_k].append({'pinyin': _e.pinyin, 'meanings': _e.meanings})
    else:
        logger.warning("[CEDICT] No local cedict_ts.u8 file and cedict_utils is not installed")
    logger.info(f"[CEDICT] Dictionary loaded: {len(CEDICT)} unique words")
except Exception as _ce:
    logger.error(f"[CEDICT] Failed to load: {_ce}")

HSK_COLORS = {
    1: '#5A9E5A', 2: '#4A7FA0', 3: '#8A5AA0', 4: '#C09030',
    5: '#C07A40', 6: '#B85450', 7: '#7A6B5D', 0: '#9B8B7A'
}
HSK_LABELS = {
    1: 'HSK 1 · Beginner', 2: 'HSK 2 · Elementary', 3: 'HSK 3 · Pre-Intermediate',
    4: 'HSK 4 · Intermediate', 5: 'HSK 5 · Upper-Intermediate', 6: 'HSK 6 · Advanced',
    7: 'HSK 7-9 · Advanced-High', 0: 'Non-HSK'
}

# Pinyin tone number -> tone mark conversion
_TONE_MAP = {
    'a': ['ā','á','ǎ','à','a'], 'e': ['ē','é','ě','è','e'],
    'i': ['ī','í','ǐ','ì','i'], 'o': ['ō','ó','ǒ','ò','o'],
    'u': ['ū','ú','ǔ','ù','u'], 'ü': ['ǖ','ǘ','ǚ','ǜ','ü'],
    'v': ['ǖ','ǘ','ǚ','ǜ','ü'],
}

def _convert_tone(syllable: str) -> str:
    if not syllable:
        return syllable
    tone = 0
    if syllable[-1].isdigit():
        tone = int(syllable[-1])
        syllable = syllable[:-1]
    if tone == 0 or tone == 5:
        return syllable
    for vowel in ['iu', 'ui', 'a', 'e', 'o', 'i', 'u', 'ü', 'v']:
        if vowel in syllable:
            if len(vowel) == 2:
                v2 = vowel[1]
                marks = _TONE_MAP.get(v2, None)
                if marks:
                    return syllable.replace(vowel, vowel[0] + marks[tone - 1], 1)
            else:
                marks = _TONE_MAP.get(vowel, None)
                if marks:
                    return syllable.replace(vowel, marks[tone - 1], 1)
    return syllable

def tone_numbers_to_marks(pinyin_str: str) -> str:
    return ' '.join(_convert_tone(syl) for syl in pinyin_str.split())

@lru_cache(maxsize=4096)
def lookup_hsk(word):
    if word in HSK_DICT:
        return HSK_DICT[word]
    return None

@lru_cache(maxsize=4096)
def lookup_cedict(word):
    entries = CEDICT.get(word)
    if not entries:
        return None
    skip_meaning_prefixes = ('surname ', 'given name', 'name of ', 'place name')
    common  = [e for e in entries if e['pinyin'] and e['pinyin'][0].islower()]
    proper  = [e for e in entries if e['pinyin'] and e['pinyin'][0].isupper()]
    def _score(e):
        s = 0
        if e['pinyin'].endswith('5'): s -= 1
        if all(m.strip().startswith('see ') for m in e['meanings']): s += 5
        return s
    ranked = sorted(common, key=_score) if common else sorted(proper, key=_score)
    for e in ranked:
        filtered = [m for m in e['meanings']
                    if not any(m.lower().startswith(kw) for kw in skip_meaning_prefixes)
                    and not m.strip().startswith('see ')]
        meanings = filtered if filtered else e['meanings']
        return {
            'pinyin': tone_numbers_to_marks(e['pinyin']),
            'meanings': meanings
        }
    return None

def lookup_word(word):
    ced = lookup_cedict(word)
    hsk = lookup_hsk(word)
    if ced and hsk:
        merged = {
            'level':    hsk.get('level', 0),
            'pinyin':   ced['pinyin'],
            'meanings': ced['meanings'],
            'pos':      hsk.get('pos', []),
        }
        return merged, 'hsk'
    if ced:
        return ced, 'cedict'
    if hsk:
        return hsk, 'hsk'
    return None, None

CHAR_MIN_LEVEL = {}
for w, info in HSK_DICT.items():
    lvl = info['level']
    for ch in w:
        if ch not in CHAR_MIN_LEVEL or lvl < CHAR_MIN_LEVEL[ch]:
            CHAR_MIN_LEVEL[ch] = lvl

def get_derived_hsk_level(word: str) -> tuple[int, bool]:
    hsk_w = lookup_hsk(word)
    if hsk_w and hsk_w.get('level', 0) > 0:
        return hsk_w.get('level', 0), False
        
    c_levels = []
    has_cjk = False
    for ch in word:
        if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
            has_cjk = True
            c_levels.append(CHAR_MIN_LEVEL.get(ch, 7))
            
    if has_cjk and c_levels:
        return max(c_levels), True
    return 0, False

def get_char_weight(ch: str) -> float:
    if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
        return 1.0
    if ch in '，。！？；：（）“”‘’【】《》「」『』〈〉、…—～':
        return 1.0
    if ch.isspace():
        return 0.4
    return 0.5

def _has_chinese(text: str) -> bool:
    return any('\u3400' <= ch <= '\u4dbf' or '\u4e00' <= ch <= '\u9fff' for ch in text)

_ASCII_PUNCT = ',.!?;:()'


def _layout_weights(text: str) -> list:
    """Relative on-screen width of every character in an OCR line."""
    cjk_line = _has_chinese(text)
    out = []
    for i, ch in enumerate(text):
        w = get_char_weight(ch)
        if cjk_line and ch in _ASCII_PUNCT:
            prev_digit = i > 0 and text[i - 1].isdigit()
            next_digit = i + 1 < len(text) and text[i + 1].isdigit()
            # OCR often reports "，" as ",": in a Chinese line it still takes a
            # full cell. A separator inside a number ("1,566") stays narrow.
            if not (prev_digit and next_digit):
                w = 1.0
        out.append(w)
    return out


def _ink_span(image, bbox, vertical, max_trim):
    """Start/end offsets of the text's ink along the line, trimming at most max_trim per side.

    PaddleOCR's line boxes have some empty margin; spreading characters over
    that margin shifts every box. Returns (0, size) when the image can't tell.
    """
    size = bbox['h'] if vertical else bbox['w']
    if image is None or max_trim < 1:
        return 0.0, float(size)
    try:
        img_h, img_w = image.shape[:2]
        x1, y1 = max(0, bbox['x']), max(0, bbox['y'])
        x2, y2 = min(img_w, bbox['x'] + bbox['w']), min(img_h, bbox['y'] + bbox['h'])
        if x2 - x1 < 4 or y2 - y1 < 4:
            return 0.0, float(size)
        crop = image[y1:y2, x1:x2].astype(np.int16)
        if crop.ndim == 2:
            crop = crop[:, :, None]
        border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
        diff = np.abs(crop - np.median(border, axis=0)).sum(axis=2)
        # Low threshold: faint anti-aliased edges must count as text.
        profile = (diff > 60).sum(axis=1 if vertical else 0)
        cols = np.nonzero(profile)[0]
        if len(cols) == 0:
            return 0.0, float(size)
        off = (y1 - bbox['y']) if vertical else (x1 - bbox['x'])
        start = min(float(cols[0] + off), max_trim)
        end = max(float(cols[-1] + 1 + off), size - max_trim)
        if end - start < size * 0.5:
            return 0.0, float(size)
        return start, end
    except Exception as e:
        logger.debug(f"[SEG] ink span failed: {e}")
        return 0.0, float(size)


def _char_positions(res):
    """Text index -> (x, w) of Chinese characters whose position OCR reported."""
    chars = res.get('chars')
    if not chars:
        return {}
    pos, k = {}, 0
    for i, ch in enumerate(res['text']):
        if k < len(chars) and chars[k]['ch'] == ch:
            pos[i] = (chars[k]['x'], chars[k]['w'])
            k += 1
    return pos


def _line_ink(image, bbox):
    """(ink mask of the line box, its x, its y), or None. Background = median border colour."""
    if image is None:
        return None
    try:
        img_h, img_w = image.shape[:2]
        x1, y1 = max(0, bbox['x']), max(0, bbox['y'])
        x2, y2 = min(img_w, bbox['x'] + bbox['w']), min(img_h, bbox['y'] + bbox['h'])
        if x2 - x1 < 4 or y2 - y1 < 4:
            return None
        crop = image[y1:y2, x1:x2].astype(np.int16)
        if crop.ndim == 2:
            crop = crop[:, :, None]
        border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
        diff = np.abs(crop - np.median(border, axis=0)).sum(axis=2)
        if diff.max() < 60:
            return None
        # Low threshold so the faint anti-aliased edges of strokes count as text.
        return diff > max(60, diff.max() * 0.2), x1, y1
    except Exception as e:
        logger.debug(f"[SEG] line ink failed: {e}")
        return None


def _fitted_word_box(res, first, last, ink, pad=2):
    """Box hugging the glyphs of text[first:last], or None.

    OCR says where each character's centre is. The word may only take ink from
    halfway to its neighbours' centres (and at most ~0.6 character from its own
    outer characters, so a character OCR skipped isn't swallowed); inside that
    range the box is cut to the exact ink. Height is the line's text band.
    """
    centers, pitch = res.get('centers'), res.get('pitch')
    if not centers or not pitch or ink is None:
        return None
    known = [i for i in range(first, last) if centers[i] is not None]
    if not known:
        return None
    mask, mx, my = ink
    c_first, c_last = centers[known[0]], centers[known[-1]]
    prev = next((centers[i] for i in range(first - 1, -1, -1) if centers[i] is not None), None)
    nxt = next((centers[i] for i in range(last, len(centers)) if centers[i] is not None), None)
    left = c_first - 0.52 * pitch
    right = c_last + 0.52 * pitch
    if prev is not None:
        left = max(left, (prev + c_first) / 2)
    if nxt is not None:
        right = min(right, (c_last + nxt) / 2)

    a, b = int(round(left)) - mx, int(round(right)) - mx
    a, b = max(0, a), min(mask.shape[1], b)
    if b - a < 2:
        return None
    cols = np.nonzero(mask[:, a:b].any(axis=0))[0]
    if len(cols) == 0:
        return None
    x0, x1 = mx + a + cols[0], mx + a + cols[-1] + 1
    if x1 - x0 < 0.3 * pitch * len(known) / max(1, last - first):
        return None  # found only a speck: not the glyphs we expected

    if 'text_top' in res:
        y0, y1 = res['text_top'], res['text_top'] + res['text_h']
    else:
        rows = np.nonzero(mask.any(axis=1))[0]
        y0, y1 = my + rows[0], my + rows[-1] + 1
    return {'x': int(x0 - pad), 'y': int(y0 - pad), 'w': int(x1 - x0 + 2 * pad), 'h': int(y1 - y0 + 2 * pad)}


def segment_ocr_results(results, image=None):
    """Split OCR lines into clickable dictionary words with their own boxes.

    When OCR reports where each character sits ('chars'), boxes come from that,
    so a character OCR skipped can't shift the rest of the line. Otherwise words
    are spread over the line by character width. image: the screenshot the
    results came from; it is only used to trim the line box's empty margin.
    """
    word_results = []
    for res in results:
        text = res['text']
        bbox = res['bbox']
        conf = res.get('confidence', 0)
        words = list(jieba.cut(text, cut_all=False))
        weights = _layout_weights(text)
        total_weight = sum(weights)
        if total_weight == 0:
            word_results.append(res)
            continue

        is_vertical = bbox['h'] > bbox['w'] * 1.5
        box_size = bbox['h'] if is_vertical else bbox['w']
        # Never trim more than half a character from either end.
        start, end = _ink_span(image, bbox, is_vertical, 0.5 * box_size / total_weight)
        unit = (end - start) / total_weight
        cursor = float(bbox['y'] if is_vertical else bbox['x']) + start
        char_pos = {} if is_vertical else _char_positions(res)
        ink = None if is_vertical or not res.get('centers') else _line_ink(image, bbox)

        idx = 0
        for w in words:
            first = idx
            w_size = unit * sum(weights[idx:idx + len(w)])
            idx += len(w)

            # Paddle can return mixed lines. Do not draw clickable boxes for
            # their Latin-only fragments in a Chinese reader.
            if not _has_chinese(w) or not w.strip():
                cursor += w_size
                continue

            known = [char_pos[i] for i in range(first, idx) if i in char_pos]
            fitted = None if is_vertical else _fitted_word_box(res, first, idx, ink)
            if fitted is not None:
                new_bbox = fitted
            elif is_vertical:
                new_bbox = {'x': bbox['x'], 'y': int(round(cursor)),
                            'w': bbox['w'], 'h': max(int(round(w_size)), 2)}
            elif known:
                left = min(x for x, _ in known)
                right = max(x + cw for x, cw in known)
                new_bbox = {'x': int(left), 'y': bbox['y'], 'w': max(int(right - left), 2), 'h': bbox['h']}
            else:
                new_bbox = {'x': int(round(cursor)), 'y': bbox['y'],
                            'w': max(int(round(w_size)), 2), 'h': bbox['h']}
            word_results.append({
                'text': w,
                'confidence': conf,
                'bbox': new_bbox,
                'hsk': lookup_hsk(w),
                'original_sentence': text
            })
            cursor += w_size
    return word_results


def get_pinyin(text: str) -> str:
    try:
        from pypinyin import pinyin, Style
        return ' '.join(p[0] for p in pinyin(text, style=Style.TONE))
    except Exception:
        return ''
