from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.recognition_strategies import RecognitionOptions
from serial_vision.ui.main_window import MainWindow
from serial_vision.ui.photo_preview import PhotoPreview
from serial_vision.ui.workers import AiRecognitionWorker, RecognitionWorker
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
            [
                gallery_actions.itemAt(index).widget().text()
                for index in range(gallery_actions.count())
            ],
        )
        preview_panel = self.window.preview.parentWidget()
        preview_actions = preview_panel.layout().itemAt(0).layout()
        captions = [
            preview_actions.itemAt(index).widget().text()
            for index in range(preview_actions.count())
            if preview_actions.itemAt(index).widget()
        ]
        self.assertEqual(
            [
                self.window.tr(key)
                for key in ("open_image", "editor", "rotate", "fit_image", "actual_size")
            ],
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
        self.assertIn(
            "*", self.window.tabs.tabText(self.window.tabs.indexOf(self.window.settings_page))
        )

    def test_one_settings_action_saves_recognition_options(self) -> None:
        self.window.recognition_rotate.setChecked(False)
        self.assertTrue(self.window.settings_save.isEnabled())
        self.window.save_all_settings()
        self.assertFalse(self.window.settings_save.isEnabled())
        self.assertEqual(
            RecognitionOptions(rotate=False, enhance=True),
            self.window.service.recognition_options(),
        )

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

    def test_update_checksum_errors_are_localized_in_status_and_dialog(self) -> None:
        self.window.update_close = QPushButton(self.window)
        self.window.update_download_status = QLabel(self.window)
        for language in ("uk", "en", "pl"):
            self.window.locale = language
            for code in ("update_checksum_unavailable", "update_integrity_failed"):
                with (
                    self.subTest(language=language, code=code),
                    patch("serial_vision.ui.main_window.QMessageBox.warning") as warning,
                ):
                    self.window.update_download_failed(code)
                    expected = self.window.tr("update_download_failed", error=self.window.tr(code))
                    self.assertEqual(expected, self.window.update_download_status.text())
                    self.assertEqual(expected, warning.call_args.args[2])
                    self.assertNotIn(code, expected)

    def test_cancelled_recognition_skips_second_stage(self) -> None:
        worker = RecognitionWorker(
            self.root / "image.png", "eng", "OCR", "Unavailable", RecognitionOptions()
        )
        cancelled = []
        stages = []
        worker.cancelled.connect(cancelled.append)
        worker.stage.connect(stages.append)
        with (
            patch("serial_vision.ui.workers.RapidOcrRecognizer") as ocr,
            patch("serial_vision.ui.workers.BarcodeRecognizer") as barcode,
            patch.object(worker, "isInterruptionRequested", side_effect=[False, True]),
        ):
            ocr.return_value.recognize.return_value = "text"
            worker.run()
            barcode.return_value.recognize.assert_not_called()
        self.assertEqual(["ocr"], stages)
        self.assertEqual([str(self.root / "image.png")], cancelled)

    def test_unreadable_photo_releases_recognition_busy_state(self) -> None:
        self.window.selected_image = self.root / "missing.jpg"
        with (
            patch("serial_vision.ui.workers.RapidOcrRecognizer") as ocr,
            patch("serial_vision.ui.workers.BarcodeRecognizer") as barcode,
            patch.object(RecognitionWorker, "start"),
        ):
            ocr.return_value.recognize.side_effect = FileNotFoundError("photo missing")
            barcode.return_value.recognize.side_effect = OSError("photo unreadable")
            self.window.start_recognition()
            worker = self.window.recognition_worker
            worker.run()
            self.assertFalse(self.window._recognition_busy)
            self.assertTrue(self.window.retry_button.isEnabled())
            self.assertIn("photo missing", self.window.ocr_result.toPlainText())
            worker.finished.emit()

    def test_old_ai_success_and_failure_cannot_replace_new_photo_results(self) -> None:
        for outcome in ("completed", "failed"):
            with self.subTest(outcome=outcome), patch.object(AiRecognitionWorker, "start"):
                self.window.agent_select.clear()
                self.window.agent_select.addItem("Profile", "profile-id")
                self.window.selected_image = self.root / "A.jpg"
                self.window.run_ai()
                worker = self.window.ai_worker
                self.window.clear_image_selection()
                self.window.selected_image = self.root / "B.jpg"
                self.window.ai_result.setPlainText("B RESULT")
                getattr(worker, outcome).emit("A RESULT")
                self.assertEqual("B RESULT", self.window.ai_result.toPlainText())
                self.assertFalse(self.window.ai_button.isEnabled())
                worker.finished.emit()
                self.assertTrue(self.window.ai_button.isEnabled())

    def test_ai_reply_is_ignored_after_switching_back_to_same_photo(self) -> None:
        with patch.object(AiRecognitionWorker, "start"):
            self.window.agent_select.addItem("Profile", "profile-id")
            self.window.agent_select.setCurrentIndex(1)
            self.window.selected_image = self.root / "A.jpg"
            self.window.run_ai()
            worker = self.window.ai_worker
            self.window.clear_image_selection()
            self.window.selected_image = self.root / "A.jpg"
            worker.completed.emit("STALE A")
            self.assertNotEqual("STALE A", self.window.ai_result.toPlainText())
            worker.finished.emit()

    def test_exit_stops_services_and_quits(self) -> None:
        self.window.show()
        with (
            patch.object(self.window, "stop_camera") as stop_camera,
            patch.object(self.window.local_api, "stop") as stop_api,
            patch.object(QApplication, "quit") as quit_app,
        ):
            self.window.close()
            stop_camera.assert_called_once()
            stop_api.assert_called_once()
            quit_app.assert_called_once()
        self.assertFalse(self.window.update_check_timer.isActive())
        self.assertFalse(self.window.isVisible())

    def test_qt_event_loop_exits_after_worker_finishes(self) -> None:
        script = """
import tempfile
from pathlib import Path
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication
from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.ui.main_window import MainWindow

class SlowWorker(QThread):
    def run(self):
        self.msleep(150)

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory() as folder:
    db = Database(Path(folder) / "test.sqlite3")
    db.set_setting("license_accepted", "yes")
    db.set_setting("image_directory", folder)
    window = MainWindow(SerialVisionService(db))
    worker = SlowWorker(window)
    worker.start()
    window.show()
    QTimer.singleShot(10, window.close)
    QTimer.singleShot(3000, lambda: app.exit(2))
    result = app.exec()
    assert not worker.isRunning()
    assert not window.update_check_timer.isActive()
    raise SystemExit(result)
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_exit_waits_for_running_worker_without_terminating_it(self) -> None:
        worker = QThread(self.window)
        self.window.show()
        with (
            patch.object(worker, "isRunning", return_value=True),
            patch.object(worker, "requestInterruption") as interrupt,
            patch.object(QApplication, "quit") as quit_app,
        ):
            self.window.close()
            interrupt.assert_called_once()
            quit_app.assert_not_called()
            self.assertTrue(self.window._shutdown_timer.isActive())
        with patch.object(QApplication, "quit") as quit_app:
            QTest.qWait(100)
            quit_app.assert_called_once()
        self.assertFalse(self.window._shutdown_timer.isActive())

    def test_equipment_filters_have_associated_accessible_labels(self) -> None:
        controls = (
            self.window.date_from,
            self.window.date_to,
            self.window.model_filter,
            self.window.operation_filter,
            self.window.type_filter,
            self.window.service_filter,
            self.window.device_search,
        )
        labels = self.window.findChildren(QLabel)
        for control in controls:
            with self.subTest(control=control):
                self.assertTrue(control.accessibleName())
                self.assertTrue(any(label.buddy() is control for label in labels))

    def test_equipment_row_keeps_edit_visible_and_delete_in_menu(self) -> None:
        model = self.window.service.models()[0]
        self.window.service.add_device(
            {
                "recognized_text": "SN-UI-TEST",
                "contract_number": "",
                "operation_type": "receipt",
                "source_image_path": "",
                "device_model_id": model["id"],
                "registered_at": "2026-10-14T12:00:00",
            }
        )
        self.window.refresh_equipment()
        controls = self.window.devices_table.cellWidget(0, 8).findChildren(QPushButton)
        self.assertEqual(
            {self.window.tr("edit"), self.window.tr("actions")},
            {control.text() for control in controls},
        )
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
