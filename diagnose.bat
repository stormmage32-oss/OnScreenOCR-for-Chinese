@echo off
chcp 65001 >nul 2>&1
title OCR Diagnostics

echo ===== SYSTEM DIAGNOSTICS =====
echo.

python --version
echo Python PATH: ok
echo.

echo --- Libraries ---
python -c "import PyQt5; print('[OK] PyQt5', PyQt5.QtCore.PYQT_VERSION_STR)" 2>&1
python -c "import mss; print('[OK] mss')" 2>&1
python -c "import PIL; print('[OK] Pillow', PIL.__version__)" 2>&1
python -c "import numpy; print('[OK] numpy', numpy.__version__)" 2>&1
python -c "import pypinyin; print('[OK] pypinyin')" 2>&1
echo.

echo --- OCR Engine (PaddleOCR) ---
python -c "import paddle; print('[OK] paddlepaddle', paddle.__version__)" 2>&1
python -c "from paddleocr import PaddleOCR; print('[OK] paddleocr import OK')" 2>&1
echo.

echo --- Full OCR Test ---
python -c "
import sys, re

def parse_ver(s):
    m = re.match(r'(\d+)\.(\d+)', s)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

print('--- PaddleOCR test ---')
try:
    import paddle
    pver = parse_ver(paddle.__version__)
    print('PaddlePaddle version:', paddle.__version__)
    from paddleocr import PaddleOCR
    import numpy as np

    if pver >= (3, 0):
        ocr = PaddleOCR(lang='ch', show_log=False)
        dummy = np.zeros((64, 200, 3), dtype=np.uint8)
        try:
            ocr.ocr(dummy, cls=True)
        except TypeError:
            ocr.ocr(dummy)
        print('[OK] PaddleOCR 3.x is working!')
    else:
        ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
        dummy = np.zeros((64, 200, 3), dtype=np.uint8)
        ocr.ocr(dummy, cls=True)
        print('[OK] PaddleOCR 2.x is working!')
    sys.exit(0)
except Exception as e:
    print('[FAIL] PaddleOCR:', e)
    sys.exit(1)
" 2>&1

echo.
echo ===== DIAGNOSTICS FINISHED =====
pause
