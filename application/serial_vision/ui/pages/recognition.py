from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.gallery import GalleryItem, GalleryPage, ThumbnailCache
from serial_vision.i18n import error_message
from serial_vision.image_catalog import ImageCatalog
from serial_vision.ui.buttons import button
from serial_vision.ui.gallery_worker import GalleryWorker
from serial_vision.ui.image_editor import ImageEditorDialog
from serial_vision.ui.pages.base import Page
from serial_vision.ui.photo_preview import PhotoPreview
from serial_vision.ui.workers import (
    AiRecognitionWorker,
    RecognitionWorker,
)


class RecognitionPage(Page):
    def __init__(
        self, service: SerialVisionService, locale: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(service, locale, parent)
        self.catalog = ImageCatalog(service.image_directory())
        self.thumbnail_cache = ThumbnailCache()
        self.gallery_worker: GalleryWorker | None = None
        self._gallery_generation = 0
        self._gallery_pending: tuple[ImageCatalog, int, int] | None = None
        self._image_buttons: dict[Path, QToolButton] = {}
        self.selected_image: Path | None = None
        self.image_page = 1
        self.recognition_generation = 0
        self.recognition_worker: RecognitionWorker | None = None
        self.ai_worker: AiRecognitionWorker | None = None
        self._recognition_workers: set[RecognitionWorker] = set()
        self._recognition_busy = False
        self._ai_busy = False
        self._ai_generation = 0
        self._closing = False
        self.image_editor: ImageEditorDialog | None = None
        self.install(self.recognition())
        self.refresh_images()
        self.refresh_agents()
        QTimer.singleShot(0, self.restore_splitters)

    def begin_shutdown(self) -> None:
        self._closing = True
        self._gallery_pending = None
        self._gallery_generation += 1
        if self.image_editor is not None:
            self.image_editor.close()

    def recognition(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        path = QHBoxLayout()
        self.folder = QLineEdit(str(self.service.image_directory() or ""))
        self.folder.setReadOnly(True)
        open_folder = button(page, "folder", self.translate("open_folder"))
        open_folder.clicked.connect(self.open_folder)
        path.addWidget(self.folder)
        path.addWidget(open_folder)
        layout.addLayout(path)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.photo_splitter = split
        photos = QWidget()
        left = QVBoxLayout(photos)
        actions = QHBoxLayout()
        for action, handler in (("refresh", self.refresh_images), ("delete", self.delete_image)):
            control = button(photos, action, self.translate(action))
            control.clicked.connect(handler)
            actions.addWidget(control)
        images_heading = QHBoxLayout()
        images_heading.addWidget(QLabel(self.translate("images")))
        images_heading.addWidget(self.help_button("images", "images"))
        images_heading.addStretch()
        left.addLayout(images_heading)
        left.addLayout(actions)
        pager = QHBoxLayout()
        self.image_previous = button(photos, "previous", self.translate("previous_page"))
        self.image_previous.clicked.connect(lambda: self.change_image_page(-1))
        self.image_page_label = QLabel()
        self.image_next = button(photos, "next", self.translate("next_page"))
        self.image_next.clicked.connect(lambda: self.change_image_page(1))
        pager.addWidget(self.image_previous)
        pager.addWidget(self.image_page_label)
        pager.addWidget(self.image_next)
        left.addLayout(pager)
        self.image_cards = QScrollArea()
        self.image_cards.setWidgetResizable(True)
        self.image_cards.setMinimumHeight(0)
        self.image_cards.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.image_cards_content = QWidget()
        self.image_cards_layout = QVBoxLayout(self.image_cards_content)
        self.image_cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.image_cards.setWidget(self.image_cards_content)
        self.image_cards.viewport().installEventFilter(self)
        self.image_button_group = QButtonGroup(self)
        self.image_button_group.setExclusive(True)
        self.image_card_groups: list[tuple[QGridLayout, list[QToolButton]]] = []
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_controls = QHBoxLayout()
        for action, handler in (
            ("open_image", self.open_selected_image),
            ("editor", self.edit_image),
            ("rotate", self.rotate),
        ):
            control = button(preview_panel, action, self.translate(action))
            control.clicked.connect(handler)
            preview_controls.addWidget(control)
        preview_controls.addStretch()
        fit = button(preview_panel, "fit_image", self.translate("fit_image"))
        fit.clicked.connect(self.zoom_image_to_fit)
        actual = button(preview_panel, "actual_size", self.translate("actual_size"))
        actual.clicked.connect(self.zoom_image_actual)
        preview_controls.addWidget(fit)
        preview_controls.addWidget(actual)
        preview_layout.addLayout(preview_controls)
        self.preview = PhotoPreview(self.translate("select_image"))
        self.preview.setToolTip(self.translate("preview_zoom_hint"))
        self.preview.setAccessibleName(self.translate("image_preview"))
        self.preview.setMinimumHeight(0)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        preview_layout.addWidget(self.preview, 1)
        self.image_splitter = QSplitter(Qt.Orientation.Vertical)
        self.image_splitter.setChildrenCollapsible(True)
        self.image_splitter.addWidget(self.image_cards)
        self.image_splitter.addWidget(preview_panel)
        self.image_splitter.setCollapsible(0, True)
        self.image_splitter.setCollapsible(1, True)
        self.image_splitter.setSizes([360, 480])
        self.image_splitter.setStretchFactor(0, 1)
        self.image_splitter.setStretchFactor(1, 2)
        left.addWidget(self.image_splitter, 1)
        split.addWidget(photos)
        results = QWidget()
        right = QVBoxLayout(results)
        recognition_actions = QHBoxLayout()
        self.recognition_status = QLabel(self.translate("recognition_ready"))
        self.recognition_status.setObjectName("recognitionStatus")
        self.recognition_status.setWordWrap(True)
        recognition_actions.addWidget(self.recognition_status, 1)
        self.retry_button = button(results, "retry", self.translate("retry_recognition"))
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry_recognition)
        recognition_actions.addWidget(self.retry_button)
        self.cancel_recognition_button = button(
            results, "cancel", self.translate("cancel_recognition")
        )
        self.cancel_recognition_button.setEnabled(False)
        self.cancel_recognition_button.clicked.connect(self.cancel_recognition)
        recognition_actions.addWidget(self.cancel_recognition_button)
        right.addLayout(recognition_actions)
        ocr_heading = QHBoxLayout()
        ocr_heading.addWidget(QLabel(self.translate("ocr")))
        ocr_heading.addWidget(self.help_button("ocr", "ocr"))
        ocr_heading.addStretch()
        right.addLayout(ocr_heading)
        ocrbar = QHBoxLayout()
        self.ocr_language = QComboBox()
        self.ocr_language.addItem("English", "eng")
        self.ocr_language.addItem("Українська", "ukr")
        self.ocr_language.addItem("Polski", "pol")
        ocrbar.addWidget(QLabel(self.translate("ocr_language")))
        ocrbar.addWidget(self.ocr_language)
        right.addLayout(ocrbar)
        self.ocr_result = QTextEdit(self.translate("ocr_empty"))
        self.ocr_result.setObjectName("recognitionResult")
        self.bind_result_menu(self.ocr_result)
        right.addWidget(self.ocr_result, 1)
        barcode_heading = QHBoxLayout()
        barcode_heading.addWidget(QLabel(self.translate("barcodes")))
        barcode_heading.addWidget(self.help_button("barcode-ai", "barcodes"))
        barcode_heading.addStretch()
        right.addLayout(barcode_heading)
        self.barcode_result = QTextEdit(self.translate("barcode_empty"))
        self.barcode_result.setObjectName("recognitionResult")
        self.barcode_result.setReadOnly(True)
        self.bind_result_menu(self.barcode_result)
        right.addWidget(self.barcode_result, 1)
        ai_heading = QHBoxLayout()
        ai_heading.addWidget(QLabel(self.translate("ai")))
        ai_heading.addWidget(self.help_button("barcode-ai", "ai"))
        ai_heading.addStretch()
        right.addLayout(ai_heading)
        ai_bar = QHBoxLayout()
        self.agent_select = QComboBox()
        self.agent_select.currentIndexChanged.connect(self.agent_changed)
        self.ai_button = button(results, "ocr", self.translate("run_ai"))
        self.ai_button.clicked.connect(self.run_ai)
        ai_bar.addWidget(self.agent_select, 1)
        ai_bar.addWidget(self.ai_button)
        right.addLayout(ai_bar)
        self.ai_result = QTextEdit(self.translate("ai_empty"))
        self.ai_result.setObjectName("recognitionResult")
        self.ai_result.setReadOnly(True)
        self.bind_result_menu(self.ai_result)
        right.addWidget(self.ai_result, 1)
        split.addWidget(results)
        split.setSizes([1050, 450])
        split.setStretchFactor(0, 7)
        split.setStretchFactor(1, 3)
        layout.addWidget(split)
        return page

    def eventFilter(self, watched, event) -> bool:
        if watched is self.image_cards.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.relayout_image_cards)
        return super().eventFilter(watched, event)

    def restore_splitters(self) -> None:
        for name, splitter in (
            ("recognition_horizontal", self.photo_splitter),
            ("recognition_vertical", self.image_splitter),
        ):
            state = self.service.splitter_state(name)
            if state:
                splitter.restoreState(QByteArray(state))
            splitter.splitterMoved.connect(
                lambda _position,
                _index,
                key=name,
                control=splitter: self.service.save_splitter_state(key, bytes(control.saveState()))
            )

    def refresh_images(self) -> None:
        self.request_gallery(reindex=True)

    def request_gallery(self, reindex: bool = False) -> None:
        if self._closing:
            return
        directory = self.service.image_directory()
        if directory != self.catalog.directory:
            self.catalog = ImageCatalog(directory)
        elif reindex:
            self.catalog.invalidate()
        self.folder.setText(str(directory or ""))
        self._gallery_generation += 1
        self._gallery_pending = (self.catalog, self.image_page, self._gallery_generation)
        self.image_page_label.setText(self.translate("gallery_loading"))
        self.image_cards.setEnabled(False)
        self.image_previous.setEnabled(False)
        self.image_next.setEnabled(False)
        if self.gallery_worker is not None:
            self.gallery_worker.requestInterruption()
        else:
            self.start_gallery_worker()

    def start_gallery_worker(self) -> None:
        if self._closing or self._gallery_pending is None:
            return
        catalog, page, generation = self._gallery_pending
        self._gallery_pending = None
        worker = GalleryWorker(catalog, self.thumbnail_cache, page, self)
        self.gallery_worker = worker
        worker.completed.connect(lambda result: self.gallery_loaded(result, generation))
        worker.failed.connect(lambda error: self.gallery_failed(error, generation))
        worker.finished.connect(lambda: self.gallery_finished(worker))
        worker.start()

    def gallery_finished(self, worker: GalleryWorker) -> None:
        if self.gallery_worker is worker:
            self.gallery_worker = None
        worker.deleteLater()
        self.start_gallery_worker()

    def gallery_failed(self, error: str, generation: int) -> None:
        if self._closing or generation != self._gallery_generation:
            return
        self.image_page_label.setText(self.translate("gallery_failed", error=error))
        self.image_cards.setEnabled(True)

    def gallery_loaded(self, result: GalleryPage, generation: int) -> None:
        if self._closing or generation != self._gallery_generation:
            return
        while self.image_cards_layout.count():
            layout_item = self.image_cards_layout.takeAt(0)
            widget = layout_item.widget() if layout_item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.image_button_group.deleteLater()
        self.image_button_group = QButtonGroup(self)
        self.image_button_group.setExclusive(True)
        self.image_page = result.page
        self.image_page_label.setText(f"{result.page}/{result.pages}")
        self.image_cards.setEnabled(True)
        self.image_previous.setEnabled(result.page > 1)
        self.image_next.setEnabled(result.page < result.pages)
        if self.selected_image is not None and self.selected_image not in {
            item.image.path for item in result.items
        }:
            self.clear_image_selection()
        self.image_card_groups = []
        self._image_buttons = {}
        groups: dict[str, list[GalleryItem]] = {}
        for item in result.items:
            label = datetime.fromtimestamp(item.image.modified_ns / 1_000_000_000).strftime(
                "%Y-%m-%d"
            )
            groups.setdefault(label, []).append(item)
        for date_label, day_images in groups.items():
            heading = QLabel(self.period_label(date_label))
            heading.setObjectName("imageDateHeading")
            self.image_cards_layout.addWidget(heading)
            cards = QWidget()
            grid = QGridLayout(cards)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(8)
            day_cards = []
            for index, item in enumerate(day_images):
                image = item.image
                card = QToolButton(cards)
                card.setCheckable(True)
                card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                card.setText(image.name)
                card.setToolTip(image.name)
                card.setAccessibleName(image.name)
                pixmap = QPixmap()
                pixmap.loadFromData(item.thumbnail)
                card.setIcon(QIcon(pixmap))
                card.setIconSize(QSize(150, 95))
                card.setMinimumWidth(165)
                card.setMaximumWidth(205)
                card.setMinimumHeight(130)
                card.setChecked(image.path == self.selected_image)
                card.clicked.connect(
                    lambda _checked=False, path=image.path: self.select_image_path(path)
                )
                self.image_button_group.addButton(card)
                day_cards.append(card)
                self._image_buttons[image.path] = card
                grid.addWidget(card, index // 4, index % 4)
            self.image_card_groups.append((grid, day_cards))
            self.image_cards_layout.addWidget(cards)
        self.image_cards_layout.addStretch()
        self.relayout_image_cards()

    def relayout_image_cards(self) -> None:
        columns = max(1, (self.image_cards.viewport().width() - 16) // 173)
        for grid, cards in self.image_card_groups:
            for index, card in enumerate(cards):
                grid.addWidget(card, index // columns, index % columns)

    def change_image_page(self, offset: int) -> None:
        self.image_page = max(1, self.image_page + offset)
        self.clear_image_selection()
        self.request_gallery()

    def select_image_path(self, image_path: Path) -> None:
        self.invalidate_ai_result()
        if not self.preview.set_image(image_path):
            self.clear_image_selection()
            QMessageBox.warning(
                self,
                self.translate("error"),
                self.translate("open_file_failed", error=str(image_path)),
            )
            return
        self.selected_image = image_path
        card = self._image_buttons.get(image_path)
        if card is not None:
            card.setChecked(True)
        self.start_recognition()

    def clear_image_selection(self) -> None:
        self.invalidate_ai_result()
        worker = getattr(self, "recognition_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
        self.recognition_generation += 1
        self.selected_image = None
        self.preview.set_image(None)
        self.ocr_result.setPlainText(self.translate("ocr_empty"))
        self.barcode_result.setPlainText(self.translate("barcode_empty"))
        self.ai_result.setPlainText(self.translate("ai_empty"))
        self.recognition_status.setText(self.translate("recognition_ready"))
        self.set_recognition_busy(False)

    def start_recognition(self) -> None:
        if self.selected_image is None:
            return
        old_worker = getattr(self, "recognition_worker", None)
        if old_worker is not None and old_worker.isRunning():
            old_worker.requestInterruption()
        self.recognition_generation += 1
        generation = self.recognition_generation
        self.set_recognition_busy(True)
        self.recognition_status.setText(self.translate("recognition_step_ocr"))
        self.ocr_result.setPlainText(self.translate("recognizing"))
        self.barcode_result.setPlainText(self.translate("recognizing"))
        worker = RecognitionWorker(
            self.selected_image,
            self.ocr_language.currentData(),
            self.translate("barcode_ocr_fallback"),
            self.translate("barcode_module_unavailable"),
            self.service.recognition_options(),
            self,
        )
        self.recognition_worker = worker
        self._recognition_workers.add(worker)
        worker.stage.connect(
            lambda stage, current=generation: self.recognition_stage(current, stage)
        )
        worker.completed.connect(
            lambda path,
            ocr_text,
            barcode_text,
            error,
            current=generation: self.recognition_finished(
                current, path, ocr_text, barcode_text, error
            )
        )
        worker.cancelled.connect(
            lambda _path, current=generation: self.recognition_cancelled(current)
        )
        worker.finished.connect(lambda current=worker: self.recognition_worker_finished(current))
        worker.start()

    def recognition_worker_finished(self, worker: RecognitionWorker) -> None:
        self._recognition_workers.discard(worker)
        if getattr(self, "recognition_worker", None) is worker:
            self.recognition_worker = None
        worker.deleteLater()

    def recognition_stage(self, generation: int, stage: str) -> None:
        worker = getattr(self, "recognition_worker", None)
        if generation == self.recognition_generation and (
            worker is None or not worker.isInterruptionRequested()
        ):
            self.recognition_status.setText(
                self.translate(
                    "recognition_step_ocr" if stage == "ocr" else "recognition_step_barcode"
                )
            )

    def cancel_recognition(self) -> None:
        worker = getattr(self, "recognition_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            self.recognition_status.setText(self.translate("recognition_cancelling"))
            self.cancel_recognition_button.setEnabled(False)

    def recognition_cancelled(self, generation: int) -> None:
        if generation != self.recognition_generation:
            return
        self.ocr_result.setPlainText(self.translate("recognition_cancelled"))
        self.barcode_result.setPlainText(self.translate("recognition_cancelled"))
        self.recognition_status.setText(self.translate("recognition_cancelled"))
        self.set_recognition_busy(False)

    def set_recognition_busy(self, busy: bool) -> None:
        self._recognition_busy = busy
        for widget in (self.ocr_language, self.ocr_result, self.barcode_result, self.agent_select):
            widget.setDisabled(busy)
        self.agent_select.setDisabled(busy or self._ai_busy)
        self.retry_button.setEnabled(not busy and self.selected_image is not None)
        self.cancel_recognition_button.setEnabled(busy)
        self.agent_changed()

    def recognition_finished(
        self, generation: int, image_path: str, ocr_text: str, barcode_text: str, error: str
    ) -> None:
        if (
            generation != self.recognition_generation
            or self.selected_image is None
            or str(self.selected_image) != image_path
        ):
            return
        self.ocr_result.setPlainText(ocr_text or self.translate("ocr_empty"))
        self.barcode_result.setPlainText(barcode_text or self.translate("barcodes_not_found"))
        self.recognition_status.setText(self.translate("recognition_finished"))
        self.set_recognition_busy(False)

    def required(self) -> bool:
        if self.selected_image is None:
            QMessageBox.warning(self, self.translate("error"), self.translate("no_image"))
            return False
        return True

    def open_selected_image(self) -> None:
        if self.required():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.selected_image)))

    def edit_image(self) -> None:
        if not self.required():
            return
        assert self.selected_image is not None
        existing = getattr(self, "image_editor", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        try:
            dialog = ImageEditorDialog(
                self.service,
                self.selected_image,
                self.ui_locale,
                str(self.ocr_language.currentData()),
                RecognitionWorker,
                AiRecognitionWorker,
                self,
            )
        except (OSError, ValueError) as error:
            QMessageBox.warning(
                self, self.translate("error"), self.translate("open_file_failed", error=str(error))
            )
            return
        self.image_editor = dialog
        dialog.destroyed.connect(
            lambda: setattr(self, "image_editor", None) if self.image_editor is dialog else None
        )
        dialog.show()

    def rotate(self) -> None:
        if self.required():
            assert self.selected_image is not None
            try:
                self.catalog.rotate_clockwise(self.selected_image)
            except (OSError, ValueError) as error:
                self.error(error_message(self.ui_locale, error))
                return
            self.select_image_path(self.selected_image)
            self.refresh_images()

    def delete_image(self) -> None:
        if (
            self.required()
            and QMessageBox.question(
                self, self.translate("confirm"), self.translate("delete_image")
            )
            == QMessageBox.StandardButton.Yes
        ):
            assert self.selected_image is not None
            try:
                self.catalog.delete(self.selected_image)
            except (OSError, ValueError) as error:
                self.error(error_message(self.ui_locale, error))
                return
            self.clear_image_selection()
            self.refresh_images()

    def zoom_image_to_fit(self) -> None:
        self.preview.zoom_to_fit()

    def zoom_image_actual(self) -> None:
        self.preview.zoom_actual()

    def retry_recognition(self) -> None:
        if self.required() and (
            self.recognition_worker is None or not self.recognition_worker.isRunning()
        ):
            self.start_recognition()

    def run_ai(self) -> None:
        if not self.required():
            return
        assert self.selected_image is not None
        agent_id = self.agent_select.currentData()
        if not agent_id:
            QMessageBox.warning(self, self.translate("error"), self.translate("profile_required"))
            return
        if self.ai_worker is not None and self.ai_worker.isRunning():
            return
        self.set_ai_busy(True)
        self.ai_result.setPlainText(self.translate("ai_recognizing"))
        generation = self._ai_generation
        image_path = self.selected_image
        self.ai_worker = AiRecognitionWorker(self.service, agent_id, self.selected_image, self)
        self.ai_worker.completed.connect(
            lambda text: self.ai_finished(text, generation, image_path, agent_id)
        )
        self.ai_worker.failed.connect(
            lambda error: self.ai_failed(error, generation, image_path, agent_id)
        )
        self.ai_worker.finished.connect(lambda: self.set_ai_busy(False))
        self.ai_worker.start()

    def invalidate_ai_result(self) -> None:
        self._ai_generation += 1
        self.ai_result.setPlainText(self.translate("ai_empty"))

    def set_ai_busy(self, busy: bool) -> None:
        self._ai_busy = busy
        self.agent_select.setDisabled(busy or self._recognition_busy)
        self.agent_changed()

    def ai_finished(self, text: str, generation: int, image_path: Path, agent_id: str) -> None:
        if (
            not self._closing
            and generation == self._ai_generation
            and image_path == self.selected_image
            and agent_id == self.agent_select.currentData()
        ):
            self.ai_result.setPlainText(text)

    def ai_failed(self, error: str, generation: int, image_path: Path, agent_id: str) -> None:
        if (
            not self._closing
            and generation == self._ai_generation
            and image_path == self.selected_image
            and agent_id == self.agent_select.currentData()
        ):
            self.ai_result.setPlainText(error_message(self.ui_locale, error))

    def refresh_agents(self) -> None:
        selected = self.agent_select.currentData() if hasattr(self, "agent_select") else ""
        self.agents = self.service.ai_agents()
        self.agent_select.clear()
        self.agent_select.addItem(self.translate("no_profiles"), "")
        for agent in self.agents:
            self.agent_select.addItem(agent["name"], agent["id"])
        index = self.agent_select.findData(selected)
        self.agent_select.setCurrentIndex(index if index >= 0 else 0)

    def agent_changed(self) -> None:
        enabled = (
            not self._recognition_busy
            and self.selected_image is not None
            and bool(self.agent_select.currentData())
        )
        self.ai_result.setDisabled(not enabled)
        self.ai_button.setDisabled(not enabled or self._ai_busy)
