from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from serial_vision.i18n import t
from serial_vision.ui.buttons import button

Field = QLineEdit | QComboBox | QCheckBox | QTextEdit | QListWidget


class WarehouseForm(QDialog):
    def __init__(self, parent: QWidget, locale: str, title: str) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.locale_code = locale
        self.fields: dict[str, Field] = {}
        self.setWindowTitle(t(locale, title))
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.addLayout(self.form)
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.feedback)
        actions = QHBoxLayout()
        self.save = button(self, "save", t(locale, "save"))
        close = button(self, "close", t(locale, "cancel"))
        close.clicked.connect(self.reject)
        actions.addStretch()
        actions.addWidget(self.save)
        actions.addWidget(close)
        layout.addLayout(actions)

    def line(self, key: str, label: str, value: object = "", secret: bool = False) -> QLineEdit:
        control = QLineEdit(str(value), self)
        control.setAccessibleName(t(self.locale_code, label))
        control.setMaxLength(4096 if key == "value" else 1000)
        if secret:
            control.setEchoMode(QLineEdit.EchoMode.Password)
        self.fields[key] = control
        self.form.addRow(t(self.locale_code, label), control)
        return control

    def multiline(self, key: str, label: str, value: str = "") -> QTextEdit:
        control = QTextEdit(self)
        control.setPlainText(value)
        control.setAccessibleName(t(self.locale_code, label))
        self.fields[key] = control
        self.form.addRow(t(self.locale_code, label), control)
        return control

    def choice(
        self, key: str, label: str, choices: list[tuple[str, str]], selected: str = ""
    ) -> QComboBox:
        control = QComboBox(self)
        control.setAccessibleName(t(self.locale_code, label))
        for caption, code in choices:
            control.addItem(caption, code)
        if selected:
            control.setCurrentIndex(max(0, control.findData(selected)))
        self.fields[key] = control
        self.form.addRow(t(self.locale_code, label), control)
        return control

    def boolean(self, key: str, label: str, value: bool = True) -> None:
        control = QCheckBox(t(self.locale_code, label), self)
        control.setChecked(value)
        self.fields[key] = control
        self.form.addRow(control)

    def multiple(
        self, key: str, label: str, choices: list[tuple[str, str]], selected: list[str]
    ) -> None:
        control = QListWidget(self)
        control.setAccessibleName(t(self.locale_code, label))
        for caption, code in choices:
            item = QListWidgetItem(caption, control)
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if code in selected else Qt.CheckState.Unchecked
            )
        self.fields[key] = control
        self.form.addRow(t(self.locale_code, label), control)

    def values(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for key, control in self.fields.items():
            if isinstance(control, QLineEdit):
                values[key] = control.text()  # Passwords are never stripped or persisted locally.
            elif isinstance(control, QComboBox):
                values[key] = control.currentData()
            elif isinstance(control, QCheckBox):
                values[key] = control.isChecked()
            elif isinstance(control, QTextEdit):
                values[key] = control.toPlainText()
            else:
                values[key] = [
                    control.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(control.count())
                    if control.item(i).checkState() == Qt.CheckState.Checked
                ]
        return values

    def submit(self, handler: Callable[[dict[str, object]], None]) -> None:
        self.save.clicked.connect(lambda: handler(self.values()))
        self.show()
