# Chinese Screen OCR

A Windows tool for reading Chinese text anywhere on the screen: games, manga, videos, websites, screenshots, any app where the text can't be copied. Scan an area, click a word for its pinyin and meaning, or keep pinyin floating over a game while you play.

## Getting started

1. Download this folder (on GitHub: **Code → Download ZIP**, then extract it).
2. Double-click **`Chinese Screen OCR.bat`**.

The first start opens a setup window that shows each step and a log while it installs everything. It needs an internet connection and takes a few minutes (about 400 MB to download). After that, the same file starts the app directly.

- If Python 3.12 isn't installed, setup downloads it from python.org into this folder. Nothing is installed system-wide, and no administrator rights are needed.
- Everything lives in this folder (`.venv` and `.runtime`). To uninstall, delete the folder.
- If setup stops, the window shows why. **Try again** continues where it left off; **Open log file** opens the full log.

Requirements: Windows 10 or 11, 64-bit.

## Examples

### Game text

![Pinyin over game text](examples/Game.webp)

### Manga / vertical text

![OCR on a manga page](examples/Manga.webp)

## Features

- **Select region**: drag a box over any part of the screen and read it.
- **Seamless mode**: scan the screen under the mouse into a borderless view and click words right where they are. `Esc` returns to the game or app.
- **Live pinyin**: keeps scanning the screen (or a box you draw) and shows pinyin above every Chinese character in real time. The layer never takes clicks or focus, so you keep playing.
- **Dictionary popup**: click a word for its pinyin, meanings and HSK level. Drag over several words to look them up together.
- **Save words**: hover a word and press `S` (configurable), or use Save in the popup. Saved words can be searched and exported for Anki.
- **DeepL translation** (optional, with your own free API key): phrases that aren't in the dictionary are translated automatically; double-click or turn on *Always translate* for any word.
- **Manga mode** for vertical text.
- Offline dictionary: CC-CEDICT and HSK word lists are included.

## Shortcuts

| Action | Default |
|---|---|
| Seamless mode | `Alt+Shift+S` |
| Pinyin overlay | `Alt+P` |
| Live pinyin | `Alt+L` |
| Live pinyin in a region | `Alt+Shift+L` |
| Save the word under the mouse (in a scan) | `S` |

All shortcuts can be changed in **Settings**.

## Troubleshooting

- **The app doesn't open after setup**: start `Chinese Screen OCR.bat` again; if it fails, the setup window opens with the reason.
- **Setup says the folder path has special characters**: move the folder somewhere simple, such as `C:\ChineseScreenOCR`.
- Logs and saved data are in `%APPDATA%\ChineseScreenOCR` (`setup.log`, `ocr_app.log`, `saved_words.json`).

## Project layout

```text
Chinese Screen OCR.bat   start here
app\                     the application (Python), dictionaries and the setup script (launcher.ps1)
app\models\              PaddleOCR's Chinese OCR models (included, so nothing is downloaded from China)
app\requirements.txt     exact library versions the setup installs
examples\                images for this README
```

## Credits

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) for Chinese OCR. Its PP-OCRv4 Chinese models (Apache 2.0) are included in `app/models`.
- CC-CEDICT dictionary data by MDBG and the CC-CEDICT contributors, under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- jieba and pypinyin for word segmentation and pinyin.
