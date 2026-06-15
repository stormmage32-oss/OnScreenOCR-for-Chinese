# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

datas = [
    ("cedict_ts.u8", "."),
]
datas += collect_data_files("Cython")
binaries = []
hiddenimports = [
    "paddleocr",
    "paddle",
]

for package in ("paddleocr", "paddle", "pyclipper", "shapely", "skimage", "imgaug", "lmdb"):
    try:
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hiddenimports
    except Exception:
        try:
            hiddenimports += collect_submodules(package)
        except Exception:
            pass

for package in ("paddleocr", "paddlepaddle", "opencv-python", "scikit-image", "imgaug"):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ChineseScreenOCR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ChineseScreenOCR",
)
