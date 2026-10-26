from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QDate,
    QLocale,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.i18n import t
from serial_vision.ui.buttons import button


class Page(QWidget):
    help_requested = Signal(str)
    record_requested = Signal(str)
    warehouse_requested = Signal(str)

    def __init__(
        self, service: SerialVisionService, locale: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.ui_locale = locale

    def install(self, content: QWidget) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)

    def show_help(self, section_id: str) -> None:
        self.help_requested.emit(section_id)

    def translate(self, key: str, **values: object) -> str:
        return t(self.ui_locale, key, **values)

    def help_button(self, section_id: str, title_key: str) -> QToolButton:
        control = QToolButton(self)
        control.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
        label = self.translate("open_help_section", section=self.translate(title_key))
        control.setToolTip(label)
        control.setAccessibleName(label)
        control.setAutoRaise(True)
        control.clicked.connect(lambda: self.show_help(section_id))
        return control

    def period_label(self, period: str) -> str:
        locale = QLocale(self.ui_locale)
        if len(period) == 7:
            year, month = period.split("-")
            return f"{locale.standaloneMonthName(int(month))} {year}"
        return locale.toString(
            QDate.fromString(period, "yyyy-MM-dd"), QLocale.FormatType.ShortFormat
        )

    def bind_result_menu(self, field: QTextEdit) -> None:
        field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        field.customContextMenuRequested.connect(lambda point: self.show_result_menu(field, point))

    def show_result_menu(self, field: QTextEdit, point) -> None:
        selected_text = field.textCursor().selectedText()
        if not selected_text:
            return
        menu = QMenu(field)
        copy_action = menu.addAction(self.translate("copy"))
        formatted = menu.addAction(self.translate("add_to_database"))
        raw = menu.addAction(self.translate("add_raw_to_database"))
        warehouse = menu.addAction(self.translate("wh_register_receipt"))
        action = menu.exec(field.mapToGlobal(point))
        if action == copy_action:
            field.copy()
        elif action == formatted:
            self.record_requested.emit(
                "".join(character for character in selected_text if character.isalnum())
            )
        elif action == raw:
            self.record_requested.emit(selected_text)
        elif action == warehouse:
            self.warehouse_requested.emit(selected_text)

    def show_generated_code(self, value: str, code_type: str) -> None:
        try:
            image_data = self.service.generate_code_png(value, code_type)
            filename = self.service.generated_code_filename(value, code_type)
        except ValueError as error:
            self.error(self.translate(str(error)))
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data, "PNG"):
            self.error(self.translate("code_type_invalid"))
            return
        title = (
            self.translate("qrcode_title", code=value.strip())
            if code_type in {"qr", "qrcode"}
            else self.translate("barcode_title", code=value.strip())
        )
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        preview = QLabel(dialog)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setPixmap(pixmap)
        layout.addWidget(preview)
        actions = QHBoxLayout()
        save = button(dialog, "save", self.translate("save_png"))
        save.clicked.connect(lambda: self.save_generated_code(image_data, filename))
        close = button(dialog, "close", self.translate("close"))
        close.clicked.connect(dialog.accept)
        actions.addWidget(save)
        actions.addWidget(close)
        layout.addLayout(actions)
        dialog.exec()

    def save_generated_code(self, image_data: bytes, filename: str) -> None:
        destination, _ = QFileDialog.getSaveFileName(
            self, self.translate("save_png"), filename, "PNG (*.png)"
        )
        if not destination:
            return
        try:
            self.service.save_generated_code(Path(destination), image_data)
        except OSError as error:
            self.error(self.translate("code_save_failed", error=str(error)))

    def open_folder(self) -> None:
        directory = self.service.image_directory()
        if directory is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def error(self, message: str) -> None:
        QMessageBox.warning(self, self.translate("error"), message)

    @staticmethod
    def table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def cell_item(table: QTableWidget, row: int, column: int) -> QTableWidgetItem:
        item = table.item(row, column)
        assert item is not None, "Table rows must be populated before attaching data"
        return item

    @staticmethod
    def fill(table: QTableWidget, row: int, values: list[object]) -> None:
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(str(value)))
