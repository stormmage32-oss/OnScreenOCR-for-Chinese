# Chinese Screen OCR

A Pleco-style screen reader for Windows that allows you to easily capture and read Chinese text from your screen. It features OCR (Optical Character Recognition) powered by PaddleOCR, dictionary lookups, Pinyin generation, HSK level tagging, and DeepL translation integration.

## Features

- **Quick Region Scan**: Select any part of your screen to instantly extract and read Chinese text.
- **Full Screen Scan**: Scan the entire screen with a customizable global hotkey (default: `Alt+S`).
- **Interactive Dictionary**: Click or hover over recognized words to see Pinyin, English meanings, and HSK levels.
- **DeepL Integration**: Translate full sentences into English automatically (requires a free DeepL API key).
- **Manga Mode**: Specialized support for vertical Chinese text.
- **Vocabulary Notebook**: Save words you want to remember and export them to Anki for spaced repetition learning.
- **Offline Capable**: After the initial download of the OCR models, the core recognition and dictionary features work entirely offline.

## Requirements

- Windows OS
- For `START.bat`: Python 3.8 to 3.12 installed and added to PATH.
- For setup builds: Python 3.10 or 3.11 and Inno Setup 6 on the build machine.

## Installation & Usage (Easiest Way)

For beginners or users who just want to run the app without hassle:

1. Download or clone this repository.
2. Double-click **`START.bat`**.
3. On the first run, the script will automatically install all required dependencies (this may take a few minutes).
4. The application will start immediately after the installation is complete. On subsequent runs, `START.bat` will skip the installation and launch the app instantly.

> **Note:** The first time you scan an image, PaddleOCR will download its lightweight AI models. This is a one-time process and will take 1-3 minutes depending on your internet connection.

## Manual Execution

If you prefer to run things manually:

1. Run `install.bat` to install the dependencies via pip.
2. Run `run.bat` to start the application.

## Build Setup

To create a Windows setup installer, double-click `build_setup.bat` or `build_installer.bat`.

The setup build creates an isolated `.build-venv`, bundles the full app into `dist/ChineseScreenOCR`, then writes the installer to `installer_output/ChineseScreenOCR-Setup.exe`.

## Build Lightweight Executable

`build_exe.bat` only creates the small launcher executable. PyInstaller also creates `build/` and `dist/` folders while doing this, and the script copies `dist/ChineseScreenOCR.exe` to the project root. This is not the setup installer.

### Troubleshooting

- **PyQt5 Issues**: If the UI doesn't launch, run `fix_pyqt.bat` to reinstall PyQt5.
- **Environment Diagnostics**: If you encounter OCR issues, run `diagnose.bat` to check if PaddlePaddle and PaddleOCR are installed correctly.

## Acknowledgments

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) for the powerful OCR engine.
- CC-CEDICT for the comprehensive Chinese-English dictionary.
