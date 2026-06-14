import os
import logging
import warnings
from functools import lru_cache

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
try:
    from cedict_utils.cedict import CedictParser
    _local_cedict = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cedict_ts.u8")
    if os.path.exists(_local_cedict):
        logger.info(f"[CEDICT] Loading local updated file: {_local_cedict}")
        _parser = CedictParser(file_path=_local_cedict)
    else:
        logger.info("[CEDICT] Using default package file...")
        _parser = CedictParser()
    _entries = _parser.parse()
    for _e in _entries:
        _k = _e.simplified
        if _k not in CEDICT:
            CEDICT[_k] = []
        CEDICT[_k].append({'pinyin': _e.pinyin, 'meanings': _e.meanings})
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
    if ch in '，。！？；：（）“”‘’【】《》':
        return 1.0
    if ch.isspace():
        return 0.4
    return 0.5

def segment_ocr_results(results):
    word_results = []
    for res in results:
        text = res['text']
        bbox = res['bbox']
        conf = res.get('confidence', 0)
        words = list(jieba.cut(text, cut_all=False))
        
        total_weight = sum(get_char_weight(c) for c in text)
        if total_weight == 0:
            word_results.append(res)
            continue
            
        is_vertical = bbox['h'] > bbox['w'] * 1.5
        box_size = bbox['h'] if is_vertical else bbox['w']
        cursor = float(bbox['y'] if is_vertical else bbox['x'])
        
        for w in words:
            w_weight = sum(get_char_weight(c) for c in w)
            w_size = box_size * (w_weight / total_weight)
            
            if w.strip():
                hsk_info = lookup_hsk(w)
                if is_vertical:
                    new_bbox = {
                        'x': bbox['x'],
                        'y': int(round(cursor)),
                        'w': bbox['w'],
                        'h': max(int(round(w_size)), 2)
                    }
                else:
                    new_bbox = {
                        'x': int(round(cursor)),
                        'y': bbox['y'],
                        'w': max(int(round(w_size)), 2),
                        'h': bbox['h']
                    }
                
                word_results.append({
                    'text': w,
                    'confidence': conf,
                    'bbox': new_bbox,
                    'hsk': hsk_info,
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
