from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QCloseEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGraphicsItem, QGraphicsRectItem,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QSlider,
    QSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.i18n import t
from serial_vision.image_editing import ImageEditSession
from serial_vision.ui.buttons import button
from serial_vision.ui.photo_preview import PhotoPreview


class CropPreview(PhotoPreview):
    selection_changed = Signal(QRectF)
    rotation_previewed = Signal(int)
    rotation_requested = Signal(int)
    _HANDLE_NAMES = ("nw", "ne", "sw", "se", "n", "s", "w", "e")
    _CURSORS = {
        "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
        "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
        "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
        "w": Qt.CursorShape.SizeHorCursor, "e": Qt.CursorShape.SizeHorCursor,
        "move": Qt.CursorShape.SizeAllCursor,
    }

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("imageEditorPreview")
        self.setDragMode(self.DragMode.NoDrag)
        self.setMouseTracking(True)
        self._selection: QGraphicsRectItem | None = None
        self._handles: dict[str, QGraphicsRectItem] = {}
        self._selection_enabled = True
        self._drag_mode: str | None = None
        self._drag_start = QPointF()
        self._drag_rect = QRectF()
        self._rotating = False
        self._rotation_angle = 0

    def set_selection_enabled(self, enabled: bool) -> None:
        self._selection_enabled = enabled
        if not enabled:
            self._drag_mode = None
            self._rotating = False
            self.viewport().unsetCursor()

    def set_preview(self, data: bytes) -> bool:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data, "PNG"):
            return False
        self._scene.clear()
        self._selection = None
        self._handles.clear()
        self._drag_mode = None
        self._rotating = False
        self._rotation_angle = 0
        self._photo = self._scene.addPixmap(pixmap)
        self._photo.setTransformOriginPoint(self._photo.boundingRect().center())
        self._scene.setSceneRect(self._photo.boundingRect().adjusted(-24, -48, 24, 24))
        self.zoom_to_fit()
        return True

    def zoom_to_fit(self) -> None:
        if self._photo is None:
            return
        self._fit = True
        self.resetTransform()
        self.fitInView(self._photo.sceneBoundingRect().adjusted(-24, -48, 24, 24), Qt.AspectRatioMode.KeepAspectRatio)

    def _rotation_handle_position(self) -> QPoint:
        bounds = self._photo.sceneBoundingRect()
        top = self.mapFromScene(QPointF(bounds.center().x(), bounds.top()))
        return QPoint(top.x(), top.y() - 26)

    def _rotation_handle_at(self, position: QPoint) -> bool:
        handle = self._rotation_handle_position()
        return (position.x() - handle.x()) ** 2 + (position.y() - handle.y()) ** 2 <= 12 ** 2

    def _preview_rotation(self, point: QPointF) -> None:
        center = self._photo.mapToScene(self._photo.boundingRect().center())
        degrees = round(math.degrees(math.atan2(point.y() - center.y(), point.x() - center.x())) + 90)
        self._rotation_angle = (degrees + 180) % 360 - 180
        self._photo.setRotation(self._rotation_angle)
        self._scene.setSceneRect(self._photo.sceneBoundingRect().adjusted(-24, -48, 24, 24))
        if self._fit:
            self.zoom_to_fit()
        self.rotation_previewed.emit(self._rotation_angle)
        self.viewport().update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._photo is None:
            return
        handle = self._rotation_handle_position()
        bounds = self._photo.sceneBoundingRect()
        top = self.mapFromScene(QPointF(bounds.center().x(), bounds.top()))
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().highlight().color()
        pen = QPen(color, 2)
        painter.setPen(pen)
        painter.drawLine(top, handle)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(handle, 8, 8)
        painter.end()

    def clear_selection(self) -> None:
        for handle in self._handles.values():
            self._scene.removeItem(handle)
        self._handles.clear()
        if self._selection is not None:
            self._scene.removeItem(self._selection)
            self._selection = None
        self.viewport().unsetCursor()

    def set_selection(self, rectangle: QRectF) -> None:
        if rectangle.width() < 2 or rectangle.height() < 2:
            self.clear_selection()
            return
        if self._selection is None:
            color = self.palette().highlight().color()
            fill = color.lighter(150)
            fill.setAlpha(45)
            pen = QPen(color, 2)
            pen.setCosmetic(True)
            self._selection = self._scene.addRect(rectangle, pen, QBrush(fill))
            self._selection.setZValue(1)
            for name in self._HANDLE_NAMES:
                handle = self._scene.addRect(QRectF(-5, -5, 10, 10), QPen(self.palette().base().color()), QBrush(color))
                handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                handle.setZValue(2)
                self._handles[name] = handle
        else:
            self._selection.setRect(rectangle)
        self._position_handles(rectangle)

    def _position_handles(self, rectangle: QRectF) -> None:
        x, middle_x, right = rectangle.left(), rectangle.center().x(), rectangle.right()
        y, middle_y, bottom = rectangle.top(), rectangle.center().y(), rectangle.bottom()
        for name, point in {
            "nw": (x, y), "ne": (right, y), "sw": (x, bottom), "se": (right, bottom),
            "n": (middle_x, y), "s": (middle_x, bottom),
            "w": (x, middle_y), "e": (right, middle_y),
        }.items():
            self._handles[name].setPos(*point)

    def _handle_at(self, position: QPoint) -> str | None:
        for name in self._HANDLE_NAMES:
            center = self.mapFromScene(self._handles[name].pos()) if name in self._handles else None
            if center is not None and abs(position.x() - center.x()) <= 8 and abs(position.y() - center.y()) <= 8:
                return name
        return None

    def _bounded(self, point: QPointF) -> QPointF:
        bounds = self._photo.boundingRect()
        return QPointF(max(bounds.left(), min(point.x(), bounds.right())), max(bounds.top(), min(point.y(), bounds.bottom())))

    def _dragged_rectangle(self, point: QPointF) -> QRectF:
        point = self._bounded(point)
        if self._drag_mode == "new":
            return QRectF(self._drag_start, point).normalized()
        rectangle = self._drag_rect
        bounds = self._photo.boundingRect()
        if self._drag_mode == "move":
            dx = max(bounds.left() - rectangle.left(), min(point.x() - self._drag_start.x(), bounds.right() - rectangle.right()))
            dy = max(bounds.top() - rectangle.top(), min(point.y() - self._drag_start.y(), bounds.bottom() - rectangle.bottom()))
            return rectangle.translated(dx, dy)
        left, top, right, bottom = rectangle.left(), rectangle.top(), rectangle.right(), rectangle.bottom()
        if self._drag_mode and "w" in self._drag_mode:
            left = max(bounds.left(), min(point.x(), right - 2))
        if self._drag_mode and "e" in self._drag_mode:
            right = min(bounds.right(), max(point.x(), left + 2))
        if self._drag_mode and "n" in self._drag_mode:
            top = max(bounds.top(), min(point.y(), bottom - 2))
        if self._drag_mode and "s" in self._drag_mode:
            bottom = min(bounds.bottom(), max(point.y(), top + 2))
        return QRectF(QPointF(left, top), QPointF(right, bottom))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._selection_enabled and event.button() == Qt.MouseButton.LeftButton and self._photo is not None:
            if self._rotation_handle_at(event.position().toPoint()):
                self._rotating = True
                self.clear_selection()
                event.accept()
                return
            point = self.mapToScene(event.position().toPoint())
            handle = self._handle_at(event.position().toPoint())
            if handle or (self._selection is not None and self._selection.rect().contains(point)):
                self._drag_mode = handle or "move"
                self._drag_start = self._bounded(point)
                self._drag_rect = QRectF(self._selection.rect())
                event.accept()
                return
            if self._photo.boundingRect().contains(point):
                self._drag_mode = "new"
                self._drag_start = self._bounded(point)
                self.clear_selection()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._rotating:
            self._preview_rotation(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._drag_mode is not None:
            rectangle = self._dragged_rectangle(self.mapToScene(event.position().toPoint()))
            if rectangle.width() >= 2 and rectangle.height() >= 2:
                self.set_selection(rectangle)
                self.selection_changed.emit(rectangle)
            event.accept()
            return
        if self._selection_enabled and self._photo is not None:
            position = event.position().toPoint()
            if self._rotation_handle_at(position):
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                event.accept()
                return
            mode = self._handle_at(position)
            if mode is None and self._selection is not None and self._selection.rect().contains(self.mapToScene(position)):
                mode = "move"
            if mode is None:
                self.viewport().unsetCursor()
            else:
                self.viewport().setCursor(self._CURSORS[mode])
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._rotating and event.button() == Qt.MouseButton.LeftButton:
            self._preview_rotation(self.mapToScene(event.position().toPoint()))
            self._rotating = False
            self.rotation_requested.emit(self._rotation_angle)
            event.accept()
            return
        if self._drag_mode is not None and event.button() == Qt.MouseButton.LeftButton:
            rectangle = self._dragged_rectangle(self.mapToScene(event.position().toPoint()))
            self._drag_mode = None
            if rectangle.width() >= 2 and rectangle.height() >= 2:
                self.set_selection(rectangle)
                self.selection_changed.emit(rectangle)
            else:
                self.clear_selection()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ImageEditorDialog(QDialog):
    """Edit a private photo copy and recognize its temporary snapshot."""

    def __init__(
        self,
        service: SerialVisionService,
        source: Path,
        locale: str,
        language: str,
        local_worker_type: type[Any],
        ai_worker_type: type[Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.locale = locale
        self.language = language
        self.local_worker_type = local_worker_type
        self.ai_worker_type = ai_worker_type
        self.session = ImageEditSession(source)
        self._temporary = tempfile.TemporaryDirectory(prefix="serial-vision-editor-")
        self._snapshot = Path(self._temporary.name) / "edited.png"
        self._workers: set[Any] = set()
        self._closing = False
        self._busy = False
        self._preview_size = (1, 1)
        self.setWindowTitle(self.tr("image_editor_title"))
        self.resize(1320, 820)
        self.setMinimumSize(900, 620)
        layout = QVBoxLayout(self)
        body = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(body, 1)

        left = QWidget(body)
        left_layout = QVBoxLayout(left)
        controls = QHBoxLayout()
        rotate = button(left, "rotate", self.tr("rotate"))
        rotate.clicked.connect(self.rotate_image)
        reset = button(left, "reset", self.tr("editor_reset"))
        reset.clicked.connect(self.reset_image)
        fit = button(left, "fit_image", self.tr("fit_image"))
        fit.clicked.connect(self.fit_image)
        actual = button(left, "actual_size", self.tr("actual_size"))
        actual.clicked.connect(self.actual_size)
        for control in (rotate, reset, fit, actual):
            controls.addWidget(control)
        controls.addWidget(QLabel(self.tr("editor_rotation_angle")))
        self.rotation_degrees = QSpinBox(left)
        self.rotation_degrees.setRange(-180, 180)
        self.rotation_degrees.setSuffix("°")
        self.rotation_degrees.setAccessibleName(self.tr("editor_rotation_angle"))
        controls.addWidget(self.rotation_degrees)
        apply_rotation = button(left, "rotate", self.tr("editor_apply_rotation"))
        apply_rotation.clicked.connect(lambda: self.rotate_by_degrees(self.rotation_degrees.value()))
        controls.addWidget(apply_rotation)
        controls.addStretch()
        left_layout.addLayout(controls)

        crop_group = QGroupBox(self.tr("editor_crop"), left)
        crop_layout = QGridLayout(crop_group)
        self.crop_values: dict[str, QSpinBox] = {}
        for index, key in enumerate(("editor_x", "editor_y", "editor_width", "editor_height")):
            field = QSpinBox(crop_group)
            field.setMinimum(0 if index < 2 else 2)
            field.setMaximum(12000)
            field.setAccessibleName(self.tr(key))
            field.editingFinished.connect(self.show_numeric_crop)
            crop_layout.addWidget(QLabel(self.tr(key)), 0, index)
            crop_layout.addWidget(field, 1, index)
            self.crop_values[key] = field
        apply_crop = button(crop_group, "crop", self.tr("editor_apply_crop"))
        apply_crop.clicked.connect(self.apply_crop)
        crop_layout.addWidget(apply_crop, 1, 4)
        left_layout.addWidget(crop_group)

        resize_row = QHBoxLayout()
        resize_row.addWidget(QLabel(self.tr("editor_resize_percent")))
        self.resize_percent = QSpinBox(left)
        self.resize_percent.setRange(25, 300)
        self.resize_percent.setValue(100)
        self.resize_percent.setSuffix(" %")
        self.resize_percent.setAccessibleName(self.tr("editor_resize_percent"))
        resize_row.addWidget(self.resize_percent)
        apply_resize = button(left, "resize", self.tr("editor_apply_resize"))
        apply_resize.clicked.connect(self.apply_resize)
        resize_row.addWidget(apply_resize)
        resize_row.addStretch()
        left_layout.addLayout(resize_row)

        self.advanced_toggle = QCheckBox(self.tr("editor_advanced"), left)
        self.advanced_toggle.toggled.connect(lambda checked: self.advanced_group.setVisible(checked))
        left_layout.addWidget(self.advanced_toggle)
        self.advanced_group = QGroupBox(self.tr("editor_advanced"), left)
        advanced_form = QFormLayout(self.advanced_group)
        self.adjustments: dict[str, QSlider] = {}
        self.adjustment_values: dict[str, QLabel] = {}
        for name in ("brightness", "contrast", "color", "sharpness"):
            field = QSlider(Qt.Orientation.Horizontal, self.advanced_group)
            field.setObjectName("imageAdjustmentSlider")
            field.setRange(0, 200)
            field.setValue(100)
            field.setTickInterval(50)
            field.setTickPosition(QSlider.TickPosition.TicksBelow)
            field.setAccessibleName(self.tr(f"editor_{name}"))
            value = QLabel("100 %", self.advanced_group)
            value.setMinimumWidth(48)
            field.valueChanged.connect(lambda current, label=value: label.setText(f"{current} %"))
            field.valueChanged.connect(self.schedule_preview)
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(value)
            advanced_form.addRow(self.tr(f"editor_{name}"), row)
            self.adjustments[name] = field
            self.adjustment_values[name] = value
        self.advanced_group.setVisible(False)
        left_layout.addWidget(self.advanced_group)

        self.preview = CropPreview(self.tr("select_image"), left)
        self.preview.setAccessibleName(self.tr("editor_crop_preview"))
        self.preview.setToolTip(self.tr("editor_crop_hint"))
        self.preview.selection_changed.connect(self.set_crop_from_selection)
        self.preview.rotation_previewed.connect(self.rotation_degrees.setValue)
        self.preview.rotation_requested.connect(self.rotate_by_degrees)
        left_layout.addWidget(self.preview, 1)
        self.dimensions = QLabel(left)
        left_layout.addWidget(self.dimensions)
        body.addWidget(left)

        right = QWidget(body)
        right_layout = QVBoxLayout(right)
        self.results: dict[str, QTextEdit] = {}
        for key in ("ocr", "barcodes", "ai"):
            right_layout.addWidget(QLabel(self.tr(key)))
            field = QTextEdit(right)
            field.setObjectName("recognitionResult")
            field.setReadOnly(key != "ocr")
            field.setPlainText(self.tr({"ocr": "ocr_empty", "barcodes": "barcode_empty", "ai": "editor_ai_not_selected"}[key]))
            right_layout.addWidget(field, 1)
            self.results[key] = field
        body.addWidget(right)
        body.setSizes([850, 470])

        footer = QHBoxLayout()
        self.status = QLabel(self.tr("editor_ready"), self)
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        footer.addWidget(QLabel(self.tr("editor_ai_profile")))
        self.ai_profile = QComboBox(self)
        self.ai_profile.addItem(self.tr("editor_no_ai"), "")
        for profile in service.ai_agents():
            self.ai_profile.addItem(profile["name"], profile["id"])
        footer.addWidget(self.ai_profile)
        self.recognize_button = button(self, "recognize", self.tr("editor_recognize"))
        self.recognize_button.clicked.connect(self.recognize)
        footer.addWidget(self.recognize_button)
        close = button(self, "close", self.tr("close"))
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)
        self._edit_controls = [rotate, reset, self.rotation_degrees, apply_rotation, apply_crop, self.resize_percent, apply_resize, self.advanced_toggle, *self.crop_values.values(), *self.adjustments.values()]

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self.refresh_preview)
        self.refresh_preview(False)

    def tr(self, key: str, **values: str) -> str:
        return t(self.locale, key, **values)

    def _reset_crop_fields(self) -> None:
        width, height = self.session.size
        for control in self.crop_values.values():
            control.setMaximum(max(12000, width, height))
        for key, value in (("editor_x", 0), ("editor_y", 0), ("editor_width", width), ("editor_height", height)):
            self.crop_values[key].setValue(value)
        self.preview.clear_selection()

    def refresh_preview(self, preserve_crop: bool = True) -> None:
        prior = self._crop_values() if preserve_crop else None
        self.session.set_adjustments(**{key: control.value() for key, control in self.adjustments.items()})
        image_data, self._preview_size = self.session.preview_png()
        if not self.preview.set_preview(image_data):
            self.status.setText(self.tr("editor_preview_failed"))
            return
        width, height = self.session.size
        self.dimensions.setText(self.tr("editor_dimensions", width=width, height=height))
        self._reset_crop_fields()
        if not preserve_crop:
            self.rotation_degrees.setValue(0)
        if prior is not None and prior[0] + prior[2] <= width and prior[1] + prior[3] <= height:
            for key, value in zip(("editor_x", "editor_y", "editor_width", "editor_height"), prior):
                self.crop_values[key].setValue(value)
            if prior != (0, 0, width, height):
                self.show_numeric_crop()

    def schedule_preview(self, *_args) -> None:
        self._preview_timer.start()

    def set_crop_from_selection(self, rectangle: QRectF) -> None:
        image_width, image_height = self.session.size
        preview_width, preview_height = self._preview_size
        left = max(0, min(image_width - 2, round(rectangle.left() * image_width / preview_width)))
        top = max(0, min(image_height - 2, round(rectangle.top() * image_height / preview_height)))
        right = min(image_width, max(left + 2, round(rectangle.right() * image_width / preview_width)))
        bottom = min(image_height, max(top + 2, round(rectangle.bottom() * image_height / preview_height)))
        for key, value in (("editor_x", left), ("editor_y", top), ("editor_width", right - left), ("editor_height", bottom - top)):
            self.crop_values[key].setValue(value)

    def show_numeric_crop(self) -> None:
        values = self._crop_values()
        width, height = self.session.size
        x, y, crop_width, crop_height = values
        if crop_width < 2 or crop_height < 2 or x + crop_width > width or y + crop_height > height:
            self.status.setText(self.tr("editor_crop_invalid"))
            return
        preview_width, preview_height = self._preview_size
        self.preview.set_selection(QRectF(x * preview_width / width, y * preview_height / height, crop_width * preview_width / width, crop_height * preview_height / height))
        self.status.setText(self.tr("editor_ready"))

    def _crop_values(self) -> tuple[int, int, int, int]:
        return tuple(self.crop_values[key].value() for key in ("editor_x", "editor_y", "editor_width", "editor_height"))

    def apply_crop(self) -> None:
        try:
            self.session.crop(*self._crop_values())
        except ValueError:
            self.status.setText(self.tr("editor_crop_invalid"))
            return
        self.refresh_preview(False)

    def apply_resize(self) -> None:
        try:
            self.session.resize(self.resize_percent.value())
        except ValueError:
            self.status.setText(self.tr("editor_resize_invalid"))
            return
        self.resize_percent.setValue(100)
        self.refresh_preview(False)

    def rotate_image(self) -> None:
        self.rotate_by_degrees(90)

    def rotate_by_degrees(self, degrees: int) -> None:
        try:
            self.session.rotate_degrees(degrees)
        except ValueError:
            self.status.setText(self.tr("editor_rotation_invalid"))
            self.refresh_preview()
            return
        self.refresh_preview(False)

    def reset_image(self) -> None:
        self.session.reset()
        for control in self.adjustments.values():
            control.setValue(100)
        self.resize_percent.setValue(100)
        self.refresh_preview(False)

    def fit_image(self) -> None:
        self.preview.zoom_to_fit()

    def actual_size(self) -> None:
        self.preview.zoom_actual()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.recognize_button.setEnabled(not busy)
        self.ai_profile.setEnabled(not busy)
        for control in self._edit_controls:
            control.setEnabled(not busy)
        self.preview.set_selection_enabled(not busy)

    def recognize(self) -> None:
        if self._busy or self._workers:
            return
        self._preview_timer.stop()
        self.session.set_adjustments(**{key: control.value() for key, control in self.adjustments.items()})
        try:
            self.session.save_snapshot(self._snapshot)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, self.tr("error"), self.tr("editor_snapshot_failed", error=str(error)))
            return
        self._set_busy(True)
        self.results["ocr"].setPlainText(self.tr("recognizing"))
        self.results["barcodes"].setPlainText(self.tr("recognizing"))
        self.results["ai"].setPlainText(self.tr("editor_ai_waiting") if self.ai_profile.currentData() else self.tr("editor_ai_not_selected"))
        self.status.setText(self._stage_label("ocr"))
        worker = self.local_worker_type(
            self._snapshot, self.language, self.tr("barcode_ocr_fallback"),
            self.tr("barcode_module_unavailable"), self.service.recognition_options(), self,
        )
        self._workers.add(worker)
        worker.stage.connect(self.local_stage)
        worker.completed.connect(self.local_finished)
        worker.cancelled.connect(self.local_cancelled)
        worker.finished.connect(lambda current=worker: self._worker_finished(current))
        worker.start()

    def local_stage(self, stage: str) -> None:
        if not self._closing:
            self.status.setText(self._stage_label(stage))

    def _stage_label(self, stage: str) -> str:
        if self.ai_profile.currentData():
            return self.tr("editor_stage_ocr_ai" if stage == "ocr" else "editor_stage_barcode_ai")
        return self.tr("recognition_step_ocr" if stage == "ocr" else "recognition_step_barcode")

    def local_finished(self, _path: str, ocr_text: str, barcode_text: str, _error: str) -> None:
        if self._closing:
            return
        self.results["ocr"].setPlainText(ocr_text or self.tr("ocr_empty"))
        self.results["barcodes"].setPlainText(barcode_text or self.tr("barcodes_not_found"))
        profile_id = str(self.ai_profile.currentData() or "")
        if not profile_id:
            self.status.setText(self.tr("recognition_finished"))
            return
        self.status.setText(self.tr("editor_ai_stage"))
        self.results["ai"].setPlainText(self.tr("ai_recognizing"))
        worker = self.ai_worker_type(self.service, profile_id, self._snapshot, self)
        self._workers.add(worker)
        worker.completed.connect(self.ai_finished)
        worker.failed.connect(self.ai_failed)
        worker.finished.connect(lambda current=worker: self._worker_finished(current))
        worker.start()

    def local_cancelled(self, _path: str) -> None:
        if not self._closing:
            self.status.setText(self.tr("recognition_cancelled"))

    def ai_finished(self, result: str) -> None:
        if not self._closing:
            self.results["ai"].setPlainText(result)
            self.status.setText(self.tr("recognition_finished"))

    def ai_failed(self, error: str) -> None:
        if not self._closing:
            self.results["ai"].setPlainText(error)
            self.status.setText(self.tr("editor_ai_failed"))

    def _worker_finished(self, worker: Any) -> None:
        self._workers.discard(worker)
        worker.deleteLater()
        if self._closing and not self._workers:
            self._temporary.cleanup()
            self.deleteLater()
        elif not self._workers:
            self._set_busy(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        self._preview_timer.stop()
        for worker in self._workers:
            worker.requestInterruption()
        if not self._workers:
            self._temporary.cleanup()
            self.deleteLater()
        super().closeEvent(event)
