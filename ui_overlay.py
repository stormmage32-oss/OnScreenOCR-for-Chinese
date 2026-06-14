import numpy as np
from PyQt5.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QScrollArea, QApplication, QRubberBand)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QPen, QImage, QPixmap, QPainter

from dictionary import lookup_hsk, HSK_COLORS, get_pinyin
from word_notebook import save_word
from ui_components import HoverTooltip, DetailPopup, _clamp_popup

class RegionSelector(QWidget):
    region_selected = pyqtSignal(int, int, int, int)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.BypassWindowManagerHint | Qt.Tool)
        virtual_rect = QRect()
        for screen in QApplication.screens():
            virtual_rect = virtual_rect.united(screen.geometry())
        self.setGeometry(virtual_rect)
        
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
        if e.key() == Qt.Key_Escape: self.close(); self.cancelled.emit()

    def mouseDoubleClickEvent(self, e):
        screen = QApplication.screenAt(e.globalPos()) or QApplication.primaryScreen()
        s = screen.geometry()
        self.close()
        self.region_selected.emit(s.x(), s.y(), s.width(), s.height())

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.origin = e.pos()
            self.rubber.setGeometry(QRect(self.origin, QSize()))
            self.rubber.show(); self.selecting = True

    def mouseMoveEvent(self, e):
        if self.selecting:
            rect = QRect(self.origin, e.pos()).normalized()
            self.rubber.setGeometry(rect)
            self.lbl.setText(f"  Drag: Select region  |  Size: {rect.width()} x {rect.height()} px  |  ESC: Cancel  ")
            self.lbl.adjustSize()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            rect = QRect(self.origin, e.pos()).normalized()
            self.rubber.hide(); self.close()
            if rect.width() > 5 and rect.height() > 5:
                gx = self.geometry().x() + rect.x()
                gy = self.geometry().y() + rect.y()
                self.region_selected.emit(gx, gy, rect.width(), rect.height())
            else:
                self.cancelled.emit()

class OCRCanvas(QLabel):
    def __init__(self, image: np.ndarray, results: list):
        super().__init__()
        self.results = results
        self.hovered_idx = -1
        self.setMouseTracking(True)
        self.drag_start = None
        self.drag_rect = QRect()
        self.is_dragging = False
        h, w = image.shape[:2]
        self._img_bytes = image.tobytes()
        qimg = QImage(self._img_bytes, w, h, 3*w, QImage.Format_RGB888)
        self.base_px = QPixmap.fromImage(qimg)
        self.setFixedSize(w, h)
        
        self._hover_tooltip = HoverTooltip()
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(300)
        self._hover_timer.timeout.connect(self._show_hover_tooltip)
        self._hover_word_idx = -1
        self._repaint()

    def _repaint(self):
        pm = self.base_px.copy()
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
                combined_text = "".join(r['text'] for r in selected)
                combined_orig = "".join(r.get('original_sentence', r['text']) for r in selected)
                combined_hsk = lookup_hsk(combined_text)
                avg_conf = sum(r.get('confidence', 0) for r in selected) / len(selected)
                
                min_x = min(r['bbox']['x'] for r in selected)
                min_y = min(r['bbox']['y'] for r in selected)
                max_r = max(r['bbox']['x'] + r['bbox']['w'] for r in selected)
                max_b = max(r['bbox']['y'] + r['bbox']['h'] for r in selected)
                c_bbox = {'x': min_x, 'y': min_y, 'w': max_r - min_x, 'h': max_b - min_y}
                
                combo_res = {
                    'text': combined_text,
                    'confidence': avg_conf,
                    'bbox': c_bbox,
                    'hsk': combined_hsk,
                    'original_sentence': combined_orig,
                    'words': [r['text'] for r in selected]
                }
                
                popup = DetailPopup(combo_res, self)
                popup.adjustSize()
                anchor = self.mapToGlobal(QPoint(c_bbox['x'] + c_bbox['w'] // 2, c_bbox['y']))
                px = anchor.x() - popup.width() // 2
                py = anchor.y() - popup.height() - 8
                screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
                screen_rect = screen.geometry()
                if py < screen_rect.top() + 8:
                    py = self.mapToGlobal(QPoint(c_bbox['x'], c_bbox['y'] + c_bbox['h'])).y() + 8
                popup.move(px, py)
                _clamp_popup(popup, self)
                popup.show()

    def leaveEvent(self, _):
        self._hover_timer.stop()
        self._hover_tooltip.dismiss()
        if self.hovered_idx != -1: self.hovered_idx = -1; self._repaint()

class OverlayWindow(QMainWindow):
    def __init__(self, image: np.ndarray, results: list, main_win=None):
        super().__init__()
        self.main_win = main_win
        self.setWindowTitle(f"OCR Results  {len(results)} texts")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("QMainWindow{background:#FAF4EB;}")
        h, w = image.shape[:2]
        self.resize(min(w+40,1440), min(h+80,960))
        self._build(image, results)

    def _build(self, image, results):
        cw = QWidget(); self.setCentralWidget(cw)
        vb = QVBoxLayout(cw); vb.setContentsMargins(0,0,0,0); vb.setSpacing(0)
        bar = QFrame(); bar.setFixedHeight(46)
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
        inner = QWidget(); inner.setStyleSheet("background:#FAF4EB;")
        il = QVBoxLayout(inner); il.setAlignment(Qt.AlignCenter); il.setContentsMargins(20,20,20,20)
        self.canvas = OCRCanvas(image, results); il.addWidget(self.canvas)
        sc.setWidget(inner); vb.addWidget(sc)

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
