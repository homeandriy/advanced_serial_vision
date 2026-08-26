from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import QDate, QDateTime, QLocale, QSize, Qt, QTimer, QUrl, QThread, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtWidgets import QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QScrollArea, QSplitter, QSystemTrayIcon, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QVBoxLayout, QWidget
from serial_vision.application_service import SerialVisionService
from serial_vision.barcode import BarcodeRecognizer
from serial_vision.i18n import SUPPORTED_LOCALES, t
from serial_vision.image_catalog import ImageCatalog
from serial_vision.ocr import RapidOcrRecognizer
from serial_vision.ui.buttons import button
from serial_vision.updates import ReleaseInfo, check_latest_release, launch_update


class UpdateWorker(QThread):
    checked = Signal(object)
    failed = Signal(str)

    def __init__(self, repository: str, current_version: str, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.current_version = current_version

    def run(self) -> None:
        try:
            self.checked.emit(check_latest_release(self.repository, self.current_version))
        except Exception as error:
            self.failed.emit(str(error))



class RecognitionWorker(QThread):
    completed = Signal(str, str, str, str)

    def __init__(self, image_path: Path, language: str, parent=None) -> None:
        super().__init__(parent)
        self.image_path = image_path
        self.language = language

    def run(self) -> None:
        ocr_text = ""
        barcode_text = ""
        try:
            ocr_text = RapidOcrRecognizer(self.language).recognize(self.image_path)
        except RuntimeError as error:
            ocr_text = str(error)
        try:
            barcode_text = BarcodeRecognizer().recognize(self.image_path)
        except RuntimeError as error:
            barcode_text = str(error)
        self.completed.emit(str(self.image_path), ocr_text, barcode_text, "")


class MainWindow(QMainWindow):
    def __init__(self, service: SerialVisionService) -> None:
        super().__init__(); self.service = service; self.locale = service.locale(); self.catalog = ImageCatalog(service.image_directory()); self.selected_image: Path | None = None; self.image_page = 1; self.equipment_page = 1
        self.service.register_launch(); self.service.log_startup("Application startup started"); self.setWindowTitle(self.tr("app_name")); self.setWindowIcon(self.icon()); self.resize(1500, 920); self.create_tray(); self.create_menus(); self.recognition_generation = 0
        self.tabs = QTabWidget(); self.setCentralWidget(self.tabs); self.tabs.addTab(self.recognition(), self.tr("recognition")); self.tabs.addTab(self.equipment(), self.tr("equipment")); self.tabs.addTab(self.models(), self.tr("models")); self.tabs.addTab(self.statistics(), self.tr("statistics")); self.tabs.addTab(self.settings(), self.tr("settings")); self.refresh_images(); self.refresh_agents(); self.refresh_equipment(); self.refresh_models(); self.refresh_statistics()
        self.statusBar().addPermanentWidget(QLabel(self.tr("developer"))); self.statusBar().addPermanentWidget(QLabel(self.tr("version", version=Path("VERSION").read_text().strip()))); self.service.log_startup("Main window is ready"); QTimer.singleShot(60_000, self.check_updates_silently); self.show_first_run_setup() if self.service.setup_required() else None

    def tr(self, key: str, **values: str) -> str: return t(self.locale, key, **values)
    def icon(self) -> QIcon: return QIcon(str(Path(__file__).parents[1] / "assets" / "app-icon.png"))
    def create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.icon(), self); self.tray.setToolTip(self.tr("app_name")); menu = QMenu(self); show = QAction(self.tr("open"), self); show.triggered.connect(self.showNormal); exit_action = QAction(self.tr("exit"), self); exit_action.triggered.connect(self.close); menu.addActions([show, exit_action]); self.tray.setContextMenu(menu); self.tray.show()

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu(self.tr("menu_file"))
        choose = file_menu.addAction(self.tr("choose_folder"))
        choose.triggered.connect(self.choose_folder)
        open_action = file_menu.addAction(self.tr("open_folder"))
        open_action.triggered.connect(self.open_folder)
        file_menu.addSeparator()
        exit_action = file_menu.addAction(self.tr("exit"))
        exit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu(self.tr("menu_edit"))
        copy_action = edit_menu.addAction(self.tr("copy"))
        copy_action.triggered.connect(self.copy_active_text)
        rotate_action = edit_menu.addAction(self.tr("rotate"))
        rotate_action.triggered.connect(self.rotate)
        delete_action = edit_menu.addAction(self.tr("delete"))
        delete_action.triggered.connect(self.delete_image)

        view_menu = self.menuBar().addMenu(self.tr("menu_view"))
        for index, key in enumerate(("recognition", "equipment", "models", "statistics", "settings")):
            action = view_menu.addAction(self.tr(key))
            action.triggered.connect(lambda _checked=False, current=index: self.tabs.setCurrentIndex(current))

        help_menu = self.menuBar().addMenu(self.tr("help"))
        help_action = help_menu.addAction(self.tr("help_contents"))
        help_action.triggered.connect(self.show_help)
        log_action = help_menu.addAction(self.tr("startup_log"))
        log_action.triggered.connect(self.open_startup_log)
        update_action = help_menu.addAction(self.tr("check_updates"))
        update_action.triggered.connect(self.check_updates)
        about_action = help_menu.addAction(self.tr("about"))
        about_action.triggered.connect(lambda: QMessageBox.information(self, self.tr("about"), self.tr("about_text")))

    def show_help(self) -> None:
        QMessageBox.information(self, self.tr("help"), self.tr("help_text"))

    def copy_active_text(self) -> None:
        focused = QApplication.focusWidget()
        if isinstance(focused, QTextEdit) and focused.textCursor().hasSelection():
            focused.copy()
            return
        QMessageBox.information(self, self.tr("help"), self.tr("select_text_to_copy"))

    def check_updates(self) -> None:
        self.start_update_check(show_status=True)

    def check_updates_silently(self) -> None:
        self.start_update_check(show_status=False)

    def start_update_check(self, show_status: bool) -> None:
        repository = self.service.update_repository()
        if not repository:
            if show_status:
                QMessageBox.information(self, self.tr("help"), self.tr("update_not_configured"))
            return
        if getattr(self, "update_worker", None) and self.update_worker.isRunning():
            return
        self.update_worker = UpdateWorker(repository, Path("VERSION").read_text().strip(), self)
        self.update_worker.checked.connect(lambda release: self.update_checked(release, show_status))
        self.update_worker.failed.connect(lambda error: self.update_failed(error, show_status))
        self.update_worker.start()

    def update_checked(self, release: ReleaseInfo | None, show_status: bool) -> None:
        if release is None:
            if show_status:
                QMessageBox.information(self, self.tr("help"), self.tr("update_not_found"))
            return
        if sys.platform == "win32" and release.installer_url:
            try:
                launch_update(release, os.getpid())
            except RuntimeError as error:
                if show_status:
                    QMessageBox.warning(self, self.tr("error"), self.tr(str(error)))
                return
            self.service.log_startup(f"Starting automatic update to {release.version}")
            self.close()
            QApplication.quit()
            return
        if show_status:
            QMessageBox.information(self, self.tr("help"), self.tr("update_available_manual", version=release.version))

    def update_failed(self, error: str, show_status: bool) -> None:
        self.service.log_startup(f"Update check failed: {error}")
        if show_status:
            QMessageBox.warning(self, self.tr("error"), error)

    def open_startup_log(self) -> None:
        self.service.log_startup("User opened startup log")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.startup_log_path())))

    def show_first_run_setup(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dialog.setWindowTitle(self.tr("first_run"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.tr("license_text")))
        accepted = QCheckBox(self.tr("license_acceptance"))
        layout.addWidget(accepted)
        path = QLineEdit()
        path.setReadOnly(True)
        choose = button(dialog, "folder", self.tr("choose_folder"))
        choose.clicked.connect(lambda: path.setText(QFileDialog.getExistingDirectory(dialog, self.tr("choose_folder"))))
        layout.addWidget(path)
        layout.addWidget(choose)
        accept = button(dialog, "save", self.tr("accept_and_continue"))
        accept.clicked.connect(lambda: self.complete_first_run(dialog, path.text(), accepted.isChecked()))
        layout.addWidget(accept)
        dialog.exec()

    def complete_first_run(self, dialog: QDialog, path: str, accepted: bool) -> None:
        if not accepted:
            QMessageBox.warning(dialog, self.tr("error"), self.tr("license_required"))
            return
        try:
            self.service.complete_setup(Path(path))
        except ValueError:
            QMessageBox.warning(dialog, self.tr("error"), self.tr("folder_missing"))
            return
        self.refresh_images()
        dialog.accept()

    def recognition(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); path = QHBoxLayout(); self.folder = QLineEdit(str(self.service.image_directory() or "")); self.folder.setReadOnly(True); open_folder = button(page, "folder", self.tr("open_folder")); open_folder.clicked.connect(self.open_folder); path.addWidget(self.folder); path.addWidget(open_folder); layout.addLayout(path)
        split = QSplitter(Qt.Orientation.Horizontal); photos = QWidget(); left = QVBoxLayout(photos); actions = QHBoxLayout()
        for action, handler in (("refresh", self.refresh_images), ("open_image", self.open_selected_image), ("rotate", self.rotate), ("delete", self.delete_image)):
            control = button(photos, action, self.tr(action)); control.clicked.connect(handler); actions.addWidget(control)
        left.addWidget(QLabel(self.tr("images"))); left.addLayout(actions); pager = QHBoxLayout(); self.image_previous = button(photos, "previous", self.tr("previous_page")); self.image_previous.clicked.connect(lambda: self.change_image_page(-1)); self.image_page_label = QLabel(); self.image_next = button(photos, "next", self.tr("next_page")); self.image_next.clicked.connect(lambda: self.change_image_page(1)); pager.addWidget(self.image_previous); pager.addWidget(self.image_page_label); pager.addWidget(self.image_next); left.addLayout(pager)
        self.image_cards = QScrollArea(); self.image_cards.setWidgetResizable(True); self.image_cards_content = QWidget(); self.image_cards_layout = QVBoxLayout(self.image_cards_content); self.image_cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.image_cards.setWidget(self.image_cards_content); self.image_button_group = QButtonGroup(self); self.image_button_group.setExclusive(True); left.addWidget(self.image_cards, 1)
        self.preview = QLabel(self.tr("select_image")); self.preview.setObjectName("imagePreview"); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); left.addWidget(self.preview, 2); split.addWidget(photos)
        results = QWidget(); right = QVBoxLayout(results); right.addWidget(QLabel(self.tr("ocr"))); ocrbar = QHBoxLayout(); self.ocr_language = QComboBox(); self.ocr_language.addItem("English", "eng"); self.ocr_language.addItem("Українська", "ukr"); self.ocr_language.addItem("Polski", "pol"); ocrbar.addWidget(QLabel(self.tr("ocr_language"))); ocrbar.addWidget(self.ocr_language); self.ocr_button = button(results, "ocr", self.tr("run_ocr")); self.ocr_button.clicked.connect(self.run_ocr); ocrbar.addWidget(self.ocr_button); right.addLayout(ocrbar); self.ocr_result = QTextEdit(self.tr("ocr_empty")); self.bind_result_menu(self.ocr_result); right.addWidget(self.ocr_result, 1)
        right.addWidget(QLabel(self.tr("barcodes"))); self.barcode_button = button(results, "ocr", self.tr("run_barcode")); self.barcode_button.clicked.connect(self.run_barcodes); right.addWidget(self.barcode_button); self.barcode_result = QTextEdit(self.tr("barcode_empty")); self.barcode_result.setReadOnly(True); self.bind_result_menu(self.barcode_result); right.addWidget(self.barcode_result, 1)
        right.addWidget(QLabel(self.tr("ai"))); self.agent_select = QComboBox(); self.agent_select.currentIndexChanged.connect(self.agent_changed); right.addWidget(self.agent_select); self.ai_result = QTextEdit(self.tr("ai_empty")); self.ai_result.setReadOnly(True); self.bind_result_menu(self.ai_result); right.addWidget(self.ai_result, 1); split.addWidget(results); split.setSizes([1050, 450]); split.setStretchFactor(0, 7); split.setStretchFactor(1, 3); layout.addWidget(split); return page

    def settings(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page)
        interface = QGroupBox(self.tr("interface_settings")); interface_form = QFormLayout(interface); self.language = QComboBox()
        for code, name in (("uk", "Українська"), ("en", "English"), ("pl", "Polski")): self.language.addItem(name, code)
        self.language.setCurrentIndex(SUPPORTED_LOCALES.index(self.locale)); interface_form.addRow(self.tr("language"), self.language); interface_save = button(interface, "save", self.tr("save_interface")); interface_save.clicked.connect(self.save_interface_settings); interface_form.addRow(interface_save); layout.addWidget(interface)

        folder_group = QGroupBox(self.tr("folder_settings")); folder_form = QFormLayout(folder_group); self.settings_folder_path = QLineEdit(str(self.service.image_directory() or "")); self.settings_folder_path.setReadOnly(True); choose = button(folder_group, "folder", self.tr("choose_folder")); choose.clicked.connect(self.choose_folder); folder_form.addRow(self.tr("image_folder"), self.settings_folder_path); folder_form.addRow(choose); folder_save = button(folder_group, "save", self.tr("save_folder")); folder_save.clicked.connect(self.save_folder_settings); folder_form.addRow(folder_save); layout.addWidget(folder_group)

        updates = QGroupBox(self.tr("update_settings")); update_form = QFormLayout(updates); self.github_repository = QLineEdit(self.service.update_repository()); update_form.addRow(self.tr("github_repository"), self.github_repository); update_save = button(updates, "save", self.tr("save_updates")); update_save.clicked.connect(self.save_update_settings); update_form.addRow(update_save); layout.addWidget(updates)

        profiles = QGroupBox(self.tr("ai_profiles")); agent = QFormLayout(profiles); self.agent_name = QLineEdit(); self.provider = QComboBox(); self.provider.addItems(["openai", "anthropic", "gemini"]); self.model = QLineEdit("gpt-4.1-mini"); self.token = QLineEdit(); self.token.setEchoMode(QLineEdit.EchoMode.Password)
        for key, widget in (("profile_name", self.agent_name), ("provider", self.provider), ("model", self.model), ("api_key", self.token)): agent.addRow(self.tr(key), widget)
        add = button(profiles, "save", self.tr("add_profile")); add.clicked.connect(self.save_agent); agent.addRow(add); layout.addWidget(profiles); layout.addStretch(); return page

    def equipment(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); filters = QHBoxLayout(); self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True); self.date_from.setSpecialValueText("—"); self.date_from.setDate(QDate(2000, 1, 1)); self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True); self.date_to.setSpecialValueText("—"); self.date_to.setDate(QDate(2000, 1, 1)); self.model_filter = QComboBox(); self.operation_filter = QComboBox(); self.operation_filter.addItem(self.tr("operation"), ""); self.operation_filter.addItem(self.tr("receipt"), "receipt"); self.operation_filter.addItem(self.tr("issue"), "issue"); self.type_filter = QComboBox(); self.type_filter.addItem(self.tr("all_types"), ""); self.type_filter.addItem(self.tr("modem"), "modem"); self.type_filter.addItem(self.tr("tuner"), "tuner"); self.service_filter = QComboBox(); self.service_filter.addItem(self.tr("all_services"), ""); self.service_filter.addItem(self.tr("internet"), "internet"); self.service_filter.addItem(self.tr("television"), "television"); self.device_search = QLineEdit(); self.device_search.setPlaceholderText(self.tr("search")); refresh = button(page, "refresh", self.tr("refresh")); refresh.clicked.connect(self.refresh_equipment); export = button(page, "export", self.tr("export")); export.clicked.connect(self.export_equipment)
        for control in (self.date_from, self.date_to, self.model_filter, self.operation_filter, self.type_filter, self.service_filter, self.device_search, refresh, export): filters.addWidget(control)
        layout.addLayout(filters); add = button(page, "save", self.tr("add_record")); add.clicked.connect(lambda: self.open_equipment_dialog("")); layout.addWidget(add); self.devices_table = self.table([self.tr(key) for key in ("date_time", "contract", "operation", "recognized_text", "model", "type", "service", "images")] + [""]); self.devices_table.cellDoubleClicked.connect(lambda row, _: self.edit_equipment(row)); layout.addWidget(self.devices_table); equipment_pager = QHBoxLayout(); self.equipment_previous = button(page, "previous", self.tr("previous_page")); self.equipment_previous.clicked.connect(lambda: self.change_equipment_page(-1)); self.equipment_page_label = QLabel(); self.equipment_next = button(page, "next", self.tr("next_page")); self.equipment_next.clicked.connect(lambda: self.change_equipment_page(1)); equipment_pager.addWidget(self.equipment_previous); equipment_pager.addWidget(self.equipment_page_label); equipment_pager.addWidget(self.equipment_next); layout.addLayout(equipment_pager); return page

    def models(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); controls = QHBoxLayout(); self.model_name = QLineEdit(); self.model_name.setPlaceholderText(self.tr("model_name")); self.model_type = QComboBox(); self.model_type.addItem(self.tr("modem"), "modem"); self.model_type.addItem(self.tr("tuner"), "tuner"); self.model_service = QComboBox(); self.model_service.addItem(self.tr("internet"), "internet"); self.model_service.addItem(self.tr("television"), "television"); add = button(page, "save", self.tr("save")); add.clicked.connect(self.add_model); delete = button(page, "delete", self.tr("delete")); delete.clicked.connect(self.delete_selected_model)
        for control in (self.model_name, self.model_type, self.model_service, add, delete): controls.addWidget(control)
        layout.addLayout(controls); self.models_table = self.table([self.tr("model"), self.tr("type"), self.tr("service")]); layout.addWidget(self.models_table); return page

    def statistics(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.statistics_mode = QComboBox()
        self.statistics_mode.addItem(self.tr("day"), "day")
        self.statistics_mode.addItem(self.tr("month"), "month")
        self.statistics_mode.setCurrentIndex(1)
        self.statistics_mode.currentIndexChanged.connect(self.refresh_statistics)
        layout.addWidget(self.statistics_mode)
        self.statistics_table = self.table([self.tr("date_time"), self.tr("receipt"), self.tr("issue"), self.tr("total")])
        layout.addWidget(self.statistics_table)
        self.operations_chart = QChartView()
        self.services_chart = QChartView()
        self.models_chart = QChartView()
        for chart in (self.operations_chart, self.services_chart, self.models_chart):
            chart.setMinimumHeight(190)
            layout.addWidget(chart)
        return page

    def period_label(self, period: str) -> str:
        locale = QLocale(self.locale)
        if len(period) == 7:
            year, month = period.split("-")
            return f"{locale.standaloneMonthName(int(month))} {year}"
        return locale.toString(QDate.fromString(period, "yyyy-MM-dd"), QLocale.FormatType.ShortFormat)

    def make_bar_chart(self, title: str, categories: list[str], series_values: list[tuple[str, list[int]]]) -> QChart:
        series = QBarSeries()
        maximum = 1
        for label, values in series_values:
            bar_set = QBarSet(label)
            bar_set.append(values)
            series.append(bar_set)
            maximum = max([maximum, *values])
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.legend().setVisible(len(series_values) > 1)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_y = QValueAxis()
        axis_y.setRange(0, maximum)
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        return chart

    def refresh_images(self) -> None:
        self.catalog = ImageCatalog(self.service.image_directory()); self.folder.setText(str(self.service.image_directory() or ""))
        while self.image_cards_layout.count():
            item = self.image_cards_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.image_button_group = QButtonGroup(self); self.image_button_group.setExclusive(True)
        images, metadata = self.catalog.page(self.image_page); self.image_page = int(metadata["page"]); self.image_page_label.setText(str(self.image_page) + "/" + str(metadata["pages"])); self.image_previous.setEnabled(self.image_page > 1); self.image_next.setEnabled(bool(metadata["has_more"]))
        groups: dict[str, list] = {}
        for image in images:
            label = datetime.fromtimestamp(image.path.stat().st_mtime).strftime("%Y-%m-%d")
            groups.setdefault(label, []).append(image)
        for date_label, day_images in groups.items():
            heading = QLabel(self.period_label(date_label)); heading.setObjectName("imageDateHeading"); self.image_cards_layout.addWidget(heading)
            cards = QWidget(); grid = QGridLayout(cards); grid.setContentsMargins(0, 0, 0, 0)
            for index, image in enumerate(day_images):
                card = QToolButton(cards); card.setCheckable(True); card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon); card.setText(image.name); card.setToolTip(image.name); card.setAccessibleName(image.name); pixmap = QPixmap(str(image.path)); card.setIcon(QIcon(pixmap)); card.setIconSize(QSize(150, 95)); card.setMinimumWidth(165); card.setMaximumWidth(205); card.setMinimumHeight(130); card.clicked.connect(lambda _checked=False, path=image.path: self.select_image_path(path)); self.image_button_group.addButton(card); grid.addWidget(card, index // 4, index % 4)
            self.image_cards_layout.addWidget(cards)
        self.image_cards_layout.addStretch()

    def change_image_page(self, offset: int) -> None:
        self.image_page = max(1, self.image_page + offset)
        self.refresh_images()

    def select_image_path(self, image_path: Path) -> None:
        self.selected_image = image_path
        self.preview.setPixmap(QPixmap(str(image_path)).scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.recognition_generation += 1
        generation = self.recognition_generation
        self.set_recognition_busy(True)
        self.ocr_result.setPlainText(self.tr("recognizing"))
        self.barcode_result.setPlainText(self.tr("recognizing"))
        self.recognition_worker = RecognitionWorker(image_path, self.ocr_language.currentData(), self)
        self.recognition_worker.completed.connect(lambda path, ocr_text, barcode_text, error, current=generation: self.recognition_finished(current, path, ocr_text, barcode_text, error))
        self.recognition_worker.start()

    def set_recognition_busy(self, busy: bool) -> None:
        for widget in (self.ocr_language, self.ocr_button, self.barcode_button, self.ocr_result, self.barcode_result, self.agent_select, self.ai_result):
            widget.setDisabled(busy)

    def recognition_finished(self, generation: int, image_path: str, ocr_text: str, barcode_text: str, error: str) -> None:
        if generation != self.recognition_generation or self.selected_image is None or str(self.selected_image) != image_path:
            return
        self.ocr_result.setPlainText(ocr_text or self.tr("ocr_empty"))
        self.barcode_result.setPlainText(barcode_text or self.tr("barcodes_not_found"))
        self.set_recognition_busy(False)
        self.agent_changed()
        self.run_ai()

    def required(self) -> bool:
        if self.selected_image is None: QMessageBox.warning(self, self.tr("error"), self.tr("no_image")); return False
        return True

    def open_selected_image(self) -> None:
        if self.required():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.selected_image)))

    def rotate(self) -> None:
        if self.required():
            self.catalog.rotate_clockwise(self.selected_image)
            self.select_image_path(self.selected_image)

    def delete_image(self) -> None:
        if self.required() and QMessageBox.question(self, self.tr("confirm"), self.tr("delete_image")) == QMessageBox.StandardButton.Yes:
            self.catalog.delete(self.selected_image); self.selected_image = None; self.preview.setText(self.tr("select_image")); self.refresh_images()

    def run_ocr(self) -> None:
        if self.required() and (not getattr(self, "recognition_worker", None) or not self.recognition_worker.isRunning()):
            self.select_image_path(self.selected_image)

    def run_barcodes(self) -> None:
        if self.required() and (not getattr(self, "recognition_worker", None) or not self.recognition_worker.isRunning()):
            self.select_image_path(self.selected_image)

    def run_ai(self) -> None:
        if self.selected_image and self.agent_select.currentData():
            try: self.ai_result.setPlainText(self.service.recognize_ai(self.agent_select.currentData(), self.selected_image))
            except RuntimeError as error: self.ai_result.setPlainText(str(error))

    def refresh_agents(self) -> None:
        self.agent_select.clear(); agents = self.service.ai_agents(); self.agent_select.addItem(self.tr("no_profiles"), "")
        for agent in agents: self.agent_select.addItem(agent["name"], agent["id"])

    def agent_changed(self) -> None:
        if not getattr(self, "recognition_worker", None) or not self.recognition_worker.isRunning():
            self.ai_result.setDisabled(not bool(self.agent_select.currentData()))

    def save_agent(self) -> None:
        if not all((self.agent_name.text().strip(), self.model.text().strip(), self.token.text())): QMessageBox.warning(self, self.tr("error"), self.tr("profile_required")); return
        self.service.save_ai_agent(self.agent_name.text().strip(), self.provider.currentText(), self.model.text().strip(), self.token.text()); self.agent_name.clear(); self.token.clear(); self.refresh_agents()

    def open_folder(self) -> None:
        if self.service.image_directory(): QDesktopServices.openUrl(self.service.image_directory().as_uri())

    def choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("choose_folder"), self.settings_folder_path.text() if hasattr(self, "settings_folder_path") else str(self.service.image_directory() or ""))
        if path and hasattr(self, "settings_folder_path"): self.settings_folder_path.setText(path)

    def save_interface_settings(self) -> None:
        self.service.save_locale(self.language.currentData()); QMessageBox.information(self, self.tr("settings"), self.tr("restart_language"))

    def save_folder_settings(self) -> None:
        try:
            self.service.save_settings(Path(self.settings_folder_path.text()))
        except ValueError:
            QMessageBox.warning(self, self.tr("error"), self.tr("folder_missing")); return
        self.image_page = 1; self.selected_image = None; self.refresh_images()

    def save_update_settings(self) -> None:
        self.service.save_update_repository(self.github_repository.text()); QMessageBox.information(self, self.tr("settings"), self.tr("settings_saved"))

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
        popular = self.service.popular_models()
        popular_ids = {item["id"] for item in popular}
        for item in [*popular, *(item for item in self.service.models() if item["id"] not in popular_ids)]:
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
        try:
            if existing is None:
                self.service.add_device(data)
            else:
                self.service.update_device(existing["id"], data)
        except ValueError as error:
            self.error(self.tr(str(error)))
            return
        self.refresh_equipment(); self.refresh_statistics()
        dialog.accept()

    def refresh_equipment(self) -> None:
        date_from = self.date_from.date().toString("yyyy-MM-dd") if self.date_from.date().year() > 2000 else ""; date_to = self.date_to.date().toString("yyyy-MM-dd") if self.date_to.date().year() > 2000 else ""
        rows, self.equipment_pagination = self.service.devices(self.device_search.text().strip(), self.type_filter.currentData(), self.service_filter.currentData(), date_from, date_to, self.model_filter.currentData() or None, self.operation_filter.currentData(), getattr(self, "equipment_page", 1)); self.current_devices = rows; self.devices_table.setRowCount(len(rows)); pagination = self.equipment_pagination; self.equipment_page_label.setText(str(self.equipment_page) if pagination is None else str(pagination["page"]) + "/" + str(pagination["pages"])); self.equipment_previous.setEnabled(pagination is not None and pagination["page"] > 1); self.equipment_next.setEnabled(pagination is not None and pagination["page"] < pagination["pages"]); self.equipment_page = 1 if pagination is None else pagination["page"]
        for row, device in enumerate(rows):
            self.fill(self.devices_table, row, [self.service.display_time(device["registered_at"]), device["contract_number"] or "", self.tr(device["operation_type"]), device["recognized_text"], device["model_name"], self.tr(device["device_type"]), self.tr(device["service"]), device["source_image_path"] or "", ""]); self.devices_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, device["id"])
            actions = QWidget(); action_layout = QHBoxLayout(actions); action_layout.setContentsMargins(2, 0, 2, 0); edit = button(actions, "edit", self.tr("edit")); edit.clicked.connect(lambda _, index=row: self.edit_equipment(index)); delete = button(actions, "delete", self.tr("delete")); delete.clicked.connect(lambda _, index=row: self.delete_equipment(index)); action_layout.addWidget(edit); source = button(actions, "folder", self.tr("open_source_image")); source.clicked.connect(lambda _, index=row: self.open_source_image(index)); action_layout.addWidget(source); action_layout.addWidget(delete); self.devices_table.setCellWidget(row, 8, actions)

    def change_equipment_page(self, offset: int) -> None:
        if self.equipment_pagination is None:
            return
        self.equipment_page = max(1, self.equipment_page + offset)
        self.refresh_equipment()

    def edit_equipment(self, row: int) -> None:
        self.open_equipment_dialog(self.current_devices[row]["recognized_text"], self.current_devices[row])

    def open_source_image(self, row: int) -> None:
        path = Path(str(self.current_devices[row]["source_image_path"] or ""))
        if not path.is_file():
            QMessageBox.warning(self, self.tr("error"), self.tr("source_image_missing"))
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def delete_equipment(self, row: int) -> None:
        device = self.current_devices[row]
        if QMessageBox.question(self, self.tr("confirm"), self.tr("delete_device")) == QMessageBox.StandardButton.Yes:
            self.service.delete_device(device["id"]); self.refresh_equipment(); self.refresh_statistics()

    def export_equipment(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("export"), "equipment.csv", "CSV (*.csv)")
        if path:
            date_from = self.date_from.date().toString("yyyy-MM-dd") if self.date_from.date().year() > 2000 else ""
            date_to = self.date_to.date().toString("yyyy-MM-dd") if self.date_to.date().year() > 2000 else ""
            rows = self.service.all_filtered_devices(self.device_search.text().strip(), self.type_filter.currentData(), self.service_filter.currentData(), date_from, date_to, self.model_filter.currentData() or None, self.operation_filter.currentData())
            self.service.export_devices(Path(path), rows)

    def refresh_models(self) -> None:
        rows = self.service.models(); self.models_table.setRowCount(len(rows)); self.model_filter.clear(); self.model_filter.addItem(self.tr("model"), "")
        for row, model in enumerate(rows):
            self.fill(self.models_table, row, [model["name"], self.tr(model["device_type"]), self.tr(model["service"])]); self.models_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, model["id"])
            self.model_filter.addItem(model["name"], model["id"])

    def add_model(self) -> None:
        if self.model_name.text().strip():
            try:
                self.service.add_model(self.model_name.text().strip(), self.model_type.currentData(), self.model_service.currentData())
            except ValueError as error:
                self.error(self.tr(str(error)))
                return
            self.model_name.clear()
            self.refresh_models()

    def delete_selected_model(self) -> None:
        item = self.models_table.item(self.models_table.currentRow(), 0)
        if item and QMessageBox.question(self, self.tr("confirm"), self.tr("delete_model")) == QMessageBox.StandardButton.Yes:
            try: self.service.delete_model(item.data(Qt.ItemDataRole.UserRole)); self.refresh_models()
            except Exception as error: self.error(str(error))

    def refresh_statistics(self) -> None:
        summary = self.service.statistics_summary(self.statistics_mode.currentData())
        operations = summary["operations"]
        self.statistics_table.setRowCount(len(operations))
        categories = [self.period_label(period) for period in operations]
        receipt = [values["receipt"] for values in operations.values()]
        issue = [values["issue"] for values in operations.values()]
        for index, (period, values) in enumerate(operations.items()):
            self.fill(self.statistics_table, index, [self.period_label(period), values["receipt"], values["issue"], values["receipt"] + values["issue"]])
        self.operations_chart.setChart(self.make_bar_chart(self.tr("operation"), categories, [(self.tr("receipt"), receipt), (self.tr("issue"), issue)]))
        services = summary["services"]
        self.services_chart.setChart(self.make_bar_chart(self.tr("service"), [self.tr(key) for key in services], [(self.tr("service"), list(services.values()))]))
        models = dict(list(summary["models"].items())[:10])
        self.models_chart.setChart(self.make_bar_chart(self.tr("models"), list(models.keys()), [(self.tr("models"), list(models.values()))]))

    def error(self, message: str) -> None:
        QMessageBox.warning(self, self.tr("error"), message)

    @staticmethod
    def table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.horizontalHeader().setStretchLastSection(True); return table

    @staticmethod
    def fill(table: QTableWidget, row: int, values: list[object]) -> None:
        for column, value in enumerate(values): table.setItem(row, column, QTableWidgetItem(str(value)))
