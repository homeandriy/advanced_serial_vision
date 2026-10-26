from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serial_vision.application_service import SerialVisionService
from serial_vision.i18n import SUPPORTED_LOCALES, error_message
from serial_vision.settings import SettingsSaveError, SettingsValues
from serial_vision.ui.buttons import button
from serial_vision.ui.pages.base import Page


class SettingsPage(Page):
    saved = Signal(object, object)
    dirty_changed = Signal(bool)
    agents_changed = Signal()

    def __init__(
        self,
        service: SerialVisionService,
        locale: str,
        configure_api: Callable[[bool, int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(service, locale, parent)
        self.configure_api = configure_api
        self.agents = self.service.ai_agents()
        self.install(self.settings())
        self.refresh_agent_profiles()

    def refresh_agents(self) -> None:
        self.agents = self.service.ai_agents()
        self.refresh_agent_profiles()
        self.agents_changed.emit()

    def settings(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(
            self.help_button("settings", "settings"), alignment=Qt.AlignmentFlag.AlignRight
        )
        interface = QGroupBox(self.translate("interface_settings"))
        interface_form = QFormLayout(interface)
        self.language = QComboBox()
        for code, name in (("uk", "Українська"), ("en", "English"), ("pl", "Polski")):
            self.language.addItem(name, code)
        self.language.setCurrentIndex(SUPPORTED_LOCALES.index(self.ui_locale))
        interface_form.addRow(self.translate("language"), self.language)
        layout.addWidget(interface)

        folder_group = QGroupBox(self.translate("folder_settings"))
        folder_form = QFormLayout(folder_group)
        self.settings_folder_path = QLineEdit(str(self.service.image_directory() or ""))
        self.settings_folder_path.setReadOnly(True)
        choose = button(folder_group, "folder", self.translate("choose_folder"))
        choose.clicked.connect(self.choose_folder)
        folder_form.addRow(self.translate("image_folder"), self.settings_folder_path)
        folder_form.addRow(choose)
        layout.addWidget(folder_group)

        appearance = QGroupBox(self.translate("appearance_settings"))
        appearance_form = QFormLayout(appearance)
        self.theme_choice = QComboBox()
        self.theme_choice.addItem(self.translate("theme_system"), "system")
        self.theme_choice.addItem(self.translate("theme_light"), "light")
        self.theme_choice.addItem(self.translate("theme_dark"), "dark")
        self.theme_choice.setCurrentIndex(max(0, self.theme_choice.findData(self.service.theme())))
        self.icon_style_choice = QComboBox()
        self.icon_style_choice.addItem(self.translate("icon_style_system"), "system")
        self.icon_style_choice.addItem(self.translate("icon_style_modern"), "modern")
        self.icon_style_choice.addItem(self.translate("icon_style_classic"), "classic")
        self.icon_style_choice.addItem(self.translate("icon_style_windows98"), "windows98")
        self.icon_style_choice.addItem(self.translate("icon_style_ubuntu22"), "ubuntu22")
        self.icon_style_choice.setCurrentIndex(
            max(0, self.icon_style_choice.findData(self.service.icon_style()))
        )
        appearance_form.addRow(self.translate("theme"), self.theme_choice)
        appearance_form.addRow(self.translate("icon_style"), self.icon_style_choice)
        layout.addWidget(appearance)

        recognition_group = QGroupBox(self.translate("recognition_strategies"))
        recognition_form = QFormLayout(recognition_group)
        options = self.service.recognition_options()
        original_info = QLabel(self.translate("recognition_original_info"))
        original_info.setWordWrap(True)
        recognition_form.addRow(original_info)
        self.recognition_rotate = QCheckBox(self.translate("recognition_rotate"))
        self.recognition_rotate.setChecked(options.rotate)
        recognition_form.addRow(self.recognition_rotate)
        self.recognition_enhance = QCheckBox(self.translate("recognition_enhance"))
        self.recognition_enhance.setChecked(options.enhance)
        recognition_form.addRow(self.recognition_enhance)
        layout.addWidget(recognition_group)

        api = QGroupBox(self.translate("api_integrations"))
        api_form = QFormLayout(api)
        self.api_enabled = QCheckBox(self.translate("api_enabled"))
        self.api_enabled.setChecked(self.service.api_enabled())
        self.api_port = QLineEdit(str(self.service.api_port()))
        api_form.addRow(self.api_enabled)
        api_form.addRow(self.translate("api_port"), self.api_port)
        layout.addWidget(api)

        profiles = QGroupBox(self.translate("ai_profiles"))
        agent = QVBoxLayout(profiles)
        self.agent_profiles = self.table(
            [self.translate("profile_name"), self.translate("provider"), self.translate("model")]
        )
        self.agent_profiles.cellDoubleClicked.connect(lambda *_: self.edit_selected_agent())
        agent.addWidget(self.agent_profiles)
        actions = QHBoxLayout()
        add = button(profiles, "save", self.translate("add_profile"))
        add.clicked.connect(self.add_agent)
        edit = button(profiles, "edit", self.translate("edit_profile"))
        edit.clicked.connect(self.edit_selected_agent)
        remove = button(profiles, "delete", self.translate("remove_profile"))
        remove.clicked.connect(self.delete_selected_agent)
        actions.addWidget(add)
        actions.addWidget(edit)
        actions.addWidget(remove)
        actions.addStretch()
        agent.addLayout(actions)
        layout.addWidget(profiles)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.addWidget(scroll, 1)
        save_bar = QHBoxLayout()
        self.settings_status = QLabel(self.translate("settings_saved"))
        self.settings_status.setObjectName("settingsStatus")
        save_bar.addWidget(self.settings_status, 1)
        self.settings_save = button(container, "save", self.translate("save_settings"))
        self.settings_save.setEnabled(False)
        self.settings_save.clicked.connect(self.save_all_settings)
        save_bar.addWidget(self.settings_save)
        outer.addLayout(save_bar)
        self._settings_saved_values = self.settings_values()
        for control in (self.language, self.theme_choice, self.icon_style_choice):
            control.currentIndexChanged.connect(self.settings_changed)
        for check_control in (self.recognition_rotate, self.recognition_enhance, self.api_enabled):
            check_control.toggled.connect(self.settings_changed)
        for text_control in (self.settings_folder_path, self.api_port):
            text_control.textChanged.connect(self.settings_changed)
        return container

    def settings_values(self) -> SettingsValues:
        return SettingsValues(
            locale=str(self.language.currentData()),
            image_directory=self.settings_folder_path.text(),
            theme=str(self.theme_choice.currentData()),
            icon_style=str(self.icon_style_choice.currentData()),
            rotate=self.recognition_rotate.isChecked(),
            enhance=self.recognition_enhance.isChecked(),
            api_enabled=self.api_enabled.isChecked(),
            api_port=self.api_port.text().strip(),
        )

    def settings_changed(self, *_args) -> None:
        dirty = self.settings_values() != self._settings_saved_values
        self.settings_save.setEnabled(dirty)
        self.settings_status.setText(
            self.translate("settings_unsaved" if dirty else "settings_saved")
        )
        self.settings_status.setProperty("state", "dirty" if dirty else "saved")
        self.settings_status.style().unpolish(self.settings_status)
        self.settings_status.style().polish(self.settings_status)
        self.dirty_changed.emit(dirty)

    def save_all_settings(self) -> None:
        current = self.settings_values()
        previous = self._settings_saved_values
        try:
            self.service.save_all_settings(current, self.configure_api)
        except (ValueError, OSError, SettingsSaveError) as error:
            self.settings_status.setText(
                self.translate("settings_save_failed", error=error_message(self.ui_locale, error))
            )
            if str(error) == "api_port_invalid":
                self.api_port.setFocus()
            self.service.log_startup(f"Settings save failed: {error!r}")
            return
        self._settings_saved_values = current
        self.settings_changed()
        self.saved.emit(current, previous)
        if current.locale != previous.locale:
            self.settings_status.setText(self.translate("restart_language"))

    def refresh_agent_profiles(self) -> None:
        self.agent_profiles.setRowCount(len(self.agents))
        for row, agent in enumerate(self.agents):
            for column, value in enumerate((agent["name"], agent["provider"], agent["model"])):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, agent["id"])
                self.agent_profiles.setItem(row, column, item)

    def selected_agent_id(self) -> str | None:
        row = self.agent_profiles.currentRow()
        item = self.agent_profiles.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def add_agent(self) -> None:
        self.edit_agent_dialog()

    def edit_selected_agent(self) -> None:
        agent_id = self.selected_agent_id()
        agent = next((row for row in self.agents if row["id"] == agent_id), None)
        if agent is None:
            QMessageBox.warning(self, self.translate("error"), self.translate("profile_required"))
            return
        self.edit_agent_dialog(agent)

    def delete_selected_agent(self) -> None:
        agent_id = self.selected_agent_id()
        if not agent_id:
            QMessageBox.warning(self, self.translate("error"), self.translate("profile_required"))
            return
        if (
            QMessageBox.question(self, self.translate("confirm"), self.translate("delete_profile"))
            == QMessageBox.StandardButton.Yes
        ):
            self.service.delete_ai_agent(agent_id)
            self.refresh_agents()

    def edit_agent_dialog(self, existing=None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self.translate("edit_profile") if existing else self.translate("add_profile")
        )
        form = QFormLayout(dialog)
        name = QLineEdit(existing["name"] if existing else "")
        provider = QComboBox()
        provider.addItems(["openai", "anthropic", "gemini"])
        provider.setCurrentText(existing["provider"] if existing else "openai")
        model = QLineEdit(existing["model"] if existing else "gpt-4.1-mini")
        token = QLineEdit()
        token.setEchoMode(QLineEdit.EchoMode.Password)
        if existing:
            token.setPlaceholderText(self.translate("api_key_optional"))
        form.addRow(self.translate("profile_name"), name)
        form.addRow(self.translate("provider"), provider)
        form.addRow(self.translate("model"), model)
        form.addRow(self.translate("api_key"), token)
        save = button(dialog, "save", self.translate("save"))
        save.clicked.connect(dialog.accept)
        form.addRow(save)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if (
            not name.text().strip()
            or not model.text().strip()
            or (existing is None and not token.text())
        ):
            QMessageBox.warning(
                self, self.translate("error"), self.translate("profile_key_required")
            )
            return
        try:
            if existing:
                self.service.update_ai_agent(
                    existing["id"],
                    name.text().strip(),
                    provider.currentText(),
                    model.text().strip(),
                    token.text(),
                )
            else:
                self.service.save_ai_agent(
                    name.text().strip(), provider.currentText(), model.text().strip(), token.text()
                )
        except ValueError as error:
            QMessageBox.warning(self, self.translate("error"), self.translate(str(error)))
            return
        self.refresh_agents()

    def choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            self.translate("choose_folder"),
            self.settings_folder_path.text()
            if hasattr(self, "settings_folder_path")
            else str(self.service.image_directory() or ""),
        )
        if path and hasattr(self, "settings_folder_path"):
            self.settings_folder_path.setText(path)
