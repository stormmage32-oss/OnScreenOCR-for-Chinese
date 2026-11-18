"""Setup checks run by launcher.ps1 inside the app's virtual environment.

    python check_env.py versions   every package in requirements.txt is installed at its pinned version
    python check_env.py imports    the libraries the app needs can be imported
    python check_env.py models     PaddleOCR loads (downloads its model files the first time)

Prints one line per problem and exits 1 on failure, 0 on success.
"""
import os
import re
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def check_versions():
    from importlib import metadata
    installed = {_norm(d.metadata["Name"]): d.version for d in metadata.distributions()}
    problems = []
    with open(os.path.join(APP_DIR, "requirements.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if "==" not in line:
                continue
            name, version = (part.strip() for part in line.split("==", 1))
            have = installed.get(_norm(name))
            if have != version:
                problems.append(f"{name}: need {version}, have {have or 'nothing'}")
    return problems


def check_imports():
    problems = []
    for module in ("PyQt5.QtWidgets", "numpy", "cv2", "paddle", "paddleocr",
                   "mss", "pypinyin", "jieba", "keyboard", "requests"):
        try:
            __import__(module)
        except Exception as e:  # noqa: BLE001 - report every kind of import failure
            problems.append(f"import {module}: {type(e).__name__}: {e}")
    return problems


def check_models():
    import logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
    sys.path.insert(0, APP_DIR)
    from ocr_engine import init_ocr
    return [] if init_ocr() else ["PaddleOCR could not be loaded (see the log above)"]


def main():
    # Progress bars and warnings from libraries go to stderr; keep them in one stream.
    sys.stderr = sys.stdout
    checks = {"versions": check_versions, "imports": check_imports, "models": check_models}
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in checks:
        print(f"usage: check_env.py {'|'.join(checks)}")
        return 2
    problems = checks[name]()
    for p in problems:
        print(f"PROBLEM: {p}")
    print("OK" if not problems else f"FAILED ({len(problems)} problem(s))")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
