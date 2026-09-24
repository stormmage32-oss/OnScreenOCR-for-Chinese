import sys
import logging
import numpy as np
from PyQt5.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QScrollArea, QApplication, QRubberBand)
from PyQt5.QtCore import Qt, QObject, QPoint, QRect, QSize, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QFont, QFontMetrics, QColor, QBrush, QPen, QImage, QPixmap, QPainter, QCursor

from dictionary import lookup_hsk, HSK_COLORS, get_pinyin, get_char_weight
from word_notebook import save_word
from ui_components import HoverTooltip, DetailPopup, _clamp_popup
from screens import scale_results

logger = logging.getLogger("OCRApp")

class _ScreenSelector(QWidget):
    """Dimmed selection layer covering exactly one monitor."""
    finished = pyqtSignal(object)  # logical global QRect, or None when cancelled

    def __init__(self, screen):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.screen_geometry = screen.geometry()
        self.setGeometry(self.screen_geometry)
        self.setCursor(Qt.CrossCursor)
        self.setWindowOpacity(0.35)
        self.setStyleSheet("background:#D4C5B0;")
        self.origin = QPoint()
        self.rubber = QRubberBand(QRubberBand.Rectangle, self)
        self.selecting = False

        self.lbl = QLabel("  Drag: Select region  |  Double click: Full screen  |  ESC: Cancel  ", self)
        self.lbl.setStyleSheet("color:#4A3F35;background:rgba(250,244,235,220);padding:8px 16px;"
                          "border-radius:6px;font-size:14px;font-weight:bold;")
        self.lbl.adjustSize(); self.lbl.move(20, 20)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape: self.finished.emit(None)

    def mouseDoubleClickEvent(self, e):
        self.finished.emit(QRect(self.screen_geometry))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.origin = e.pos()
            self.rubber.setGeometry(QRect(self.origin, QSize()))
            self.rubber.show(); self.selecting = True

    def _drag_rect(self, pos):
        return QRect(self.origin, pos).normalized().intersected(self.rect())

    def mouseMoveEvent(self, e):
        if self.selecting:
            rect = self._drag_rect(e.pos())
            self.rubber.setGeometry(rect)
            self.lbl.setText(f"  Drag: Select region  |  Size: {rect.width()} x {rect.height()} px  |  ESC: Cancel  ")
            self.lbl.adjustSize()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            rect = self._drag_rect(e.pos())
            self.rubber.hide()
            if rect.width() > 5 and rect.height() > 5:
                self.finished.emit(rect.translated(self.screen_geometry.topLeft()))
            else:
                self.finished.emit(None)


class RegionSelector(QObject):
    """Region picker with one layer per monitor.

    A single window spanning every monitor is mis-placed by Qt 5 once Windows
    display scaling is involved (each screen keeps its own scale factor), so
    each monitor gets its own layer, whose coordinates are always consistent.
    Emits logical global coordinates; screens.to_physical() converts them.
    """
    region_selected = pyqtSignal(int, int, int, int)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.windows = []
        for screen in QApplication.screens():
            w = _ScreenSelector(screen)
            w.finished.connect(self._finish)
            self.windows.append(w)

    def show(self):
        for w in self.windows:
            w.show()
        # Give keyboard focus (for ESC) to the layer under the mouse.
        for w in self.windows:
            if w.screen_geometry.contains(QCursor.pos()):
                w.activateWindow(); w.raise_()

    def close(self):
        for w in self.windows:
            w.close()

    def _finish(self, rect):
        self.close()
        if rect is None:
            self.cancelled.emit()
        else:
            self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())

