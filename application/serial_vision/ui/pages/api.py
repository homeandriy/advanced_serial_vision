from __future__ import annotations

from PySide6.QtCore import (
    QDateTime,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.ui.buttons import button
from serial_vision.ui.pages.base import Page


class ApiPage(Page):
    def __init__(
        self, service: SerialVisionService, locale: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(service, locale, parent)
        self.install(self.api_integrations())
        self.refresh_api_integration()

    def api_integrations(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        keys_page = QWidget()
        keys_layout = QVBoxLayout(keys_page)
        self.api_keys_table = self.table(
            [
                self.translate("profile_name"),
                self.translate("note"),
                self.translate("api_key_prefix"),
                self.translate("api_rate"),
                self.translate("expires_at"),
                self.translate("api_status"),
            ]
        )
        keys_layout.addWidget(self.api_keys_table)
        actions = QHBoxLayout()
        issue = button(keys_page, "save", self.translate("issue_api_key"))
        issue.clicked.connect(self.issue_api_key)
        revoke = button(keys_page, "delete", self.translate("revoke_api_key"))
        revoke.clicked.connect(self.revoke_selected_api_key)
        refresh = button(keys_page, "refresh", self.translate("refresh"))
        refresh.clicked.connect(self.refresh_api_integration)
        actions.addWidget(issue)
        actions.addWidget(revoke)
        actions.addWidget(refresh)
        actions.addStretch()
        keys_layout.addLayout(actions)
        tabs.addTab(keys_page, self.translate("api_keys"))
        audit_page = QWidget()
        audit_layout = QVBoxLayout(audit_page)
        self.api_audit_table = self.table(
            [
                self.translate("date_time"),
                self.translate("profile_name"),
                self.translate("method"),
                self.translate("path"),
                self.translate("status"),
            ]
        )
        audit_layout.addWidget(self.api_audit_table)
        audit_refresh = button(audit_page, "refresh", self.translate("refresh"))
        audit_refresh.clicked.connect(self.refresh_api_integration)
        audit_layout.addWidget(audit_refresh)
        tabs.addTab(audit_page, self.translate("api_audit"))
        return page

    def refresh_api_integration(self) -> None:
        if not hasattr(self, "api_keys_table"):
            return
        keys = self.service.api_keys()
        self.api_keys_table.setRowCount(len(keys))
        for row, key in enumerate(keys):
            status = (
                self.translate("api_revoked") if key["revoked_at"] else self.translate("api_active")
            )
            self.fill(
                self.api_keys_table,
                row,
                [
                    key["name"],
                    key["note"],
                    key["token_prefix"],
                    self.rate_label(int(key["min_interval_ms"])),
                    key["expires_at"] or self.translate("never"),
                    status,
                ],
            )
            self.cell_item(self.api_keys_table, row, 0).setData(Qt.ItemDataRole.UserRole, key["id"])
        audit = self.service.api_audit()
        self.api_audit_table.setRowCount(len(audit))
        for row, entry in enumerate(audit):
            self.fill(
                self.api_audit_table,
                row,
                [
                    self.service.display_time(entry["requested_at"]),
                    entry["key_name"] or "—",
                    entry["method"],
                    entry["path"],
                    entry["status"],
                ],
            )

    def rate_label(self, value: int) -> str:
        return {
            200: self.translate("api_rate_5"),
            500: self.translate("api_rate_2"),
            1000: self.translate("api_rate_1"),
            2000: self.translate("api_rate_half"),
        }[value]

    def issue_api_key(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.translate("issue_api_key"))
        form = QFormLayout(dialog)
        name = QLineEdit()
        note = QLineEdit()
        rate = QComboBox()
        [
            rate.addItem(label, value)
            for label, value in (
                (self.translate("api_rate_5"), 200),
                (self.translate("api_rate_2"), 500),
                (self.translate("api_rate_1"), 1000),
                (self.translate("api_rate_half"), 2000),
            )
        ]
        expires = QCheckBox(self.translate("api_key_expiry"))
        expiry = QDateTimeEdit(QDateTime.currentDateTime().addDays(30))
        expiry.setCalendarPopup(True)
        expiry.setEnabled(False)
        expires.toggled.connect(expiry.setEnabled)
        form.addRow(self.translate("profile_name"), name)
        form.addRow(self.translate("note"), note)
        form.addRow(self.translate("api_rate"), rate)
        form.addRow(expires)
        form.addRow(self.translate("expires_at"), expiry)
        create = button(dialog, "save", self.translate("issue_api_key"))
        create.clicked.connect(dialog.accept)
        form.addRow(create)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            token = self.service.issue_api_key(
                name.text(),
                note.text(),
                expiry.dateTime().toString(Qt.DateFormat.ISODate) if expires.isChecked() else None,
                int(rate.currentData()),
            )
        except ValueError as error:
            QMessageBox.warning(self, self.translate("error"), self.translate(str(error)))
            return
        result = QDialog(self)
        result.setWindowTitle(self.translate("api_key_created"))
        result_form = QVBoxLayout(result)
        result_form.addWidget(QLabel(self.translate("api_key_once")))
        value = QTextEdit(token)
        value.setReadOnly(True)
        result_form.addWidget(value)
        copy = button(result, "copy", self.translate("copy"))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(token))
        result_form.addWidget(copy)
        result.exec()
        self.refresh_api_integration()

    def revoke_selected_api_key(self) -> None:
        item = self.api_keys_table.item(self.api_keys_table.currentRow(), 0)
        if (
            item
            and QMessageBox.question(
                self, self.translate("confirm"), self.translate("revoke_api_key_confirm")
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.service.revoke_api_key(item.data(Qt.ItemDataRole.UserRole))
            self.refresh_api_integration()
