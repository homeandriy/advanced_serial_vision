from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.ui.buttons import button
from serial_vision.ui.pages.base import Page


class ModelsPage(Page):
    changed = Signal()

    def __init__(
        self, service: SerialVisionService, locale: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(service, locale, parent)
        self.install(self.models())
        self.refresh_models()

    def models(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        add = button(page, "save", self.translate("add_model"))
        add.clicked.connect(self.add_model)
        import_button = button(page, "open", self.translate("import_models"))
        import_button.clicked.connect(self.import_models)
        controls.addWidget(add)
        controls.addWidget(import_button)
        controls.addWidget(self.help_button("models", "models"))
        controls.addStretch()
        layout.addLayout(controls)
        self.models_table = self.table(
            [
                self.translate("model"),
                self.translate("type"),
                self.translate("service"),
                self.translate("usage_count"),
                self.translate("actions"),
            ]
        )
        self.models_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.models_table.setSortingEnabled(True)
        self.models_table.cellDoubleClicked.connect(lambda row, _: self.edit_model(row))
        layout.addWidget(self.models_table)
        return page

    def refresh_models(self) -> None:
        rows = self.service.models()
        self.models_table.setSortingEnabled(False)
        self.models_table.setRowCount(len(rows))
        for row, model in enumerate(rows):
            self.fill(
                self.models_table,
                row,
                [
                    model["name"],
                    self.translate(model["device_type"]),
                    self.translate(model["service"]),
                    model["usage_count"],
                    "",
                ],
            )
            self.cell_item(self.models_table, row, 0).setData(Qt.ItemDataRole.UserRole, model["id"])
            self.cell_item(self.models_table, row, 3).setData(
                Qt.ItemDataRole.EditRole, int(model["usage_count"])
            )
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(2, 0, 2, 0)
            edit = button(actions, "edit", self.translate("edit"))
            edit.clicked.connect(lambda _, index=row: self.edit_model(index))
            delete = button(actions, "delete", self.translate("delete"))
            delete.clicked.connect(lambda _, identifier=model["id"]: self.delete_model(identifier))
            action_layout.addWidget(edit)
            action_layout.addWidget(delete)
            self.models_table.setCellWidget(row, 4, actions)
        self.models_table.setSortingEnabled(True)
        self.models_table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def import_models(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.translate("import_models"), "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            result = self.service.import_models_xlsx(Path(path))
        except ValueError as error:
            self.error(self.translate(str(error)))
            return
        self.refresh_models()
        self.changed.emit()
        QMessageBox.information(
            self,
            self.translate("import_models"),
            self.translate(
                "model_import_summary",
                added=str(result["added"]),
                duplicates=str(result["duplicates"]),
                invalid=str(len(result["invalid_rows"])),
            ),
        )

    def add_model(self) -> None:
        self.open_model_dialog()

    def edit_model(self, row: int) -> None:
        item = self.models_table.item(row, 0)
        model = (
            next(
                (
                    entry
                    for entry in self.service.models()
                    if entry["id"] == item.data(Qt.ItemDataRole.UserRole)
                ),
                None,
            )
            if item
            else None
        )
        if model is not None:
            self.open_model_dialog(model)

    def open_model_dialog(self, existing=None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self.translate("edit_model") if existing else self.translate("add_model")
        )
        form = QFormLayout(dialog)
        name = QLineEdit(existing["name"] if existing else "")
        device_type = QComboBox()
        device_type.addItem(self.translate("modem"), "modem")
        device_type.addItem(self.translate("tuner"), "tuner")
        device_type.setCurrentIndex(
            max(0, device_type.findData(existing["device_type"] if existing else "modem"))
        )
        service = QComboBox()
        service.addItem(self.translate("internet"), "internet")
        service.addItem(self.translate("television"), "television")
        service.setCurrentIndex(
            max(0, service.findData(existing["service"] if existing else "internet"))
        )
        form.addRow(self.translate("model_name"), name)
        form.addRow(self.translate("type"), device_type)
        form.addRow(self.translate("service"), service)
        save = button(dialog, "save", self.translate("save"))
        save.clicked.connect(dialog.accept)
        form.addRow(save)
        if dialog.exec() != QDialog.DialogCode.Accepted or not name.text().strip():
            return
        try:
            if existing:
                self.service.update_model(
                    existing["id"],
                    name.text().strip(),
                    device_type.currentData(),
                    service.currentData(),
                )
            else:
                self.service.add_model(
                    name.text().strip(), device_type.currentData(), service.currentData()
                )
        except ValueError as error:
            self.error(self.translate(str(error)))
            return
        self.refresh_models()
        self.changed.emit()

    def delete_model(self, model_id: int) -> None:
        if (
            QMessageBox.question(self, self.translate("confirm"), self.translate("delete_model"))
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.service.delete_model(model_id)
            self.refresh_models()
            self.changed.emit()
        except ValueError as error:
            self.error(self.translate(str(error)))
