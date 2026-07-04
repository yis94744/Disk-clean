"""Safe Treemap - bulletproof rendering"""
from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from utils.helpers import format_size
import traceback

MAX_VISIBLE = 200

class TreemapWidget(QWidget):
    node_clicked = Signal(object)
    node_right_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self._root = None
        self._crumbs = []
        self._rects = []
        self._dirty = True
        self._error = None
        self.setStyleSheet("background: transparent;")

    def set_data(self, root):
        """Set root data - safe wrapper"""
        try:
            self._root = root
            self._crumbs = [root]
            self._dirty = True
            self._error = None
            self._safe_layout()
            self.update()
        except Exception as e:
            self._error = str(e)
            traceback.print_exc()
            self._rects = []
            self.update()

    def drill_down(self, node):
        try:
            if node and node.is_dir and node.children:
                self._crumbs.append(node)
                self._dirty = True
                self._safe_layout()
                self.update()
        except Exception as e:
            self._error = str(e)

    def go_up(self):
        try:
            if len(self._crumbs) > 1:
                self._crumbs.pop()
                self._dirty = True
                self._safe_layout()
                self.update()
        except Exception as e:
            self._error = str(e)

    def _safe_layout(self):
        """Layout wrapper with full error protection"""
        try:
            self._do_layout()
        except Exception as e:
            self._error = str(e)
            self._rects = []

    def _do_layout(self):
        self._rects = []
        if not self._crumbs:
            return
        current = self._crumbs[-1]
        if not current:
            return
        children = getattr(current, 'children', None)
        if children is None:
            return
        if len(children) == 0:
            # Empty directory - show as single empty rect
            self._rects = [(QRectF(2, 2, float(self.width()-4), float(self.height()-4)), current)]
            return

        items = []
        for c in children:
            sz = getattr(c, 'size', 0)
            if sz > 0:
                items.append(c)

        if not items:
            return

        w = self.width() - 4
        h = self.height() - 4
        if w <= 10 or h <= 10:
            return

        total = sum(getattr(i, 'size', 0) for i in items)
        if total <= 0:
            return

        # Limit items
        if len(items) > MAX_VISIBLE:
            items.sort(key=lambda x: getattr(x, 'size', 0), reverse=True)
            top = items[:MAX_VISIBLE - 1]
            rest = items[MAX_VISIBLE - 1:]
            rest_sz = sum(getattr(i, 'size', 0) for i in rest)
            from core.scanner import ScanNode
            rest_node = ScanNode(current.path, "... more", rest_sz)
            rest_node.is_dir = False
            items = top + [rest_node]

        try:
            self._squarify(QRectF(2, 2, float(w), float(h)), items, float(total))
        except Exception:
            self._rects = []

    def _squarify(self, rect, items, total, depth=0):
        if depth > 100:
            return
        if not items or total <= 0:
            return
        sorted_items = sorted(items, key=lambda x: getattr(x, 'size', 0), reverse=True)
        self._layout_row(rect, sorted_items, total, depth + 1)

    def _layout_row(self, rect, items, total, depth):
        if depth > 100 or not items or total <= 0:
            return

        x = rect.x(); y = rect.y(); w = rect.width(); h = rect.height()
        if w <= 2 or h <= 2:
            return

        is_horizontal = w >= h
        row = [items[0]]
        row_sum = getattr(items[0], 'size', 0)

        for i in range(1, min(len(items), 50)):
            item = items[i]
            item_sz = getattr(item, 'size', 0)
            if item_sz <= 0:
                continue
            test_sum = row_sum + item_sz
            if test_sum <= 0:
                break
            if is_horizontal:
                rw = w * (test_sum / total)
                item_w = rw * (item_sz / test_sum) if test_sum > 0 else 0
                asp = max(item_w / max(h, 0.1), max(h, 0.1) / item_w) if item_w > 0 else 1e9
            else:
                rh = h * (test_sum / total)
                item_h = rh * (item_sz / test_sum) if test_sum > 0 else 0
                asp = max(w / max(item_h, 0.1), max(item_h, 0.1) / w) if item_h > 0 else 1e9

            row_best = 1e9
            for ri in row:
                risz = getattr(ri, 'size', 0)
                if risz <= 0:
                    continue
                if is_horizontal:
                    rw2 = w * (row_sum / total) if total > 0 else 0
                    riw = rw2 * (risz / row_sum) if row_sum > 0 else 0
                    ri_asp = max(riw / max(h, 0.1), max(h, 0.1) / riw) if riw > 0 else 1e9
                else:
                    rh2 = h * (row_sum / total) if total > 0 else 0
                    rih = rh2 * (risz / row_sum) if row_sum > 0 else 0
                    ri_asp = max(w / max(rih, 0.1), max(rih, 0.1) / w) if rih > 0 else 1e9
                row_best = min(row_best, ri_asp)

            if asp <= row_best or len(row) >= 20:
                row.append(item)
                row_sum = test_sum
            else:
                break

        remaining = items[len(row):]
        remaining_sum = sum(getattr(i, 'size', 0) for i in remaining)

        if is_horizontal:
            rw = w * (row_sum / total) if total > 0 else 0
            if rw > 0:
                self._fill_row(QRectF(x, y, rw, h), row, row_sum, is_horizontal)
            if remaining and remaining_sum > 0 and (w - rw) > 2:
                self._layout_row(QRectF(x + rw, y, w - rw, h), remaining, remaining_sum, depth + 1)
        else:
            rh = h * (row_sum / total) if total > 0 else 0
            if rh > 0:
                self._fill_row(QRectF(x, y, w, rh), row, row_sum, is_horizontal)
            if remaining and remaining_sum > 0 and (h - rh) > 2:
                self._layout_row(QRectF(x, y + rh, w, h - rh), remaining, remaining_sum, depth + 1)

    def _fill_row(self, rect, items, total, is_h):
        x = rect.x(); y = rect.y(); w = rect.width(); h = rect.height()
        if total <= 0 or w <= 0 or h <= 0:
            return
        for item in items:
            item_sz = getattr(item, 'size', 0)
            if item_sz <= 0:
                continue
            if is_h:
                iw = w * (item_sz / total)
                if iw >= 1:
                    self._rects.append((QRectF(x, y, iw, h), item))
                    x += iw
            else:
                ih = h * (item_sz / total)
                if ih >= 1:
                    self._rects.append((QRectF(x, y, w, ih), item))
                    y += ih

    def paintEvent(self, ev):
        try:
            self._do_paint(ev)
        except Exception:
            pass

    def _do_paint(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0f0f23"))

        if self._error:
            p.setPen(QPen(QColor("#F44336")))
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(self.rect(), Qt.AlignCenter, "Render error: " + self._error[:100])
            p.end()
            return

        if not self._root:
            p.setPen(QPen(QColor("#888")))
            p.setFont(QFont("Microsoft YaHei", 12))
            p.drawText(self.rect(), Qt.AlignCenter, "Scan a drive to see treemap")
            p.end()
            return

        if self._dirty:
            self._safe_layout()

        if not self._rects:
            p.setPen(QPen(QColor("#888")))
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(self.rect(), Qt.AlignCenter, "No data to display")
            p.end()
            return

        colors = [
            QColor("#1b5e20"), QColor("#0d47a1"), QColor("#e65100"),
            QColor("#4a148c"), QColor("#004d40"), QColor("#880e4f"),
            QColor("#1a237e"), QColor("#006064"), QColor("#bf360c"),
        ]
        for i, (r, node) in enumerate(self._rects[:MAX_VISIBLE]):
            try:
                c = colors[i % len(colors)]
                p.fillRect(r, c)
                p.setPen(QPen(QColor("#ffffff22"), 1))
                p.drawRect(r)
                if r.width() > 30 and r.height() > 18:
                    p.setPen(QPen(Qt.white))
                    p.setFont(QFont("Microsoft YaHei", 8))
                    nm = getattr(node, 'name', '?') or '?'
                    max_chars = int(r.width() // 7) if r.width() > 60 else 8
                    nm = nm[:max_chars]
                    tr = QRectF(r.x() + 3, r.y() + 3, r.width() - 6, r.height() - 6)
                    p.drawText(tr, Qt.TextWordWrap, nm)
            except Exception:
                continue
        p.end()

    def mousePressEvent(self, ev):
        try:
            pos = ev.position()
            for r, node in self._rects:
                if r.contains(pos):
                    if ev.button() == Qt.LeftButton and getattr(node, 'is_dir', False) and getattr(node, 'children', None):
                        self.drill_down(node)
                    elif ev.button() == Qt.RightButton:
                        self.go_up()
                    return
        except Exception:
            pass
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        try:
            pos = ev.position()
            for r, node in self._rects:
                if r.contains(pos):
                    nm = getattr(node, 'name', '?') or '?'
                    sz = format_size(getattr(node, 'size', 0))
                    fc = getattr(node, 'file_count', 0)
                    tip = nm + "\n" + sz + ", " + str(fc) + " files"
                    QToolTip.showText(ev.globalPosition().toPoint(), tip)
                    return
        except Exception:
            pass
