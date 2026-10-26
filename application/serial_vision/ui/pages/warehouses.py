from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.i18n import TEXT
from serial_vision.ui.buttons import button
from serial_vision.ui.pages.base import Page
from serial_vision.ui.warehouse_forms import WarehouseForm
from serial_vision.warehouse.client import WarehouseClient, object_response, response_rows
from serial_vision.warehouse.excel import read_warehouse_xlsx, save_template
from serial_vision.warehouse.security import WarehouseError


class WarehouseTask(QThread):
    def __init__(self, job: Callable[[], dict[str, object]], parent: QWidget) -> None:
        super().__init__(parent)
        self.job = job
        self.result: dict[str, object] = {}
        self.failure: WarehouseError | None = None

    def run(self) -> None:
        try:
            self.result = self.job()
        except WarehouseError as error:
            self.failure = error
        except Exception:
            self.failure = WarehouseError("wh_connection", 503)


class WarehousesPage(Page):
    session_changed = Signal(bool, bool)

    def __init__(
        self,
        service: SerialVisionService,
        locale: str,
        client: WarehouseClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(service, locale, parent)
        self.client = client
        self.worker: WarehouseTask | None = None
        self._closing = False
        self.initialized = False
        self.activated = False
        self.user: dict[str, object] = {}
        self.snapshot: dict[str, list[dict[str, object]]] = {}
        self.pending_serial = ""
        self._translation_originals: dict[tuple[str, str], str] = {}
        layout = QVBoxLayout(self)
        self.status = QLabel(self.translate("wh_intro"))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.build_login()
        self.build_password()
        self.build_workspace()

    def run_job(
        self,
        job: Callable[[], dict[str, object]],
        completed: Callable[[dict[str, object]], None],
        dialog: WarehouseForm | None = None,
    ) -> None:
        if self._closing or self.worker is not None:
            return
        self.stack.setEnabled(False)
        if dialog is not None:
            dialog.setEnabled(False)
        self.status.setText(self.translate("wh_loading"))
        worker = WarehouseTask(job, self)
        self.worker = worker
        worker.finished.connect(lambda: self.job_finished(worker, completed, dialog))
        worker.start()

    def job_finished(
        self,
        worker: WarehouseTask,
        completed: Callable[[dict[str, object]], None],
        dialog: WarehouseForm | None,
    ) -> None:
        self.worker = None
        worker.deleteLater()
        if self._closing:
            return
        self.stack.setEnabled(True)
        if dialog is not None:
            dialog.setEnabled(True)
        if worker.failure:
            code = worker.failure.code
            message = (
                self.translate(code)
                if code in TEXT[self.ui_locale]
                else self.translate("wh_input_invalid")
            )
            self.status.setText(message)
            if dialog is not None:
                dialog.feedback.setText(message)
            if code == "wh_login_required":
                self.clear_session()
            return
        self.status.setText(self.translate("wh_ready"))
        completed(worker.result)

    def call(
        self,
        action: str,
        data: dict[str, object] | None,
        completed: Callable[[dict[str, object]], None],
        dialog: WarehouseForm | None = None,
    ) -> None:
        self.run_job(lambda: self.client.call(action, data), completed, dialog)

    def activate(self) -> None:
        if not self.activated:
            self.activated = True
            self.call("status", None, self.status_loaded)

    def status_loaded(self, result: dict[str, object]) -> None:
        self.initialized = bool(result["initialized"])
        first = not self.initialized
        self.login_name.setVisible(first)
        self.login_name_label.setVisible(first)
        self.login_confirm.setVisible(first)
        self.login_confirm_label.setVisible(first)
        self.bootstrap.setVisible(first and bool(result["bootstrap_required"]))
        self.bootstrap_label.setVisible(first and bool(result["bootstrap_required"]))
        self.login_button.setText(self.translate("wh_create_admin" if first else "wh_login"))
        self.login_button.setToolTip(self.login_button.text())
        self.login_button.setAccessibleName(self.login_button.text())
        self.status.setText(self.translate("wh_first_admin" if first else "wh_intro"))
        self.session_changed.emit(False, self.initialized)

    def build_login(self) -> None:
        panel = QWidget()
        form = QFormLayout(panel)
        self.login_name = QLineEdit()
        self.login_name_label = QLabel(self.translate("wh_full_name"))
        self.login_name_label.setBuddy(self.login_name)
        form.addRow(self.login_name_label, self.login_name)
        self.login_email = QLineEdit()
        self.login_email.setAccessibleName(self.translate("wh_email"))
        form.addRow(self.translate("wh_email"), self.login_email)
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.setMaxLength(256)
        self.login_password.setAccessibleName(self.translate("wh_password"))
        form.addRow(self.translate("wh_password"), self.login_password)
        self.login_confirm = QLineEdit()
        self.login_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_confirm_label = QLabel(self.translate("wh_confirm_password"))
        self.login_confirm_label.setBuddy(self.login_confirm)
        form.addRow(self.login_confirm_label, self.login_confirm)
        self.bootstrap = QLineEdit()
        self.bootstrap.setEchoMode(QLineEdit.EchoMode.Password)
        self.bootstrap_label = QLabel(self.translate("wh_bootstrap_label"))
        self.bootstrap_label.setBuddy(self.bootstrap)
        form.addRow(self.bootstrap_label, self.bootstrap)
        show = QCheckBox(self.translate("wh_show_password"))
        show.toggled.connect(self.show_login_passwords)
        form.addRow(show)
        policy = QLabel(self.translate("wh_password_policy"))
        policy.setWordWrap(True)
        form.addRow(policy)
        self.login_button = button(panel, "open", self.translate("wh_login"))
        self.login_button.clicked.connect(self.sign_in)
        self.login_password.returnPressed.connect(self.sign_in)
        retry = button(panel, "refresh", self.translate("refresh"))
        retry.clicked.connect(lambda: self.call("status", None, self.status_loaded))
        form.addRow(self.login_button, retry)
        self.stack.addWidget(panel)

    def show_login_passwords(self, checked: bool) -> None:
        for control in (self.login_password, self.login_confirm, self.bootstrap):
            control.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )

    def sign_in(self) -> None:
        password = self.login_password.text()
        if not self.initialized and password != self.login_confirm.text():
            self.status.setText(self.translate("wh_password_mismatch"))
            return
        self.call(
            "login" if self.initialized else "bootstrap",
            {
                "email": self.login_email.text(),
                "name": self.login_name.text(),
                "password": password,
                "bootstrap_key": self.bootstrap.text(),
            },
            self.session_loaded,
        )

    def build_password(self) -> None:
        panel = QWidget()
        form = QFormLayout(panel)
        message = QLabel(self.translate("wh_password_change_required"))
        self.password_intro = message
        message.setWordWrap(True)
        form.addRow(message)
        self.old_password, self.new_password, self.confirm_password = (
            QLineEdit(),
            QLineEdit(),
            QLineEdit(),
        )
        for key, control in (
            ("wh_old_password", self.old_password),
            ("wh_new_password", self.new_password),
            ("wh_confirm_password", self.confirm_password),
        ):
            control.setEchoMode(QLineEdit.EchoMode.Password)
            control.setMaxLength(256)
            control.setAccessibleName(self.translate(key))
            form.addRow(self.translate(key), control)
        policy = QLabel(self.translate("wh_password_policy"))
        policy.setWordWrap(True)
        form.addRow(policy)
        save = button(panel, "save", self.translate("wh_change_password"))
        save.clicked.connect(self.change_password)
        leave = button(panel, "close", self.translate("wh_logout"))
        leave.clicked.connect(self.sign_out)
        form.addRow(save, leave)
        self.password_back = button(panel, "cancel", self.translate("cancel"))
        self.password_back.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.password_back.hide()
        form.addRow(self.password_back)
        self.stack.addWidget(panel)

    def open_password_change(self) -> None:
        forced = bool(self.user.get("must_change"))
        self.password_back.setVisible(not forced)
        self.password_intro.setText(
            self.translate("wh_password_change_required" if forced else "wh_change_password")
        )
        self.stack.setCurrentIndex(1)

    def change_password(self) -> None:
        if self.new_password.text() != self.confirm_password.text():
            self.status.setText(self.translate("wh_password_mismatch"))
            return
        self.call(
            "change_password",
            {"old_password": self.old_password.text(), "password": self.new_password.text()},
            self.session_loaded,
        )

    def session_loaded(self, result: dict[str, object]) -> None:
        self.user = object_response(result["user"])
        self.initialized = True
        self.old_password.setText(self.login_password.text())
        for control in (
            self.login_password,
            self.login_confirm,
            self.new_password,
            self.confirm_password,
            self.bootstrap,
        ):
            control.clear()
        if self.user["must_change"]:
            self.open_password_change()
            self.status.setText(self.translate("wh_password_change_required"))
            self.session_changed.emit(False, True)
        else:
            self.old_password.clear()
            self.stack.setCurrentIndex(2)
            self.session_changed.emit(self.user["role"] == "admin", True)
            self.refresh()

    def clear_session(self) -> None:
        for dialog in self.findChildren(QDialog):
            for field in dialog.findChildren(QLineEdit):
                field.clear()
            dialog.close()
        self.client.token = ""
        self.user = {}
        self.snapshot = {}
        for table in self.tables.values():
            table.setRowCount(0)
        for (locale, key), value in self._translation_originals.items():
            TEXT[locale][key] = value
        self._translation_originals.clear()
        self.stack.setCurrentIndex(0)
        for control in (self.old_password, self.new_password, self.confirm_password):
            control.clear()
        self.session_changed.emit(False, self.initialized)

    def sign_out(self) -> None:
        self.call("logout", None, lambda _result: self.clear_session())

    def build_workspace(self) -> None:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        actions = QHBoxLayout()
        self.identity = QLabel()
        self.identity.setTextFormat(Qt.TextFormat.PlainText)
        actions.addWidget(self.identity, 1)
        refresh = button(panel, "refresh", self.translate("refresh"))
        refresh.clicked.connect(self.refresh)
        change = button(panel, "edit", self.translate("wh_change_password"))
        change.clicked.connect(self.open_password_change)
        logout = button(panel, "close", self.translate("wh_logout"))
        logout.clicked.connect(self.sign_out)
        for header_button in (refresh, change, logout):
            actions.addWidget(header_button)
        layout.addLayout(actions)
        self.inventory_filters = QWidget(panel)
        filters = QGridLayout(self.inventory_filters)
        self.warehouse_filter, self.model_filter = QComboBox(), QComboBox()
        self.responsible_filter, self.serial_filter = QLineEdit(), QLineEdit()
        for filter_index, (key, control) in enumerate(
            (
                ("wh_warehouses", self.warehouse_filter),
                ("model", self.model_filter),
                ("wh_responsible", self.responsible_filter),
                ("wh_serial", self.serial_filter),
            )
        ):
            group = QFormLayout()
            control.setAccessibleName(self.translate(key))
            group.addRow(self.translate(key), control)
            filters.addLayout(group, filter_index // 2, filter_index % 2)
        apply = button(panel, "refresh", self.translate("wh_apply_filters"))
        apply.clicked.connect(self.apply_filters)
        filters.addWidget(apply, 2, 1)
        self.warehouse_filter.addItem(self.translate("wh_all"), "")
        self.model_filter.addItem(self.translate("wh_all"), "")
        self.warehouse_filter.currentIndexChanged.connect(self.apply_filters)
        self.model_filter.currentIndexChanged.connect(self.apply_filters)
        self.responsible_filter.returnPressed.connect(self.apply_filters)
        self.serial_filter.returnPressed.connect(self.apply_filters)
        layout.addWidget(self.inventory_filters)
        self.sections = QTabWidget()
        layout.addWidget(self.sections)
        self.tables: dict[str, QTableWidget] = {}
        self.columns: dict[str, list[tuple[str, str]]] = {
            "people": [
                ("name", "wh_full_name"),
                ("position", "wh_position"),
                ("phone", "wh_phone"),
                ("email", "wh_email"),
                ("active", "wh_active"),
            ],
            "warehouses": [
                ("code", "wh_code"),
                ("name", "wh_name"),
                ("address", "wh_address"),
                ("responsible", "wh_responsible"),
                ("active", "wh_active"),
            ],
            "balances": [
                ("code", "wh_code"),
                ("model", "model"),
                ("responsible", "wh_responsible"),
                ("quantity", "wh_quantity"),
            ],
            "movements": [
                ("registered_at", "date_time"),
                ("kind", "operation"),
                ("serial", "wh_serial"),
                ("model", "model"),
                ("source", "wh_source"),
                ("destination", "wh_destination"),
                ("actor", "wh_actor"),
                ("source_responsible", "wh_source_responsible"),
                ("destination_responsible", "wh_destination_responsible"),
            ],
            "users": [
                ("email", "wh_email"),
                ("name", "wh_full_name"),
                ("role", "wh_role"),
                ("active", "wh_active"),
                ("must_change", "wh_temporary"),
            ],
            "tokens": [("name", "wh_name"), ("scope", "wh_scope"), ("expires", "wh_expires")],
            "translations": [
                ("locale", "language"),
                ("key", "wh_translation_key"),
                ("value", "wh_translation_value"),
            ],
            "audits": [
                ("registered_at", "date_time"),
                ("actor", "wh_actor"),
                ("action", "wh_action"),
                ("entity_id", "wh_entity"),
            ],
        }
        self.manager_buttons: list[QWidget] = []
        self.section_widgets: dict[str, QWidget] = {}
        controls: dict[str, list[tuple[str, str, Callable[[], None]]]] = {
            "people": [
                ("save", "wh_add_person", self.edit_person),
                ("edit", "edit", lambda: self.edit_person(True)),
            ],
            "warehouses": [
                ("save", "wh_add_warehouse", self.edit_warehouse),
                ("edit", "edit", lambda: self.edit_warehouse(True)),
                ("edit", "wh_assign_responsible", self.edit_responsible),
                ("open", "wh_responsible_history", self.show_history),
                ("open", "wh_import", self.import_excel),
                ("save", "wh_template", self.template),
            ],
            "balances": [
                ("save", "receipt", lambda: self.movement("receipt")),
                ("save", "issue", lambda: self.movement("issue")),
                ("open", "wh_transfer", lambda: self.movement("transfer")),
                ("save", "add_model", self.add_model),
            ],
            "users": [
                ("save", "wh_add_user", self.add_user),
                ("edit", "wh_user_access", self.edit_user),
                ("reset", "wh_reset_password", self.reset_user),
            ],
            "tokens": [
                ("save", "wh_issue_token", self.issue_token),
                ("delete", "wh_revoke_token", self.revoke_token),
            ],
            "translations": [("edit", "wh_edit_translation", self.edit_translation)],
        }
        for name in (
            "warehouses",
            "people",
            "balances",
            "movements",
            "users",
            "tokens",
            "translations",
            "audits",
        ):
            columns = self.columns[name]
            section = QWidget()
            box = QVBoxLayout(section)
            bar = QGridLayout()
            for action_index, (action, label, handler) in enumerate(controls.get(name, [])):
                control = button(section, action, self.translate(label))
                # clicked(bool) must not become the edit/create flag.
                control.clicked.connect(lambda _checked=False, callback=handler: callback())
                bar.addWidget(control, action_index // 3, action_index % 3)
                if name == "people" or (
                    name == "warehouses"
                    and label not in {"wh_responsible_history", "wh_template"}
                    or label == "add_model"
                ):
                    self.manager_buttons.append(control)
            bar.setColumnStretch(3, 1)
            box.addLayout(bar)
            table = self.table([self.translate(label) for _, label in columns])
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.setSortingEnabled(False)
            header = table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setMinimumSectionSize(90)
            header.setMaximumSectionSize(360)
            if name in {"warehouses", "people", "balances", "users"}:
                for column in range(1, len(columns) - 1):
                    header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
            self.tables[name] = table
            box.addWidget(table)
            self.sections.addTab(section, self.translate("wh_" + name))
            self.section_widgets[name] = section
        self.movement_page = 1
        self.movement_footer = QWidget(panel)
        footer = QHBoxLayout(self.movement_footer)
        previous = button(panel, "previous", self.translate("previous_page"))
        previous.clicked.connect(lambda: self.change_movement_page(-1))
        following = button(panel, "next", self.translate("next_page"))
        following.clicked.connect(lambda: self.change_movement_page(1))
        self.movement_page_label = QLabel()
        footer.addWidget(previous)
        footer.addWidget(self.movement_page_label)
        footer.addWidget(following)
        layout.addWidget(self.movement_footer)
        self.sections.currentChanged.connect(self.section_changed)
        self.section_changed()
        self.stack.addWidget(panel)

    def section_changed(self, *_args: object) -> None:
        current = self.sections.currentWidget()
        self.inventory_filters.setVisible(
            current in (self.section_widgets["balances"], self.section_widgets["movements"])
        )
        self.movement_footer.setVisible(current is self.section_widgets["movements"])

    def refresh(self) -> None:
        filters: dict[str, object] = {
            "warehouse_id": self.warehouse_filter.currentData() or "",
            "model_id": self.model_filter.currentData() or "",
            "responsible": self.responsible_filter.text(),
            "serial": self.serial_filter.text(),
            "page": self.movement_page,
        }

        def load() -> dict[str, object]:
            result: dict[str, object] = {}
            result["me"] = self.client.call("me")
            user = object_response(object_response(result["me"])["user"])
            names = ["warehouses", "people", "balances", "movements", "models", "translations"]
            if user["role"] == "admin":
                names += ["users", "tokens", "audits"]
            for name in names:
                result[name] = self.client.call(
                    name, filters if name in {"movements", "balances"} else None
                )
            return result

        self.run_job(load, self.refreshed)

    def apply_filters(self, *_args: object) -> None:
        self.movement_page = 1
        self.refresh()

    def refreshed(self, result: dict[str, object]) -> None:
        self.user = object_response(object_response(result["me"])["user"])
        self.snapshot = {
            name: response_rows(object_response(value))
            for name, value in result.items()
            if name != "me"
        }
        for row in self.snapshot.get("translations", []):
            locale, key, translated = str(row["locale"]), str(row["key"]), str(row["value"])
            if locale in TEXT and key in TEXT[locale]:
                self._translation_originals.setdefault((locale, key), TEXT[locale][key])
                TEXT[locale][key] = translated
        role = str(self.user["role"])
        for control, name, label in (
            (self.warehouse_filter, "warehouses", "code"),
            (self.model_filter, "models", "name"),
        ):
            selected = control.currentData()
            control.blockSignals(True)
            control.clear()
            control.addItem(self.translate("wh_all"), "")
            for entry in self.snapshot[name]:
                control.addItem(str(entry[label]), entry["id"])
            control.setCurrentIndex(max(0, control.findData(selected)))
            control.blockSignals(False)
        self.identity.setText(str(self.user["email"]) + " · " + self.translate("wh_role_" + role))
        self.session_changed.emit(role == "admin", True)
        for manager_button in self.manager_buttons:
            manager_button.setEnabled(role != "storekeeper")
        for name in ("users", "tokens", "translations", "audits"):
            self.sections.setTabVisible(
                self.sections.indexOf(self.section_widgets[name]), role == "admin"
            )
        for name, table in self.tables.items():
            rows = self.snapshot.get(name, [])
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                for column, (key, _label) in enumerate(self.columns[name]):
                    value = row.get(key, "")
                    if key in {"active", "must_change"}:
                        value = self.translate("wh_yes" if value else "wh_no")
                    elif key == "role":
                        value = self.translate("wh_role_" + str(value))
                    elif key == "kind":
                        value = self.translate("wh_transfer" if value == "transfer" else str(value))
                    elif key == "expires":
                        value = (
                            datetime.fromtimestamp(float(str(value)), UTC)
                            .astimezone()
                            .strftime("%Y-%m-%d %H:%M")
                        )
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    table.setItem(index, column, item)
        metadata = object_response(result["movements"])
        self.movement_pages = int(str(metadata["pages"]))
        self.movement_page_label.setText(
            self.translate(
                "wh_page",
                page=self.movement_page,
                pages=self.movement_pages,
                total=metadata["total"],
            )
        )
        if self.pending_serial:
            self.movement("receipt")

    def selected(self, name: str) -> dict[str, object] | None:
        row = self.tables[name].currentRow()
        rows = self.snapshot.get(name, [])
        if 0 <= row < len(rows):
            return rows[row]
        self.status.setText(self.translate("wh_select_row"))
        return None

    def form(self, title: str) -> WarehouseForm:
        return WarehouseForm(self, self.ui_locale, title)

    def submit_form(
        self, form: WarehouseForm, action: str, values: dict[str, object], secret: str = ""
    ) -> None:
        def saved(result: dict[str, object]) -> None:
            form.accept()
            if secret:
                self.show_secret(str(result[secret]))
            self.refresh()

        self.call(action, values, saved, form)

    def edit_warehouse(self, editing: bool = False) -> None:
        row = self.selected("warehouses") if editing else {}
        if row is None:
            return
        form = self.form("wh_add_warehouse" if not editing else "edit")
        for key, label in (
            ("code", "wh_code"),
            ("name", "wh_name"),
            ("address", "wh_address"),
            ("note", "wh_note"),
        ):
            form.line(key, label, row.get(key, ""))
        form.boolean("active", "wh_active", bool(row.get("active", True)))
        form.submit(
            lambda values: self.submit_form(
                form, "save_warehouse", {**values, **({"id": row["id"]} if editing else {})}
            )
        )

    def edit_responsible(self) -> None:
        row = self.selected("warehouses")
        if row is None:
            return
        form = self.form("wh_assign_responsible")
        choices = [
            (str(person["name"]) + " · " + str(person["position"]), str(person["id"]))
            for person in self.snapshot.get("people", [])
            if person["active"]
        ]
        form.choice("person_id", "wh_responsible", choices, str(row.get("person_id") or ""))
        form.save.setEnabled(bool(choices))
        if not choices:
            form.feedback.setText(self.translate("wh_add_person"))
        form.submit(
            lambda values: self.submit_form(
                form, "save_responsible", {**values, "warehouse_id": row["id"]}
            )
        )

    def edit_person(self, editing: bool = False) -> None:
        row = self.selected("people") if editing else {}
        if row is None:
            return
        form = self.form("wh_add_person" if not editing else "edit")
        for key, label in (
            ("name", "wh_full_name"),
            ("position", "wh_position"),
            ("phone", "wh_phone"),
            ("email", "wh_email"),
        ):
            form.line(key, label, row.get(key, ""))
        form.boolean("active", "wh_active", bool(row.get("active", True)))
        form.submit(
            lambda values: self.submit_form(
                form, "save_person", {**values, **({"id": row["id"]} if editing else {})}
            )
        )

    def show_history(self) -> None:
        row = self.selected("warehouses")
        if row is not None:
            self.call(
                "responsible_history",
                {"warehouse_id": row["id"]},
                lambda result: self.show_rows(
                    "wh_responsible_history",
                    response_rows(result),
                    [
                        ("name", "wh_full_name"),
                        ("position", "wh_position"),
                        ("phone", "wh_phone"),
                        ("email", "wh_email"),
                        ("started_at", "wh_started"),
                        ("ended_at", "wh_ended"),
                        ("actor", "wh_actor"),
                    ],
                ),
            )

    def show_rows(
        self, title: str, rows: list[dict[str, object]], columns: list[tuple[str, str]]
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.translate(title))
        layout = QVBoxLayout(dialog)
        table = self.table([self.translate(label) for _, label in columns])
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.fill(table, i, [row.get(key, "") or "" for key, _ in columns])
        layout.addWidget(table)
        close = button(dialog, "close", self.translate("close"))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.resize(900, 450)
        dialog.show()

    def warehouse_choices(self) -> list[tuple[str, str]]:
        return [
            (str(row["code"]) + " · " + str(row["name"]), str(row["id"]))
            for row in self.snapshot.get("warehouses", [])
            if row["active"]
        ]

    def movement(self, kind: str) -> None:
        form = self.form("wh_transfer" if kind == "transfer" else kind)
        form.line("serial", "wh_serial", self.pending_serial)
        self.pending_serial = ""
        form.choice(
            "model_id",
            "model",
            [(str(row["name"]), str(row["id"])) for row in self.snapshot.get("models", [])],
        )
        if kind != "receipt":
            form.choice("source_id", "wh_source", self.warehouse_choices())
        if kind != "issue":
            form.choice("destination_id", "wh_destination", self.warehouse_choices())
        form.line("note", "wh_note")
        request_id = str(uuid.uuid4())
        form.submit(
            lambda values: self.submit_form(
                form, "move", {**values, "kind": kind, "request_id": request_id}
            )
        )

    def change_movement_page(self, offset: int) -> None:
        self.movement_page = min(
            getattr(self, "movement_pages", 1), max(1, self.movement_page + offset)
        )
        self.refresh()

    def prepare_receipt(self, serial: str) -> None:
        self.pending_serial = serial
        self.activate()
        if self.user and not self.user["must_change"] and self.worker is None:
            self.movement("receipt")

    def add_model(self) -> None:
        form = self.form("add_model")
        form.line("name", "model")
        form.choice(
            "device_type", "type", [(self.translate(key), key) for key in ("modem", "tuner")]
        )
        form.choice(
            "service", "service", [(self.translate(key), key) for key in ("internet", "television")]
        )
        form.submit(lambda values: self.submit_form(form, "save_model", values))

    def add_user(self) -> None:
        form = self.form("wh_add_user")
        form.line("email", "wh_email")
        form.line("name", "wh_full_name")
        form.choice(
            "role",
            "wh_role",
            [
                (self.translate("wh_role_" + key), key)
                for key in ("storekeeper", "manager", "admin")
            ],
        )
        form.line("temporary_password", "wh_temporary_password", secret=True).setPlaceholderText(
            self.translate("wh_auto_password")
        )
        form.multiple("warehouse_ids", "wh_warehouses", self.warehouse_choices(), [])
        form.submit(
            lambda values: self.submit_form(form, "create_user", values, "temporary_password")
        )

    def edit_user(self) -> None:
        row = self.selected("users")
        if row is None:
            return
        form = self.form("wh_user_access")
        form.choice(
            "role",
            "wh_role",
            [
                (self.translate("wh_role_" + key), key)
                for key in ("storekeeper", "manager", "admin")
            ],
            str(row["role"]),
        )
        form.boolean("active", "wh_active", bool(row["active"]))
        selected = row.get("warehouse_ids", [])
        form.multiple(
            "warehouse_ids",
            "wh_warehouses",
            self.warehouse_choices(),
            [str(value) for value in selected] if isinstance(selected, list) else [],
        )
        form.submit(
            lambda values: self.submit_form(form, "update_user", {**values, "id": row["id"]})
        )

    def reset_user(self) -> None:
        row = self.selected("users")
        if (
            row is not None
            and QMessageBox.question(
                self, self.translate("confirm"), self.translate("wh_reset_confirm")
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.call(
                "reset_password",
                {"id": row["id"]},
                lambda result: self.show_secret(str(result["temporary_password"])),
            )

    def show_secret(self, value: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setWindowTitle(self.translate("wh_secret_title"))
        layout = QVBoxLayout(dialog)
        explanation = QLabel(self.translate("wh_secret_once"))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        field = QLineEdit(value)
        field.setReadOnly(True)
        field.setAccessibleName(self.translate("wh_secret_title"))
        layout.addWidget(field)
        close = button(dialog, "close", self.translate("close"))
        close.clicked.connect(dialog.accept)
        dialog.finished.connect(lambda _result: field.clear())
        layout.addWidget(close)
        dialog.resize(600, 160)
        dialog.show()

    def issue_token(self) -> None:
        form = self.form("wh_issue_token")
        form.line("name", "wh_name")
        form.choice(
            "scope",
            "wh_scope",
            [
                (self.translate("wh_scope_warehouse"), "warehouse"),
                (self.translate("wh_scope_admin"), "admin"),
            ],
        )
        form.submit(lambda values: self.submit_form(form, "issue_token", values, "token"))

    def revoke_token(self) -> None:
        row = self.selected("tokens")
        if row is not None:
            self.call("revoke_token", {"hash": row["hash"]}, lambda _result: self.refresh())

    def edit_translation(self) -> None:
        form = self.form("wh_edit_translation")
        locale_choice = form.choice(
            "locale", "language", [("Українська", "uk"), ("English", "en"), ("Polski", "pl")]
        )
        key_choice = form.choice(
            "key", "wh_translation_key", [(key, key) for key in sorted(TEXT["uk"])]
        )
        editor = form.multiline(
            "value", "wh_translation_value", TEXT["uk"][str(key_choice.currentData())]
        )

        def update_preview(*_args: object) -> None:
            editor.setPlainText(
                TEXT[str(locale_choice.currentData())][str(key_choice.currentData())]
            )

        locale_choice.currentIndexChanged.connect(update_preview)
        key_choice.currentIndexChanged.connect(update_preview)
        form.submit(lambda values: self.submit_form(form, "save_translation", values))

    def import_excel(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, self.translate("wh_import"), "", "Excel (*.xlsx)"
        )
        if filename:
            self.run_job(
                lambda: self.client.call(
                    "import_warehouses", {"rows": read_warehouse_xlsx(Path(filename))}
                ),
                self.imported,
            )

    def imported(self, result: dict[str, object]) -> None:
        QMessageBox.information(
            self,
            self.translate("wh_import"),
            self.translate("wh_import_done", added=result["added"], skipped=result["skipped"]),
        )
        self.refresh()

    def template(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, self.translate("wh_template"), "warehouses.xlsx", "Excel (*.xlsx)"
        )
        if filename:
            self.run_job(lambda: self.write_template(Path(filename)), lambda _result: None)

    @staticmethod
    def write_template(path: Path) -> dict[str, object]:
        save_template(path)
        return {}

    def begin_shutdown(self) -> None:
        self._closing = True
