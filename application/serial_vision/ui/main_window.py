from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QDate, QDateTime, Qt
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox, QSplitter, QSystemTrayIcon, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
from serial_vision.application_service import SerialVisionService
from serial_vision.barcode import BarcodeRecognizer
from serial_vision.i18n import SUPPORTED_LOCALES, t
from serial_vision.image_catalog import ImageCatalog
from serial_vision.ocr import TesseractRecognizer
from serial_vision.ui.buttons import button


class MainWindow(QMainWindow):
    def __init__(self, service: SerialVisionService) -> None:
        super().__init__(); self.service = service; self.locale = service.locale(); self.catalog = ImageCatalog(service.image_directory()); self.selected_image: Path | None = None
        self.setWindowTitle(self.tr("app_name")); self.setWindowIcon(self.icon()); self.resize(1500, 920); self.create_tray()
        self.tabs = QTabWidget(); self.setCentralWidget(self.tabs); self.tabs.addTab(self.recognition(), self.tr("recognition")); self.tabs.addTab(self.equipment(), self.tr("equipment")); self.tabs.addTab(self.models(), self.tr("models")); self.tabs.addTab(self.statistics(), self.tr("statistics")); self.tabs.addTab(self.settings(), self.tr("settings")); self.refresh_images(); self.refresh_agents(); self.refresh_equipment(); self.refresh_models(); self.refresh_statistics()
        self.statusBar().addPermanentWidget(QLabel(self.tr("developer"))); self.statusBar().addPermanentWidget(QLabel(self.tr("version", version=Path("VERSION").read_text().strip())))

    def tr(self, key: str, **values: str) -> str: return t(self.locale, key, **values)
    def icon(self) -> QIcon: return QIcon(str(Path(__file__).parents[1] / "assets" / "app-icon.png"))
    def create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.icon(), self); self.tray.setToolTip(self.tr("app_name")); menu = QMenu(self); show = QAction(self.tr("open"), self); show.triggered.connect(self.showNormal); exit_action = QAction(self.tr("exit"), self); exit_action.triggered.connect(self.close); menu.addActions([show, exit_action]); self.tray.setContextMenu(menu); self.tray.show()

    def recognition(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); path = QHBoxLayout(); self.folder = QLineEdit(str(self.service.image_directory() or "")); self.folder.setReadOnly(True); open_folder = button(page, "folder", self.tr("open_folder")); open_folder.clicked.connect(self.open_folder); path.addWidget(self.folder); path.addWidget(open_folder); layout.addLayout(path)
        split = QSplitter(Qt.Orientation.Horizontal); photos = QWidget(); left = QVBoxLayout(photos); actions = QHBoxLayout()
        for action, handler in (("refresh", self.refresh_images), ("rotate", self.rotate), ("delete", self.delete_image)):
            control = button(photos, action, self.tr(action)); control.clicked.connect(handler); actions.addWidget(control)
        left.addWidget(QLabel(self.tr("images"))); left.addLayout(actions); self.images = QListWidget(); self.images.currentRowChanged.connect(self.select_image); left.addWidget(self.images, 1); self.preview = QLabel(self.tr("select_image")); self.preview.setObjectName("imagePreview"); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); left.addWidget(self.preview, 2); split.addWidget(photos)
        results = QWidget(); right = QVBoxLayout(results); right.addWidget(QLabel(self.tr("ocr"))); ocrbar = QHBoxLayout(); self.ocr_language = QComboBox(); self.ocr_language.addItem("English", "eng"); self.ocr_language.addItem("Українська", "ukr"); self.ocr_language.addItem("Polski", "pol"); ocrbar.addWidget(QLabel(self.tr("ocr_language"))); ocrbar.addWidget(self.ocr_language); ocr = button(results, "ocr", self.tr("run_ocr")); ocr.clicked.connect(self.run_ocr); ocrbar.addWidget(ocr); right.addLayout(ocrbar); self.ocr_result = QTextEdit(self.tr("ocr_empty")); self.bind_result_menu(self.ocr_result); right.addWidget(self.ocr_result, 1)
        right.addWidget(QLabel(self.tr("barcodes"))); barcode = button(results, "ocr", self.tr("run_barcode")); barcode.clicked.connect(self.run_barcodes); right.addWidget(barcode); self.barcode_result = QTextEdit(self.tr("barcode_empty")); self.barcode_result.setReadOnly(True); self.bind_result_menu(self.barcode_result); right.addWidget(self.barcode_result, 1)
        right.addWidget(QLabel(self.tr("ai"))); self.agent_select = QComboBox(); self.agent_select.currentIndexChanged.connect(self.agent_changed); right.addWidget(self.agent_select); self.ai_result = QTextEdit(self.tr("ai_empty")); self.ai_result.setReadOnly(True); self.bind_result_menu(self.ai_result); right.addWidget(self.ai_result, 1); split.addWidget(results); split.setSizes([1050, 450]); split.setStretchFactor(0, 7); split.setStretchFactor(1, 3); layout.addWidget(split); return page

    def settings(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); form = QFormLayout(); self.language = QComboBox()
        for code, name in (("uk", "Українська"), ("en", "English"), ("pl", "Polski")): self.language.addItem(name, code)
        self.language.setCurrentIndex(SUPPORTED_LOCALES.index(self.locale)); self.tesseract = QLineEdit(self.service.tesseract_binary()); folder = button(page, "folder", self.tr("choose_folder")); folder.clicked.connect(self.choose_folder); save = button(page, "save", self.tr("save")); save.clicked.connect(self.save_settings); form.addRow(self.tr("language"), self.language); form.addRow(self.tr("image_folder"), folder); form.addRow(self.tr("tesseract"), self.tesseract); form.addRow(save); layout.addLayout(form)
        layout.addWidget(QLabel(self.tr("ai_profiles"))); agent = QFormLayout(); self.agent_name = QLineEdit(); self.provider = QComboBox(); self.provider.addItems(["openai", "anthropic", "gemini"]); self.model = QLineEdit("gpt-4.1-mini"); self.token = QLineEdit(); self.token.setEchoMode(QLineEdit.EchoMode.Password)
        for key, widget in (("profile_name", self.agent_name), ("provider", self.provider), ("model", self.model), ("api_key", self.token)): agent.addRow(self.tr(key), widget)
        add = button(page, "save", self.tr("add_profile")); add.clicked.connect(self.save_agent); agent.addRow(add); layout.addLayout(agent); return page

    def equipment(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); filters = QHBoxLayout(); self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True); self.date_from.setSpecialValueText("—"); self.date_from.setDate(QDate(2000, 1, 1)); self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True); self.date_to.setSpecialValueText("—"); self.date_to.setDate(QDate(2000, 1, 1)); self.model_filter = QComboBox(); self.operation_filter = QComboBox(); self.operation_filter.addItem(self.tr("operation"), ""); self.operation_filter.addItem(self.tr("receipt"), "receipt"); self.operation_filter.addItem(self.tr("issue"), "issue"); self.type_filter = QComboBox(); self.type_filter.addItem(self.tr("all_types"), ""); self.type_filter.addItem(self.tr("modem"), "modem"); self.type_filter.addItem(self.tr("tuner"), "tuner"); self.service_filter = QComboBox(); self.service_filter.addItem(self.tr("all_services"), ""); self.service_filter.addItem(self.tr("internet"), "internet"); self.service_filter.addItem(self.tr("television"), "television"); self.device_search = QLineEdit(); self.device_search.setPlaceholderText(self.tr("search")); refresh = button(page, "refresh", self.tr("refresh")); refresh.clicked.connect(self.refresh_equipment); export = button(page, "export", self.tr("export")); export.clicked.connect(self.export_equipment)
        for control in (self.date_from, self.date_to, self.model_filter, self.operation_filter, self.type_filter, self.service_filter, self.device_search, refresh, export): filters.addWidget(control)
        layout.addLayout(filters); add = button(page, "save", self.tr("add_record")); add.clicked.connect(lambda: self.open_equipment_dialog("")); layout.addWidget(add); self.devices_table = self.table([self.tr(key) for key in ("date_time", "contract", "operation", "recognized_text", "model", "type", "service", "images")] + [""]); self.devices_table.cellDoubleClicked.connect(lambda row, _: self.edit_equipment(row)); layout.addWidget(self.devices_table); return page

    def models(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); controls = QHBoxLayout(); self.model_name = QLineEdit(); self.model_name.setPlaceholderText(self.tr("model_name")); self.model_type = QComboBox(); self.model_type.addItem(self.tr("modem"), "modem"); self.model_type.addItem(self.tr("tuner"), "tuner"); self.model_service = QComboBox(); self.model_service.addItem(self.tr("internet"), "internet"); self.model_service.addItem(self.tr("television"), "television"); add = button(page, "save", self.tr("save")); add.clicked.connect(self.add_model); delete = button(page, "delete", self.tr("delete")); delete.clicked.connect(self.delete_selected_model)
        for control in (self.model_name, self.model_type, self.model_service, add, delete): controls.addWidget(control)
        layout.addLayout(controls); self.models_table = self.table([self.tr("model"), self.tr("type"), self.tr("service")]); layout.addWidget(self.models_table); return page

    def statistics(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); self.statistics_table = self.table(["Month", self.tr("receipt"), self.tr("issue"), "Total"]); layout.addWidget(self.statistics_table); return page

    def refresh_images(self) -> None:
        self.catalog = ImageCatalog(self.service.image_directory()); self.folder.setText(str(self.service.image_directory() or "")); self.images.clear()
        for image in self.catalog.images(): self.images.addItem(image.name); self.images.item(self.images.count() - 1).setData(Qt.ItemDataRole.UserRole, image.path)
    def select_image(self, row: int) -> None:
        item = self.images.item(row); self.selected_image = item.data(Qt.ItemDataRole.UserRole) if item else None
        if self.selected_image: self.preview.setPixmap(QPixmap(str(self.selected_image)).scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)); self.run_ai()
    def required(self) -> bool:
        if self.selected_image is None: QMessageBox.warning(self, self.tr("error"), self.tr("no_image")); return False
        return True
    def rotate(self) -> None:
        if self.required(): self.catalog.rotate_clockwise(self.selected_image); self.select_image(self.images.currentRow())
    def delete_image(self) -> None:
        if self.required() and QMessageBox.question(self, self.tr("confirm"), self.tr("delete_image")) == QMessageBox.StandardButton.Yes: self.catalog.delete(self.selected_image); self.refresh_images()
    def run_ocr(self) -> None:
        if self.required():
            try: self.ocr_result.setPlainText(TesseractRecognizer(self.tesseract.text(), self.ocr_language.currentData()).recognize(self.selected_image))
            except RuntimeError as error: QMessageBox.warning(self, self.tr("error"), str(error))
    def run_barcodes(self) -> None:
        if self.required():
            try: self.barcode_result.setPlainText(BarcodeRecognizer().recognize(self.selected_image) or self.tr("barcodes_not_found"))
            except RuntimeError as error: QMessageBox.warning(self, self.tr("error"), str(error))
    def run_ai(self) -> None:
        if self.selected_image and self.agent_select.currentData():
            try: self.ai_result.setPlainText(self.service.recognize_ai(self.agent_select.currentData(), self.selected_image))
            except RuntimeError as error: self.ai_result.setPlainText(str(error))
    def refresh_agents(self) -> None:
        self.agent_select.clear(); agents = self.service.ai_agents(); self.agent_select.addItem(self.tr("no_profiles"), "")
        for agent in agents: self.agent_select.addItem(agent["name"], agent["id"])
    def agent_changed(self) -> None: self.ai_result.setDisabled(not bool(self.agent_select.currentData()))
    def save_agent(self) -> None:
        if not all((self.agent_name.text().strip(), self.model.text().strip(), self.token.text())): QMessageBox.warning(self, self.tr("error"), self.tr("profile_required")); return
        self.service.save_ai_agent(self.agent_name.text().strip(), self.provider.currentText(), self.model.text().strip(), self.token.text()); self.agent_name.clear(); self.token.clear(); self.refresh_agents()
    def open_folder(self) -> None:
        if self.service.image_directory(): QDesktopServices.openUrl(self.service.image_directory().as_uri())
    def choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("choose_folder"), str(self.service.image_directory() or ""))
        if path: self.service.save_settings(Path(path), self.tesseract.text()); self.refresh_images()
    def save_settings(self) -> None: self.service.save_locale(self.language.currentData()); QMessageBox.information(self, self.tr("settings"), self.tr("restart_language"))

    def bind_result_menu(self, field: QTextEdit) -> None:
        field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        field.customContextMenuRequested.connect(lambda point: self.show_result_menu(field, point))

    def show_result_menu(self, field: QTextEdit, point) -> None:
        selected_text = field.textCursor().selectedText()
        if not selected_text:
            return
        menu = QMenu(field); copy_action = menu.addAction(self.tr("copy")); formatted = menu.addAction(self.tr("add_to_database")); raw = menu.addAction(self.tr("add_raw_to_database")); action = menu.exec(field.mapToGlobal(point))
        if action == copy_action:
            field.copy()
        elif action == formatted:
            self.open_equipment_dialog("".join(character for character in selected_text if character.isalnum()))
        elif action == raw:
            self.open_equipment_dialog(selected_text)

    def open_equipment_dialog(self, text: str, existing=None) -> None:
        dialog = QDialog(self); dialog.setWindowTitle(self.tr("new_equipment")); form = QFormLayout(dialog); text_field = QTextEdit(text); contract = QLineEdit(); operation = QComboBox(); operation.addItem(self.tr("receipt"), "receipt"); operation.addItem(self.tr("issue"), "issue"); model = QComboBox()
        for item in self.service.models():
            model.addItem(item["name"], item["id"])
        date_time = QDateTimeEdit(); date_time.setDateTime(QDateTime.currentDateTime()); date_time.setCalendarPopup(True)
        if existing is not None:
            contract.setText(existing["contract_number"] or ""); operation.setCurrentIndex(operation.findData(existing["operation_type"])); model.setCurrentIndex(model.findData(existing["device_model_id"])); date_time.setDateTime(QDateTime.fromString(existing["registered_at"], Qt.DateFormat.ISODate))
        form.addRow(self.tr("recognized_text"), text_field); form.addRow(self.tr("contract"), contract); form.addRow(self.tr("operation"), operation); form.addRow(self.tr("model"), model); form.addRow(self.tr("date_time"), date_time)
        save = button(dialog, "save", self.tr("save")); save.clicked.connect(lambda: self.save_context_device(dialog, text_field, contract, operation, model, date_time, existing)); form.addRow(save); dialog.exec()

    def save_context_device(self, dialog: QDialog, text_field: QTextEdit, contract: QLineEdit, operation: QComboBox, model: QComboBox, date_time: QDateTimeEdit, existing=None) -> None:
        text = text_field.toPlainText().strip()
        if not text or model.currentData() is None:
            self.error(self.tr("profile_required")); return
        data = {"recognized_text": text, "contract_number": contract.text(), "operation_type": operation.currentData(), "source_image_path": existing["source_image_path"] if existing is not None else str(self.selected_image or ""), "device_model_id": model.currentData(), "registered_at": date_time.dateTime().toString(Qt.DateFormat.ISODate)}
        if existing is None: self.service.add_device(data)
        else: self.service.update_device(existing["id"], data)
        self.refresh_equipment(); self.refresh_statistics()
        dialog.accept()

    def refresh_equipment(self) -> None:
        date_from = self.date_from.date().toString("yyyy-MM-dd") if self.date_from.date().year() > 2000 else ""; date_to = self.date_to.date().toString("yyyy-MM-dd") if self.date_to.date().year() > 2000 else ""
        rows = self.service.devices(self.device_search.text().strip(), self.type_filter.currentData(), self.service_filter.currentData(), date_from, date_to, self.model_filter.currentData() or None, self.operation_filter.currentData()); self.current_devices = rows; self.devices_table.setRowCount(len(rows))
        for row, device in enumerate(rows):
            self.fill(self.devices_table, row, [device["registered_at"], device["contract_number"] or "", self.tr(device["operation_type"]), device["recognized_text"], device["model_name"], self.tr(device["device_type"]), self.tr(device["service"]), device["source_image_path"] or "", ""]); self.devices_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, device["id"])
            actions = QWidget(); action_layout = QHBoxLayout(actions); action_layout.setContentsMargins(2, 0, 2, 0); edit = button(actions, "edit", self.tr("edit")); edit.clicked.connect(lambda _, index=row: self.edit_equipment(index)); delete = button(actions, "delete", self.tr("delete")); delete.clicked.connect(lambda _, index=row: self.delete_equipment(index)); action_layout.addWidget(edit); action_layout.addWidget(delete); self.devices_table.setCellWidget(row, 8, actions)

    def edit_equipment(self, row: int) -> None:
        self.open_equipment_dialog(self.current_devices[row]["recognized_text"], self.current_devices[row])

    def delete_equipment(self, row: int) -> None:
        device = self.current_devices[row]
        if QMessageBox.question(self, self.tr("confirm"), self.tr("delete_device")) == QMessageBox.StandardButton.Yes:
            self.service.delete_device(device["id"]); self.refresh_equipment(); self.refresh_statistics()

    def export_equipment(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("export"), "equipment.csv", "CSV (*.csv)")
        if path:
            self.service.export_devices(Path(path), self.current_devices)

    def refresh_models(self) -> None:
        rows = self.service.models(); self.models_table.setRowCount(len(rows)); self.model_filter.clear(); self.model_filter.addItem(self.tr("model"), "")
        for row, model in enumerate(rows):
            self.fill(self.models_table, row, [model["name"], self.tr(model["device_type"]), self.tr(model["service"])]); self.models_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, model["id"])
            self.model_filter.addItem(model["name"], model["id"])

    def add_model(self) -> None:
        if self.model_name.text().strip():
            self.service.add_model(self.model_name.text().strip(), self.model_type.currentData(), self.model_service.currentData()); self.model_name.clear(); self.refresh_models()

    def delete_selected_model(self) -> None:
        item = self.models_table.item(self.models_table.currentRow(), 0)
        if item and QMessageBox.question(self, self.tr("confirm"), self.tr("delete_model")) == QMessageBox.StandardButton.Yes:
            try: self.service.delete_model(item.data(Qt.ItemDataRole.UserRole)); self.refresh_models()
            except Exception as error: self.error(str(error))

    def refresh_statistics(self) -> None:
        totals: dict[str, dict[str, int]] = {}
        for row in self.service.statistics(): totals.setdefault(row["period"], {"receipt": 0, "issue": 0})[row["operation_type"]] = row["total"]
        self.statistics_table.setRowCount(len(totals))
        for index, (period, values) in enumerate(totals.items()): self.fill(self.statistics_table, index, [period, values["receipt"], values["issue"], values["receipt"] + values["issue"]])

    @staticmethod
    def table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.horizontalHeader().setStretchLastSection(True); return table

    @staticmethod
    def fill(table: QTableWidget, row: int, values: list[object]) -> None:
        for column, value in enumerate(values): table.setItem(row, column, QTableWidgetItem(str(value)))
