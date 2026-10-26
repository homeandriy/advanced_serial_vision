from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QDate,
    QDateTime,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.ui.buttons import button, icon_for
from serial_vision.ui.pages.base import Page


class EquipmentPage(Page):
    changed = Signal()

    def __init__(
        self,
        service: SerialVisionService,
        locale: str,
        source_image: Callable[[], Path | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(service, locale, parent)
        self.source_image_provider = source_image
        self.equipment_page = 1
        self.install(self.equipment())
        self.refresh_model_filter()
        self.refresh_equipment()

    def refresh_model_filter(self) -> None:
        selected = self.model_filter.currentData()
        self.model_filter.clear()
        self.model_filter.addItem(self.translate("model"), "")
        for model in self.service.models():
            self.model_filter.addItem(model["name"], model["id"])
        self.model_filter.setCurrentIndex(max(0, self.model_filter.findData(selected)))

    def equipment(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setSpecialValueText("—")
        self.date_from.setDate(QDate(2000, 1, 1))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setSpecialValueText("—")
        self.date_to.setDate(QDate(2000, 1, 1))
        self.model_filter = QComboBox()
        self.operation_filter = QComboBox()
        self.operation_filter.addItem(self.translate("operation"), "")
        self.operation_filter.addItem(self.translate("receipt"), "receipt")
        self.operation_filter.addItem(self.translate("issue"), "issue")
        self.type_filter = QComboBox()
        self.type_filter.addItem(self.translate("all_types"), "")
        self.type_filter.addItem(self.translate("modem"), "modem")
        self.type_filter.addItem(self.translate("tuner"), "tuner")
        self.service_filter = QComboBox()
        self.service_filter.addItem(self.translate("all_services"), "")
        self.service_filter.addItem(self.translate("internet"), "internet")
        self.service_filter.addItem(self.translate("television"), "television")
        self.device_search = QLineEdit()
        self.device_search.setPlaceholderText(self.translate("search"))
        self.device_search.returnPressed.connect(self.refresh_equipment)
        filters = QGridLayout()
        filter_fields = (
            ("date_from_label", self.date_from),
            ("date_to_label", self.date_to),
            ("model", self.model_filter),
            ("operation", self.operation_filter),
            ("type", self.type_filter),
            ("service", self.service_filter),
        )
        for index, (label_key, control) in enumerate(filter_fields):
            row, column = divmod(index, 3)
            label = QLabel(self.translate(label_key))
            label.setBuddy(control)
            control.setAccessibleName(self.translate(label_key))
            filters.addWidget(label, row * 2, column)
            filters.addWidget(control, row * 2 + 1, column)
        search_label = QLabel(self.translate("search"))
        search_label.setBuddy(self.device_search)
        self.device_search.setAccessibleName(self.translate("search"))
        filters.addWidget(search_label, 4, 0)
        filters.addWidget(self.device_search, 5, 0, 1, 2)
        filter_actions = QHBoxLayout()
        refresh = button(page, "refresh", self.translate("refresh"))
        refresh.clicked.connect(self.refresh_equipment)
        export = button(page, "export", self.translate("export"))
        export.clicked.connect(self.export_equipment)
        filter_actions.addWidget(refresh)
        filter_actions.addWidget(export)
        filter_actions.addWidget(self.help_button("search-export", "equipment"))
        filters.addLayout(filter_actions, 5, 2)
        for column in range(3):
            filters.setColumnStretch(column, 1)
        layout.addLayout(filters)
        add = button(page, "save", self.translate("add_record"))
        add.clicked.connect(lambda: self.open_equipment_dialog(""))
        layout.addWidget(add)
        self.devices_table = self.table(
            [
                self.translate(key)
                for key in (
                    "date_time",
                    "contract",
                    "operation",
                    "recognized_text",
                    "model",
                    "type",
                    "service",
                    "images",
                    "actions",
                )
            ]
        )
        header = self.devices_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self.devices_table.cellDoubleClicked.connect(lambda row, _: self.edit_equipment(row))
        layout.addWidget(self.devices_table)
        equipment_pager = QHBoxLayout()
        self.equipment_previous = button(page, "previous", self.translate("previous_page"))
        self.equipment_previous.clicked.connect(lambda: self.change_equipment_page(-1))
        self.equipment_page_label = QLabel()
        self.equipment_next = button(page, "next", self.translate("next_page"))
        self.equipment_next.clicked.connect(lambda: self.change_equipment_page(1))
        equipment_pager.addWidget(self.equipment_previous)
        equipment_pager.addWidget(self.equipment_page_label)
        equipment_pager.addWidget(self.equipment_next)
        layout.addLayout(equipment_pager)
        return page

    def open_equipment_dialog(self, text: str, existing=None, prefill=None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.translate("new_equipment"))
        form = QFormLayout(dialog)
        text_field = QTextEdit(text)
        contract = QLineEdit()
        operation = QComboBox()
        operation.addItem(self.translate("receipt"), "receipt")
        operation.addItem(self.translate("issue"), "issue")
        model = QComboBox()
        popular = self.service.popular_models()
        popular_ids = {item["id"] for item in popular}
        for item in [
            *popular,
            *(item for item in self.service.models() if item["id"] not in popular_ids),
        ]:
            model.addItem(item["name"], item["id"])
        date_time = QDateTimeEdit()
        date_time.setDateTime(QDateTime.currentDateTime())
        date_time.setCalendarPopup(True)
        if existing is not None or prefill is not None:
            source = existing if existing is not None else prefill
            contract.setText(source["contract_number"] or "")
            operation.setCurrentIndex(operation.findData(source["operation_type"]))
            model.setCurrentIndex(model.findData(source["device_model_id"]))
            date_time.setDateTime(
                QDateTime.fromString(source["registered_at"], Qt.DateFormat.ISODate)
            )
        code_field = QWidget(dialog)
        code_layout = QVBoxLayout(code_field)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.addWidget(text_field)
        code_actions = QHBoxLayout()
        qr = button(code_field, "generate_qr", self.translate("generate_qr"))
        qr.clicked.connect(lambda: self.show_generated_code(text_field.toPlainText(), "qr"))
        barcode = button(code_field, "generate_barcode", self.translate("generate_barcode"))
        barcode.clicked.connect(
            lambda: self.show_generated_code(text_field.toPlainText(), "barcode")
        )
        code_actions.addWidget(qr)
        code_actions.addWidget(barcode)
        code_actions.addStretch()
        code_layout.addLayout(code_actions)
        form.addRow(self.translate("recognized_text"), code_field)
        form.addRow(self.translate("contract"), contract)
        form.addRow(self.translate("operation"), operation)
        form.addRow(self.translate("model"), model)
        form.addRow(self.translate("date_time"), date_time)
        if existing is not None:
            api_examples = button(dialog, "api_example", self.translate("api_request_examples"))
            api_examples.clicked.connect(lambda: self.show_device_api_examples(existing["id"]))
            copy_record = button(dialog, "copy_record", self.translate("copy_record"))
            copy_record.clicked.connect(lambda: self.copy_device_dialog(dialog, existing))
            form.addRow(api_examples)
            form.addRow(copy_record)
        save = button(dialog, "save", self.translate("save"))
        save.clicked.connect(
            lambda: self.save_context_device(
                dialog, text_field, contract, operation, model, date_time, existing, prefill
            )
        )
        form.addRow(save)
        dialog.exec()

    def copy_device_dialog(self, dialog: QDialog, device) -> None:
        dialog.reject()
        self.open_equipment_dialog(device["recognized_text"], prefill=device)

    def show_device_api_examples(self, device_id: int) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.translate("api_request_examples"))
        layout = QVBoxLayout(dialog)
        examples = QTextEdit(dialog)
        examples.setReadOnly(True)
        examples.setPlainText(
            f"GET http://127.0.0.1:{self.service.api_port()}/api/v1/equipment/{device_id}\n"
            "Authorization: Bearer <your-key>\n\n"
            f"POST http://127.0.0.1:{self.service.api_port()}/api/v1/code/get\n"
            "Authorization: Bearer <your-key>\n"
            "Content-Type: application/json\n\n"
            f'{{\n  "record_id": {device_id},\n  "type": "qrcode"\n}}'
        )
        layout.addWidget(examples)
        close = button(dialog, "close", self.translate("close"))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def save_context_device(
        self,
        dialog: QDialog,
        text_field: QTextEdit,
        contract: QLineEdit,
        operation: QComboBox,
        model: QComboBox,
        date_time: QDateTimeEdit,
        existing=None,
        prefill=None,
    ) -> None:
        text = text_field.toPlainText().strip()
        if not text:
            self.error(self.translate("recognized_text_required"))
            text_field.setFocus()
            return
        if model.currentData() is None:
            self.error(self.translate("model_required"))
            model.setFocus()
            return
        data = {
            "recognized_text": text,
            "contract_number": contract.text(),
            "operation_type": operation.currentData(),
            "source_image_path": (existing or prefill)["source_image_path"]
            if (existing is not None or prefill is not None)
            else str(self.source_image_provider() or ""),
            "device_model_id": model.currentData(),
            "registered_at": date_time.dateTime().toString(Qt.DateFormat.ISODate),
        }
        try:
            if existing is None:
                self.service.add_device(data)
            else:
                self.service.update_device(existing["id"], data)
        except ValueError as error:
            self.error(self.translate(str(error)))
            return
        self.refresh_equipment()
        self.changed.emit()
        dialog.accept()

    def refresh_equipment(self) -> None:
        date_from = (
            self.date_from.date().toString("yyyy-MM-dd")
            if self.date_from.date().year() > 2000
            else ""
        )
        date_to = (
            self.date_to.date().toString("yyyy-MM-dd") if self.date_to.date().year() > 2000 else ""
        )
        rows, self.equipment_pagination = self.service.devices(
            self.device_search.text().strip(),
            self.type_filter.currentData(),
            self.service_filter.currentData(),
            date_from,
            date_to,
            self.model_filter.currentData() or None,
            self.operation_filter.currentData(),
            getattr(self, "equipment_page", 1),
        )
        self.current_devices = rows
        self.devices_table.setRowCount(len(rows))
        pagination = self.equipment_pagination
        self.equipment_page_label.setText(
            str(self.equipment_page)
            if pagination is None
            else str(pagination["page"]) + "/" + str(pagination["pages"])
        )
        self.equipment_previous.setEnabled(pagination is not None and pagination["page"] > 1)
        self.equipment_next.setEnabled(
            pagination is not None and pagination["page"] < pagination["pages"]
        )
        self.equipment_page = 1 if pagination is None else pagination["page"]
        for row, device in enumerate(rows):
            self.fill(
                self.devices_table,
                row,
                [
                    self.service.display_time(device["registered_at"]),
                    device["contract_number"] or "",
                    self.translate(device["operation_type"]),
                    device["recognized_text"],
                    device["model_name"],
                    self.translate(device["device_type"]),
                    self.translate(device["service"]),
                    device["source_image_path"] or "",
                    "",
                ],
            )
            self.cell_item(self.devices_table, row, 0).setData(
                Qt.ItemDataRole.UserRole, device["id"]
            )
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(4, 0, 4, 0)
            action_layout.setSpacing(6)
            edit = button(actions, "edit", self.translate("edit"))
            edit.clicked.connect(lambda _, index=row: self.edit_equipment(index))
            more = button(actions, "actions", self.translate("actions"))
            menu = QMenu(more)
            for title, icon_name, handler in (
                (
                    "open_source_image",
                    "folder",
                    lambda _checked=False, index=row: self.open_source_image(index),
                ),
                (
                    "generate_qr",
                    "generate_qr",
                    lambda _checked=False, index=row: self.show_generated_code(
                        self.current_devices[index]["recognized_text"], "qr"
                    ),
                ),
                (
                    "generate_barcode",
                    "generate_barcode",
                    lambda _checked=False, index=row: self.show_generated_code(
                        self.current_devices[index]["recognized_text"], "barcode"
                    ),
                ),
            ):
                action = menu.addAction(icon_for(more, icon_name), self.translate(title))
                action.triggered.connect(handler)
            menu.addSeparator()
            delete = menu.addAction(icon_for(more, "delete"), self.translate("delete"))
            delete.triggered.connect(lambda _checked=False, index=row: self.delete_equipment(index))
            more.setMenu(menu)
            action_layout.addWidget(edit)
            action_layout.addWidget(more)
            self.devices_table.setCellWidget(row, 8, actions)

    def change_equipment_page(self, offset: int) -> None:
        if self.equipment_pagination is None:
            return
        self.equipment_page = max(1, self.equipment_page + offset)
        self.refresh_equipment()

    def edit_equipment(self, row: int) -> None:
        self.open_equipment_dialog(
            self.current_devices[row]["recognized_text"], self.current_devices[row]
        )

    def open_source_image(self, row: int) -> None:
        path = Path(str(self.current_devices[row]["source_image_path"] or ""))
        if not path.is_file():
            QMessageBox.warning(
                self, self.translate("error"), self.translate("source_image_missing")
            )
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def delete_equipment(self, row: int) -> None:
        device = self.current_devices[row]
        if (
            QMessageBox.question(self, self.translate("confirm"), self.translate("delete_device"))
            == QMessageBox.StandardButton.Yes
        ):
            self.service.delete_device(device["id"])
            self.refresh_equipment()
            self.changed.emit()

    def export_equipment(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, self.translate("export"), "equipment.csv", "CSV (*.csv)"
        )
        if path:
            date_from = (
                self.date_from.date().toString("yyyy-MM-dd")
                if self.date_from.date().year() > 2000
                else ""
            )
            date_to = (
                self.date_to.date().toString("yyyy-MM-dd")
                if self.date_to.date().year() > 2000
                else ""
            )
            rows = self.service.all_filtered_devices(
                self.device_search.text().strip(),
                self.type_filter.currentData(),
                self.service_filter.currentData(),
                date_from,
                date_to,
                self.model_filter.currentData() or None,
                self.operation_filter.currentData(),
            )
            self.service.export_devices(Path(path), rows)
