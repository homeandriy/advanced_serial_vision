from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QWidget


class PhotoPreview(QGraphicsView):
    """Keep one source pixmap while the operator pans and zooms its viewport."""

    def __init__(self, empty_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.empty_text = empty_text
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._photo: QGraphicsPixmapItem | None = None
        self._fit = True
        self.setObjectName("imagePreview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def set_image(self, path: Path | None) -> bool:
        self._scene.clear()
        self._photo = None
        self.resetTransform()
        self._fit = True
        if path is None:
            self.viewport().update()
            return True
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.viewport().update()
            return False
        self._photo = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._photo.boundingRect())
        self.zoom_to_fit()
        return True

    def zoom_to_fit(self) -> None:
        if self._photo is None:
            return
        self._fit = True
        self.resetTransform()
        self.fitInView(self._photo, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_actual(self) -> None:
        if self._photo is None:
            return
        self._fit = False
        self.resetTransform()
        self.centerOn(self._photo)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._fit and self._photo is not None:
            self.zoom_to_fit()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._photo is None or not event.angleDelta().y():
            super().wheelEvent(event)
            return
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        next_scale = self.transform().m11() * factor
        if 0.05 <= next_scale <= 8:
            self._fit = False
            self.scale(factor, factor)
        event.accept()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._photo is None:
            painter = QPainter(self.viewport())
            painter.setPen(self.palette().text().color())
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, self.empty_text)
