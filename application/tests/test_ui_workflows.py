from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication, QPushButton

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.recognition_strategies import RecognitionOptions
from serial_vision.ui.main_window import MainWindow, RecognitionWorker
from serial_vision.ui.photo_preview import PhotoPreview
from serial_vision.updates import ReleaseInfo


class UiWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = Database(self.root / "database.sqlite3")
        self.database.set_setting("license_accepted", "yes")
        self.database.set_setting("image_directory", str(self.root))
        self.window = MainWindow(SerialVisionService(self.database))

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_preview_recalculates_fit_and_100_percent_zoom(self) -> None:
        path = self.root / "image.png"
        Image.new("RGB", (1200, 800), "white").save(path)
        preview = PhotoPreview("Empty")
        preview.resize(300, 200)
        preview.show()
        self.app.processEvents()
        self.assertTrue(preview.set_image(path))
        self.assertLess(preview.transform().m11(), 1)
        preview.zoom_actual()
        self.assertAlmostEqual(1, preview.transform().m11())
        preview.zoom_to_fit()
        self.assertLess(preview.transform().m11(), 1)
        preview.close()

    def test_selected_photo_actions_are_on_preview_toolbar(self) -> None:
        photos = self.window.image_splitter.parentWidget()
        gallery_actions = photos.layout().itemAt(1).layout()
        self.assertEqual(
            [self.window.tr("refresh"), self.window.tr("delete")],
            [gallery_actions.itemAt(index).widget().text() for index in range(gallery_actions.count())],
        )
        preview_panel = self.window.preview.parentWidget()
        preview_actions = preview_panel.layout().itemAt(0).layout()
        captions = [preview_actions.itemAt(index).widget().text()
                    for index in range(preview_actions.count()) if preview_actions.itemAt(index).widget()]
        self.assertEqual(
            [self.window.tr(key) for key in ("open_image", "editor", "rotate", "fit_image", "actual_size")],
            captions,
        )

    def test_image_refresh_preserves_visible_selection_and_page_change_clears_it(self) -> None:
        for index in range(49):
            Image.new("RGB", (16, 16), "white").save(self.root / f"photo_{index:02}.png")
        self.window.refresh_images()
        selected = next(iter(self.window._image_buttons))
        self.window.selected_image = selected
        self.window.preview.set_image(selected)
        self.window.refresh_images()
        self.assertTrue(self.window._image_buttons[selected].isChecked())
        self.window.change_image_page(1)
        self.assertIsNone(self.window.selected_image)
        self.assertIsNone(self.window.preview._photo)
        self.assertFalse(self.window.retry_button.isEnabled())

    def test_settings_mark_unsaved_changes(self) -> None:
        self.assertFalse(self.window.settings_save.isEnabled())
        self.window.theme_choice.setCurrentIndex(1)
        self.assertTrue(self.window.settings_save.isEnabled())
        self.assertIn("*", self.window.tabs.tabText(self.window.tabs.indexOf(self.window.settings_page)))

    def test_one_settings_action_saves_recognition_options(self) -> None:
        self.window.recognition_rotate.setChecked(False)
        self.assertTrue(self.window.settings_save.isEnabled())
        self.window.save_all_settings()
        self.assertFalse(self.window.settings_save.isEnabled())
        self.assertEqual(RecognitionOptions(rotate=False, enhance=True), self.window.service.recognition_options())

    def test_theme_can_be_saved_without_changing_an_unset_photo_folder(self) -> None:
        self.window.settings_folder_path.setText("")
        self.window._settings_saved_values = self.window.settings_values()
        self.window.theme_choice.setCurrentIndex(1)
        self.window.save_all_settings()
        self.assertEqual("light", self.window.service.theme())
        self.assertFalse(self.window.settings_save.isEnabled())

    def test_ai_action_stays_disabled_without_a_profile_after_recognition(self) -> None:
        self.window.selected_image = self.root / "image.png"
        self.window.set_recognition_busy(True)
        self.window.set_recognition_busy(False)
        self.assertFalse(self.window.ai_button.isEnabled())
        self.assertFalse(self.window.ai_result.isEnabled())

    def test_update_checks_repeat_and_respect_later_until_manual_check(self) -> None:
        self.assertTrue(self.window.update_check_timer.isActive())
        self.assertEqual(4 * 60 * 60 * 1_000, self.window.update_check_timer.interval())
        release = ReleaseInfo("0.7.0", "Changes", "https://example.test/setup.exe")
        self.window._dismissed_update_version = release.version
        with patch.object(self.window, "show_update_dialog") as show_dialog:
            self.window.update_checked(release, show_status=False)
            show_dialog.assert_not_called()
            self.window.update_checked(release, show_status=True)
            show_dialog.assert_called_once_with(release)

    def test_cancelled_recognition_skips_second_stage(self) -> None:
        worker = RecognitionWorker(self.root / "image.png", "eng", "OCR", "Unavailable", RecognitionOptions())
        cancelled = []
        stages = []
        worker.cancelled.connect(cancelled.append)
        worker.stage.connect(stages.append)
        with patch("serial_vision.ui.main_window.RapidOcrRecognizer") as ocr, patch("serial_vision.ui.main_window.BarcodeRecognizer") as barcode, patch.object(worker, "isInterruptionRequested", side_effect=[False, True]):
            ocr.return_value.recognize.return_value = "text"
            worker.run()
            barcode.return_value.recognize.assert_not_called()
        self.assertEqual(["ocr"], stages)
        self.assertEqual([str(self.root / "image.png")], cancelled)

    def test_equipment_row_keeps_edit_visible_and_delete_in_menu(self) -> None:
        model = self.window.service.models()[0]
        self.window.service.add_device({
            "recognized_text": "SN-UI-TEST", "contract_number": "", "operation_type": "receipt",
            "source_image_path": "", "device_model_id": model["id"],
            "registered_at": "2026-10-14T12:00:00",
        })
        self.window.refresh_equipment()
        controls = self.window.devices_table.cellWidget(0, 8).findChildren(QPushButton)
        self.assertEqual({self.window.tr("edit"), self.window.tr("actions")}, {control.text() for control in controls})
        menu = next(control.menu() for control in controls if control.menu() is not None)
        self.assertEqual(self.window.tr("delete"), menu.actions()[-1].text())
        self.assertTrue(menu.actions()[-2].isSeparator())

    def test_selected_photo_opens_separate_editor(self) -> None:
        image = self.root / "label.png"
        Image.new("RGB", (120, 80), "white").save(image)
        self.window.selected_image = image
        self.window.edit_image()
        dialog = self.window.image_editor
        self.assertTrue(dialog.isVisible())
        self.assertEqual(image, dialog.session.source)
        dialog.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
