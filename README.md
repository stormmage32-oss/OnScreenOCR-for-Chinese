# Chinese Screen OCR

Chinese Screen OCR is a small Windows tool for reading Chinese text directly from the screen. It is useful for games, manga, screenshots, videos, websites, and any app where the text is not easy to copy.

You can scan a selected area, scan the full screen, click recognized words for dictionary details, or show a temporary pinyin overlay on top of the current screen.

## Examples

### Game Text

![Chinese pinyin overlay on game text](EXAMPLES/Game.webp)

The pinyin overlay can sit on top of game menus and dialogue without opening a separate result window. Press the overlay hotkey again to hide it and continue playing.

### Manga / Vertical Text

![Chinese OCR on manga text](EXAMPLES/Manga.webp)

Manga mode helps with vertical Chinese text. You can scan a panel, inspect recognized words, and save vocabulary while reading.

## Features

- Region scan: drag over any part of the screen and run OCR on that area.
- Full screen scan: scan the active screen with a hotkey.
- Pinyin overlay: show pinyin directly above Chinese characters, then toggle it off with the same hotkey.
- Adaptive pinyin color: overlay text changes color based on the screen area behind it for better contrast.
- Dictionary popups: click recognized text to see pinyin, meanings, and HSK information.
- Hover hints: hover over recognized boxes for quick word feedback.
- Manga mode: rotate OCR handling for vertical Chinese text.
- DeepL translation: optional sentence translation with your own DeepL API key.
- Vocabulary notebook: save words and export them for Anki.
- System tray support: keep the app running in the background.
- Offline dictionary: CC-CEDICT and HSK data are bundled locally.

## Hotkeys

- Full screen scan: `Alt+S` by default.
- Pinyin overlay: `Alt+P` by default.

Both hotkeys can be changed from the main window.

## Requirements

- Windows.
- Python 3.8 to 3.12 for running from source with `START.bat`.
- Python 3.10 or 3.11 plus Inno Setup 6 if you want to build the setup installer.

The first OCR run may download PaddleOCR model files. After that, normal OCR and dictionary lookup can work offline.

## Quick Start

1. Download or clone this repository.
2. Double-click `START.bat`.
3. Wait for the first-time dependency setup to finish.
4. Use `Select Region & Scan`, `Scan Full Screen`, or the hotkeys.

On later runs, `START.bat` reuses the local `.venv` and starts faster.

## Manual Run

If you prefer doing the steps yourself:

1. Run `install.bat`.
2. Run `run.bat`.

## Building

### Setup Installer

To create a Windows setup installer, double-click:

```text
build_setup.bat
```

or:

```text
build_installer.bat
```

The installer is written to:

```text
installer_output\ChineseScreenOCR-Setup.exe
```

This build uses `.build-venv`, PyInstaller, and Inno Setup. Build output folders are ignored by git.

### Lightweight Launcher EXE

`build_exe.bat` creates only a small launcher executable. It is not the setup installer.

PyInstaller will create `build/`, `dist/`, and a root `ChineseScreenOCR.exe` while doing this. Those files are build outputs.

## Troubleshooting

- If the UI does not launch, run `fix_pyqt.bat`.
- If OCR fails, run `diagnose.bat`.
- If PaddleOCR behaves strangely after dependency changes, run `repair_paddleocr.bat`.
- If setup building fails with an Inno Setup error, install Inno Setup 6 and run `build_setup.bat` again.

## Data Files

Runtime settings and saved words are stored under the user's AppData folder. Old root-level `config.json` and `saved_words.json` files are still supported for migration.

## Credits

- PaddleOCR for Chinese OCR.
- CC-CEDICT for Chinese-English dictionary data.
- Jieba and pypinyin for segmentation and pinyin support.
