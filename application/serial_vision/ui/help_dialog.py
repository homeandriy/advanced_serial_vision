from __future__ import annotations

import re
from importlib.resources import files

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QTextBrowser, QVBoxLayout, QWidget

from serial_vision.i18n import t
from serial_vision.ui.buttons import button


SECTION_PATTERN = re.compile(r"<!-- section: ([a-z-]+) -->\s*")


class HelpDialog(QDialog):
    """Localized, navigable in-app help sourced from packaged Markdown files."""

    def __init__(self, locale: str, section_id: str | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.locale = locale
        self.setWindowTitle("Serial Vision — " + t(locale, "help"))
        self.resize(1080, 760)
        self.sections = self._sections(locale)
        layout = QVBoxLayout(self)
        content = QHBoxLayout()
        self.contents = QListWidget(self)
        self.contents.setMinimumWidth(250)
        self.contents.setMaximumWidth(340)
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        content.addWidget(self.contents)
        content.addWidget(self.browser, 1)
        layout.addLayout(content, 1)
        for identifier, title, _ in self.sections:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            self.contents.addItem(item)
        self.contents.currentItemChanged.connect(self._show_selected_section)
        close = button(self, "close", t(locale, "close"))
        close.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(close)
        layout.addLayout(actions)
        target_row = next((index for index, item in enumerate(self.sections) if item[0] == section_id), 0)
        self.contents.setCurrentRow(target_row)

    @staticmethod
    def _sections(locale: str) -> list[tuple[str, str, str]]:
        language = locale if locale in {"uk", "en", "pl"} else "uk"
        help_assets = files("serial_vision").joinpath("assets", "help")
        markdown = help_assets.joinpath(f"{language}.md").read_text(encoding="utf-8")
        if language == "uk":
            markdown += help_assets.joinpath("uk-extra.md").read_text(encoding="utf-8")
        parts = SECTION_PATTERN.split(markdown)
        sections: list[tuple[str, str, str]] = []
        for index in range(1, len(parts), 2):
            identifier, body = parts[index], parts[index + 1].strip()
            title = next((line.removeprefix("## ") for line in body.splitlines() if line.startswith("## ")), identifier)
            sections.append((identifier, title, body))
        return sections

    def _show_selected_section(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        identifier = str(item.data(Qt.ItemDataRole.UserRole))
        body = next((content for key, _, content in self.sections if key == identifier), "")
        self.browser.setMarkdown(body)
        self.browser.verticalScrollBar().setValue(0)
