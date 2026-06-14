# -*- coding: utf-8 -*-
"""
Build hsk_dict.py from New HSK 3.0 PDF vocabulary files.
Run once: python build_hsk_dict.py

CRITICAL FIX: These PDFs use Kangxi Radicals (U+2F00-U+2FDF) and CJK
Compatibility Ideographs instead of standard CJK Unified Ideographs.
We must normalize all text with NFKC before processing.
"""
import re, os, sys, io, warnings, unicodedata
import pdfplumber

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
warnings.filterwarnings("ignore")

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files 0.12", "HSK3.0 Levels")

PDF_FILES = {
    1: "New-HSK-Vocabulary-Level-1.pdf",
    2: "New-HSK-Vocabulary-Level-2.pdf",
    3: "New-HSK-Vocabulary-Level-3.pdf",
    4: "New-HSK-Vocabulary-Level-4.pdf",
    5: "New-HSK-Vocabulary-Level-5.pdf",
    6: "New-HSK-Vocabulary-L6.pdf",
    7: "New-HSK-Vocabulary-Level-7-9.pdf",
}

LEVEL_MAP = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}

def is_chinese(s):
    return any('\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' for c in s)

def normalize_text(text):
    """Normalize Kangxi radicals and CJK compatibility chars to standard CJK."""
    return unicodedata.normalize('NFKC', text)

def extract_entries(pdf_path, level):
    entries = {}
    print(f"  Processing Level {level}: {os.path.basename(pdf_path)}")

    no_translation = (level == 7)

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            # CRITICAL: Normalize Unicode BEFORE any regex matching
            text = normalize_text(text)
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Skip header/footer lines
                if 'MandarinBean' in line or 'Page' in line or 'Level' in line:
                    continue

                if no_translation:
                    # Format: "1 挨 āi 动、介" or "1 挨家挨户 āijiā-āihù"
                    m = re.match(
                        r'^\d+\s+'
                        r'([\u4e00-\u9fff\u3400-\u4dbf]+(?:[·\u30fb\s]?[\u4e00-\u9fff\u3400-\u4dbf]+)*)\s+'
                        r'([a-zāáǎàēéěèīíǐìōóǒùūúǔǖǘǚǜü,\'\-\s]+?)(?:\s+[\u4e00-\u9fff、,、\s]*)?$',
                        line, re.IGNORECASE
                    )
                    if m:
                        word = m.group(1).strip().replace(' ', '')
                        pinyin = m.group(2).strip()
                        if is_chinese(word):
                            entries[word] = {
                                'level': LEVEL_MAP[level],
                                'pinyin': pinyin,
                                'meanings': []
                            }
                else:
                    # Format: "1 爱 ài verb to love"
                    # First try full match with POS + translation
                    m = re.match(
                        r'^\d+\s+'
                        r'([\u4e00-\u9fff\u3400-\u4dbf]+(?:[\s]?[\u4e00-\u9fff\u3400-\u4dbf]+)*)\s+'
                        r'([a-zāáǎàēéěèīíǐìōóǒòùūúǔǖǘǚǜü,\s\-\']+?)\s+'
                        r'(?:noun|verb|adjective|adverb|pronoun|number|classifier|preposition|'
                        r'conjunction|interjection|auxiliary|prefix|suffix|particle|phrase|idiom|'
                        r'measure|determiner|numeral|modal|proper|[\w\s,\/\(\)、]+?)\s+(.+)',
                        line, re.IGNORECASE
                    )
                    if m:
                        word = m.group(1).strip().replace(' ', '')
                        pinyin = m.group(2).strip()
                        meaning = m.group(3).strip()
                        if is_chinese(word):
                            entries[word] = {
                                'level': LEVEL_MAP[level],
                                'pinyin': pinyin,
                                'meanings': [meaning]
                            }
                        continue

                    # Simpler fallback: number + chinese + pinyin + rest
                    m2 = re.match(
                        r'^\d+\s+'
                        r'([\u4e00-\u9fff\u3400-\u4dbf\s]+?)\s+'
                        r'([a-zāáǎàēéěèīíǐìōóǒòùūúǔǖǘǚǜü,\s\-\']+?)\s+(.+)',
                        line, re.IGNORECASE
                    )
                    if m2:
                        word = m2.group(1).strip().replace(' ', '')
                        pinyin = m2.group(2).strip()
                        meaning = m2.group(3).strip()
                        if is_chinese(word) and len(word) >= 1:
                            entries[word] = {
                                'level': LEVEL_MAP[level],
                                'pinyin': pinyin,
                                'meanings': [meaning]
                            }

    print(f"    -> {len(entries)} entries found")
    return entries


all_entries = {}

for level, filename in PDF_FILES.items():
    path = os.path.join(BASE, filename)
    if not os.path.exists(path):
        print(f"  [SKIP] Not found: {filename}")
        continue
    entries = extract_entries(path, level)
    for word, info in entries.items():
        if word not in all_entries:
            all_entries[word] = info

print(f"\nTotal entries: {len(all_entries)}")

# Write hsk_dict.py
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsk_dict.py")
with open(out_path, 'w', encoding='utf-8') as f:
    f.write("# -*- coding: utf-8 -*-\n")
    f.write("# Auto-generated from New HSK 3.0 PDF vocabulary files\n")
    f.write("# DO NOT EDIT MANUALLY\n\n")
    f.write("HSK_DICT = {\n")
    for word, info in sorted(all_entries.items()):
        f.write(f"    {repr(word)}: {{'level': {info['level']}, 'pinyin': {repr(info['pinyin'])}, 'meanings': {repr(info['meanings'])}}},\n")
    f.write("}\n")

print(f"Written to: {out_path}")

# Level breakdown
from collections import Counter
lvl_counts = Counter(v['level'] for v in all_entries.values())
for lv in sorted(lvl_counts):
    label = f"HSK 7-9" if lv == 7 else f"HSK {lv}"
    print(f"  {label}: {lvl_counts[lv]} words")