class OCRCanvas(QLabel):
    def __init__(self, image: np.ndarray, results: list, scale: float = 1.0):
        """image/results are in physical pixels; scale = physical px per logical px."""
        super().__init__()
        self.results = scale_results(results, 1.0 / scale)
        self._scale = scale
        self.hovered_idx = -1
        self.setMouseTracking(True)
        self.drag_start = None
        self.drag_rect = QRect()
        self.is_dragging = False
        self._click_token = 0
        self._detail_popup = None
        h, w = image.shape[:2]
        self._img_bytes = image.tobytes()
        qimg = QImage(self._img_bytes, w, h, 3*w, QImage.Format_RGB888)
        self.base_px = QPixmap.fromImage(qimg)
        # Show the screenshot at its true on-screen size, still at full resolution.
        self.base_px.setDevicePixelRatio(scale)
        self.setFixedSize(round(w / scale), round(h / scale))
        
        self._hover_tooltip = HoverTooltip()
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(300)
        self._hover_timer.timeout.connect(self._show_hover_tooltip)
        self._hover_word_idx = -1
        self._repaint()

    def _repaint(self):
        pm = self.base_px.copy()
        pm.setDevicePixelRatio(self._scale)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        font = QFont("Microsoft YaHei", 9); p.setFont(font); fm = p.fontMetrics()
        for i, res in enumerate(self.results):
            b = res['bbox']; x, y, w, h = b['x'], b['y'], b['w'], b['h']
            hot = (i == self.hovered_idx)
            hsk_info = res.get('hsk')
            hsk_lvl = hsk_info['level'] if hsk_info else 0
            hsk_clr = QColor(HSK_COLORS.get(hsk_lvl, '#9B8B7A'))
            if hot:
                hsk_clr.setAlpha(120)
                p.setBrush(QBrush(hsk_clr)); p.setPen(QPen(QColor(HSK_COLORS.get(hsk_lvl, '#C08B5C')),2))
            else:
                hsk_clr.setAlpha(35)
                p.setBrush(QBrush(hsk_clr)); p.setPen(QPen(QColor(HSK_COLORS.get(hsk_lvl, '#D4C5B0')),1))
            p.drawRoundedRect(x, y, w, h, 4, 4)
            if hot:
                hsk_tag = f'HSK{hsk_lvl}' if hsk_lvl > 0 else ''
                txt = res['text'] + (f' [{hsk_tag}]' if hsk_tag else '')
                tw = fm.horizontalAdvance(txt)+12; th = fm.height()+8
                ly = y - th - 4
                if ly < 0: ly = y + h + 4
                lx = x
                if lx + tw > self.width(): lx = self.width() - tw - 4
                p.setBrush(QBrush(QColor(250, 244, 235, 230))); p.setPen(Qt.NoPen)
                p.drawRoundedRect(lx, ly, tw, th, 5, 5)
                p.setPen(QColor(74, 63, 53)); p.drawText(lx+6, ly+th-6, txt)
                
        if self.is_dragging and self.drag_rect.isValid():
            p.setBrush(QBrush(QColor(192, 139, 92, 60)))
            p.setPen(QPen(QColor(192, 139, 92, 180), 1))
            p.drawRect(self.drag_rect)
            
        p.end(); self.setPixmap(pm)

    def _show_hover_tooltip(self):
        idx = self._hover_word_idx
        if idx < 0 or idx >= len(self.results): return
        res = self.results[idx]
        b = res['bbox']
        gp = self.mapToGlobal(QPoint(b['x'] + b['w'] // 2, b['y']))
        self._hover_tooltip.show_for(res['text'], gp)

    def mouseMoveEvent(self, e):
        pos = e.pos()
        if self.is_dragging:
            self.drag_rect = QRect(self.drag_start, pos).normalized()
            self._repaint()
            self._hover_tooltip.dismiss()
            return
        ni = -1
        for i, res in enumerate(self.results):
            b = res['bbox']
            if QRect(b['x'],b['y'],b['w'],b['h']).contains(pos): ni = i; break
        self.setCursor(Qt.PointingHandCursor if ni != -1 else Qt.ArrowCursor)
        if ni != self.hovered_idx:
            self.hovered_idx = ni
            self._repaint()
            self._hover_timer.stop()
            self._hover_tooltip.dismiss()
            if ni != -1:
                self._hover_word_idx = ni
                self._hover_timer.start()
            else:
                self._hover_word_idx = -1

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._click_token += 1
            self._hover_timer.stop()
            self._hover_tooltip.dismiss()
            self.drag_start = e.pos()
            self.is_dragging = True
            self.drag_rect = QRect()
            
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.drag_rect = QRect(self.drag_start, e.pos()).normalized()
            
            is_click = self.drag_rect.width() < 5 and self.drag_rect.height() < 5
            selected = []
            for res in self.results:
                b = res['bbox']
                rect = QRect(b['x'], b['y'], b['w'], b['h'])
                if is_click:
                    if rect.contains(e.pos()):
                        selected.append(res); break
                else:
                    if self.drag_rect.intersects(rect):
                        selected.append(res)
                        
            self.drag_rect = QRect()
            self._repaint()
            
            if selected:
                combo_res = self._combined_result(selected, translate_requested=not is_click)
                if is_click:
                    # Wait briefly so a double-click can replace this ordinary
                    # dictionary lookup with a DeepL translation request.
                    token = self._click_token
                    QTimer.singleShot(180, lambda: self._show_if_single_click(token, combo_res))
                else:
                    self._show_detail_popup(combo_res)

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self._click_token += 1  # cancels the first click's delayed popup
        self.is_dragging = False
        self.drag_rect = QRect()
        self._repaint()
        for res in self.results:
            b = res['bbox']
            if QRect(b['x'], b['y'], b['w'], b['h']).contains(e.pos()):
                self._show_detail_popup(self._combined_result([res], translate_requested=True))
                return

    def _combined_result(self, selected, translate_requested=False):
        combined_text = "".join(result['text'] for result in selected)
        min_x = min(result['bbox']['x'] for result in selected)
        min_y = min(result['bbox']['y'] for result in selected)
        max_r = max(result['bbox']['x'] + result['bbox']['w'] for result in selected)
        max_b = max(result['bbox']['y'] + result['bbox']['h'] for result in selected)
        return {
            'text': combined_text,
            'confidence': sum(result.get('confidence', 0) for result in selected) / len(selected),
            'bbox': {'x': min_x, 'y': min_y, 'w': max_r - min_x, 'h': max_b - min_y},
            'hsk': lookup_hsk(combined_text),
            'original_sentence': selected[0].get('original_sentence', combined_text) if len(selected) == 1 else combined_text,
            'words': [result['text'] for result in selected],
            'translate_requested': translate_requested,
        }

    def _show_if_single_click(self, token, result):
        if token == self._click_token:
            self._show_detail_popup(result)

    def _show_detail_popup(self, result):
        if self._detail_popup is not None and self._detail_popup.isVisible():
            self._detail_popup.close()
        popup = DetailPopup(result, self)
        self._detail_popup = popup
        popup.adjustSize()
        bbox = result['bbox']
        anchor = self.mapToGlobal(QPoint(bbox['x'] + bbox['w'] // 2, bbox['y']))
        px = anchor.x() - popup.width() // 2
        py = anchor.y() - popup.height() - 8
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        if py < screen.geometry().top() + 8:
            py = self.mapToGlobal(QPoint(bbox['x'], bbox['y'] + bbox['h'])).y() + 8
        popup.move(px, py)
        _clamp_popup(popup, self)
        popup.show()

    def leaveEvent(self, _):
        self._hover_timer.stop()
        self._hover_tooltip.dismiss()
        if self.hovered_idx != -1: self.hovered_idx = -1; self._repaint()

class OverlayWindow(QMainWindow):
    """OCR result window; seamless mode keeps controls hidden until the top edge is reached."""
    seamless_closed = pyqtSignal()

    def __init__(self, image: np.ndarray, results: list, main_win=None, screen_rect=None, seamless=False,
                 scale: float = 1.0):
        super().__init__()
        self._scale = scale
        self.main_win = main_win
        self.screen_rect = screen_rect
        self.seamless = seamless
        self.setWindowTitle(f"OCR Results  {len(results)} texts")
        flags = Qt.WindowStaysOnTopHint
        if seamless:
            flags |= Qt.FramelessWindowHint | Qt.Tool | Qt.CustomizeWindowHint
        else:
            flags |= Qt.Window
        self.setWindowFlags(flags)
        self.setStyleSheet("QMainWindow{background:#FAF4EB;}")
        h, w = image.shape[:2]
        if screen_rect:
            self.setGeometry(screen_rect)
        else:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            avail = screen.availableGeometry()
            self.resize(min(round(w / scale) + 40, avail.width() - 40),
                        min(round(h / scale) + 80, avail.height() - 40))
        self._build(image, results)
        if self.seamless:
            self.setMouseTracking(True)
            self._set_controls_visible(False)
            self.setAttribute(Qt.WA_DeleteOnClose, True)

    def _build(self, image, results):
        cw = QWidget(); self.setCentralWidget(cw)
        vb = QVBoxLayout(cw); vb.setContentsMargins(0,0,0,0); vb.setSpacing(0)
        bar = QFrame(); bar.setFixedHeight(46)
        self.control_bar = bar
        bar.setStyleSheet("background:#F4EFE6;border-bottom:1px solid #D4C5B0;")
        bl = QHBoxLayout(bar); bl.setContentsMargins(14,0,14,0)
        info = QLabel(f"  {len(results)} texts found (PaddleOCR)   Click on boxes")
        info.setStyleSheet("color:#4A3F35;font-size:12px;"); bl.addWidget(info); bl.addStretch()
        
        ca = QPushButton("Copy All")
        ca.setStyleSheet(self._bs("#EADCC9", fg="#4A3F35", border="1px solid #C4B29B"))
        ca.clicked.connect(lambda: QApplication.clipboard().setText('\n'.join(r['text'] for r in results)))
        bl.addWidget(ca)
        
        sa = QPushButton("Save All")
        sa.setStyleSheet(self._bs("#6B8E4E", fg="#FFF8F0", bold=True))
        def save_all():
            for r in results: save_word(r['text'], get_pinyin(r['text']))
            sa.setText("Saved ✓"); sa.setEnabled(False)
        sa.clicked.connect(save_all)
        bl.addWidget(sa)
        
        ns = QPushButton("New Scan")
        ns.setStyleSheet(self._bs("#C08B5C", fg="#FFF8F0", bold=True))
        ns.clicked.connect(self._yeni_tarama); bl.addWidget(ns)
        
        vb.addWidget(bar)
        sc = QScrollArea(); sc.setStyleSheet("background:#FAF4EB;border:none;"); sc.setWidgetResizable(True)
        if self.seamless:
            sc.setFrameShape(QFrame.NoFrame)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget(); inner.setStyleSheet("background:#FAF4EB;")
        il = QVBoxLayout(inner); il.setAlignment(Qt.AlignCenter)
        if self.seamless:
            il.setContentsMargins(0, 0, 0, 0)
        else:
            il.setContentsMargins(20, 20, 20, 20)
        self.canvas = OCRCanvas(image, results, self._scale); il.addWidget(self.canvas)
        sc.setWidget(inner); vb.addWidget(sc)
        if self.seamless:
            # The canvas consumes mouse moves, so observe it as well as the window.
            self.canvas.installEventFilter(self)
            sc.viewport().installEventFilter(self)

    def _set_controls_visible(self, visible):
        self.control_bar.setVisible(visible)
        self.control_bar.setFixedHeight(46 if visible else 0)

    def eventFilter(self, watched, event):
        if self.seamless and event.type() == QEvent.MouseMove:
            global_pos = watched.mapToGlobal(event.pos())
            self._set_controls_visible(global_pos.y() <= self.frameGeometry().top() + 58)
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event):
        if self.seamless:
            self._set_controls_visible(event.globalPos().y() <= self.frameGeometry().top() + 58)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if self.seamless and event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.seamless:
            self.seamless_closed.emit()
        super().closeEvent(event)

    def _yeni_tarama(self):
        self.close()
        if self.main_win:
            self.main_win.show(); self.main_win.raise_()

    @staticmethod
    def _bs(bg, fg="#4A3F35", border=None, bold=False):
        bw = "font-weight:bold;" if bold else ""
        border_style = f"border:{border};" if border else "border:none;"
        return (f"QPushButton{{background:{bg};color:{fg};{border_style}border-radius:7px;"
                f"padding:5px 14px;font-size:12px;{bw}}}"
                f"QPushButton:hover{{background:{bg}ee;}}"
                f"QPushButton:disabled{{background:#E8DCCC;color:#B0A090;border:none;}}")

class PinyinOverlayWindow(QWidget):
    def __init__(self, results: list, screen_rect: QRect, image=None, parent=None):
        super().__init__(parent)
        self.screen_rect = screen_rect
        self._set_data(results, image)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(screen_rect)

    def _set_data(self, results, image):
        # OCR runs on physical pixels; this window is laid out in logical ones.
        self.image = image
        self._scale = image.shape[1] / max(1, self.screen_rect.width()) if image is not None else 1.0
        self.results = scale_results(results, 1.0 / self._scale)

    @staticmethod
    def _cjk_text(text: str) -> str:
        return ''.join(ch for ch in text if '\u3400' <= ch <= '\u9fff')

    @staticmethod
    def _is_cjk(ch: str) -> bool:
        return '\u3400' <= ch <= '\u9fff'

    @staticmethod
    def _char_pinyin(chars: str) -> list:
        try:
            from pypinyin import pinyin, Style
            return [item[0] for item in pinyin(chars, style=Style.TONE)]
        except Exception:
            joined = get_pinyin(chars)
            return joined.split() if joined else []

    def _font_for(self, py: str, box_w: int, box_h: int):
        target_w = max(3, box_w - 1)
        base_size = max(5, min(10, int(box_h * 0.38)))
        for size in range(base_size, 3, -1):
            for stretch in (100, 90, 80, 70, 60, 50):
                font = QFont("Segoe UI", size, QFont.Normal)
                font.setStretch(stretch)
                font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
                fm = QFontMetrics(font)
                if fm.horizontalAdvance(py) <= target_w:
                    return font, fm
        font = QFont("Segoe UI", 4, QFont.Normal)
        font.setStretch(45)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
        return font, QFontMetrics(font)

    def _label_y(self, y: int, h: int, th: int, margin: int, measured=False) -> int:
        # A measured y is the top of the ink, so sit right on it; a detector box
        # has padding above the glyphs, so overlap it slightly.
        ly = y - th + (0 if measured else 2)
        if ly < margin:
            ly = y + 1
        return max(margin, min(ly, self.height() - th - margin))

    def _adaptive_colors(self, rect: QRect):
        if self.image is None:
            return QColor(235, 45, 35, 245), QColor(255, 248, 230, 235)

        h, w = self.image.shape[:2]
        s = self._scale
        rect = QRect(int(rect.left() * s), int(rect.top() * s),
                     max(1, int(rect.width() * s)), max(1, int(rect.height() * s)))
        x1 = max(0, min(rect.left(), w - 1))
        y1 = max(0, min(rect.top(), h - 1))
        x2 = max(x1 + 1, min(rect.right() + 1, w))
        y2 = max(y1 + 1, min(rect.bottom() + 1, h))
        patch = self.image[y1:y2, x1:x2]
        if patch.size == 0:
            return QColor(235, 45, 35, 245), QColor(255, 248, 230, 235)

        lum = float((0.2126 * patch[:, :, 0] + 0.7152 * patch[:, :, 1] + 0.0722 * patch[:, :, 2]).mean())
        if lum < 95:
            return QColor(255, 225, 40, 250), QColor(0, 0, 0, 235)
        if lum < 165:
            return QColor(0, 235, 255, 250), QColor(0, 0, 0, 230)
        return QColor(235, 35, 30, 250), QColor(255, 250, 225, 240)

    def _iter_char_labels(self, res):
        if res.get("chars"):
            # Measured glyph positions from the OCR engine (see _add_glyph_geometry).
            return [{"pinyin": py, "x": c["x"], "y": res["text_top"], "w": c["w"], "h": res["text_h"],
                     "measured": True}
                    for c, py in zip(res["chars"], self._char_pinyin("".join(c["ch"] for c in res["chars"])))]
        text = res.get("text", "").strip()
        cjk = self._cjk_text(text)
        if not cjk:
            return []
        syllables = self._char_pinyin(cjk)
        if not syllables:
            return []

        b = res["bbox"]
        total_weight = sum(get_char_weight(ch) for ch in text) or len(text) or 1
        cursor = float(b["x"])
        cjk_index = 0
        labels = []

        for ch in text:
            weight = get_char_weight(ch)
            char_w = max(1.0, b["w"] * (weight / total_weight))
            if self._is_cjk(ch) and cjk_index < len(syllables):
                labels.append({
                    "pinyin": syllables[cjk_index],
                    "x": int(round(cursor)),
                    "y": b["y"],
                    "w": int(round(char_w)),
                    "h": b["h"],
                })
                cjk_index += 1
            cursor += char_w

        return labels

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        margin = 4

        for res in sorted(self.results, key=lambda item: (item["bbox"]["y"], item["bbox"]["x"])):
            for label in self._iter_char_labels(res):
                py = label["pinyin"]
                x, y, w, h = label["x"], label["y"], label["w"], label["h"]
                font, fm = self._font_for(py, w, h)
                p.setFont(font)
                th = fm.height() + 1
                lx = max(margin, min(x, self.width() - max(w, 1) - margin))
                ly = self._label_y(y, h, th, margin, label.get("measured", False))
                rect = QRect(lx, ly, max(1, w), th)

                text_rect = rect.adjusted(1, 0, -1, 0)
                fill, outline = self._adaptive_colors(rect)
                p.save()
                p.setClipRect(rect)
                p.setPen(outline)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    p.drawText(text_rect.translated(dx, dy), Qt.AlignCenter, py)
                p.setPen(fill)
                p.drawText(text_rect, Qt.AlignCenter, py)
                p.restore()

        p.end()


class LivePinyinOverlayWindow(PinyinOverlayWindow):
    """Click-through pinyin layer refreshed continuously by LiveScanWorker.

    It never takes focus or input, so the game underneath keeps working, and it
    is excluded from screen capture so the scanner never reads its own labels.
    """
    WDA_EXCLUDEFROMCAPTURE = 0x11

    def __init__(self, screen_rect: QRect):
        super().__init__([], screen_rect)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(2000)
        self._topmost_timer.timeout.connect(self._keep_on_top)
        self._exclude_from_capture()

    def set_results(self, results, image):
        self._set_data(results, image)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._topmost_timer.start()

    def hideEvent(self, event):
        self._topmost_timer.stop()
        super().hideEvent(event)

    def _exclude_from_capture(self):
        if sys.platform != 'win32':
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32')
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        GWL_EXSTYLE, WS_EX_LAYERED = -20, 0x80000
        hwnd = int(self.winId())  # creates the native window while it is still hidden
        # Windows refuses display affinity on layered (translucent) windows, so drop
        # the layered style for the call and restore it; the setting sticks.
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_LAYERED)
        ok = user32.SetWindowDisplayAffinity(hwnd, self.WDA_EXCLUDEFROMCAPTURE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        if not ok:
            logger.warning("[LIVE] Could not exclude overlay from capture (needs Windows 10 2004+).")

    def _keep_on_top(self):
        # Borderless games often push themselves to the top; re-assert without stealing focus.
        if sys.platform != 'win32':
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32')
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        HWND_TOPMOST = -1
        SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_NOOWNERZORDER = 0x1, 0x2, 0x10, 0x200
        user32.SetWindowPos(int(self.winId()), HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER)
