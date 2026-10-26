from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QThread, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.gallery import GalleryPage
from serial_vision.recognition_strategies import RecognitionOptions
from serial_vision.ui.main_window import MainWindow
from serial_vision.ui.photo_preview import PhotoPreview
from serial_vision.ui.workers import AiRecognitionWorker, CameraScanWorker, RecognitionWorker
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
        self.wait_gallery()

    def wait_gallery(self) -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            self.app.processEvents()
            if (
                self.window.recognition_page.gallery_worker is None
                and self.window.statistics_page.worker is None
            ):
                return
            time.sleep(0.005)
        self.fail("Background screen workers did not finish")

    def tearDown(self) -> None:
        self.window.close()
        self.wait_gallery()
        self.app.processEvents()
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
        photos = self.window.recognition_page.image_splitter.parentWidget()
        gallery_actions = photos.layout().itemAt(1).layout()
        self.assertEqual(
            [self.window.translate("refresh"), self.window.translate("delete")],
            [
                gallery_actions.itemAt(index).widget().text()
                for index in range(gallery_actions.count())
            ],
        )
        preview_panel = self.window.recognition_page.preview.parentWidget()
        preview_actions = preview_panel.layout().itemAt(0).layout()
        captions = [
            preview_actions.itemAt(index).widget().text()
            for index in range(preview_actions.count())
            if preview_actions.itemAt(index).widget()
        ]
        self.assertEqual(
            [
                self.window.translate(key)
                for key in ("open_image", "editor", "rotate", "fit_image", "actual_size")
            ],
            captions,
        )

    def test_image_refresh_preserves_visible_selection_and_page_change_clears_it(self) -> None:
        for index in range(49):
            Image.new("RGB", (16, 16), "white").save(self.root / f"photo_{index:02}.png")
        self.window.recognition_page.refresh_images()
        self.wait_gallery()
        selected = next(iter(self.window.recognition_page._image_buttons))
        self.window.recognition_page.selected_image = selected
        self.window.recognition_page.preview.set_image(selected)
        self.window.recognition_page.refresh_images()
        self.wait_gallery()
        self.assertTrue(self.window.recognition_page._image_buttons[selected].isChecked())
        self.window.recognition_page.change_image_page(1)
        self.assertIsNone(self.window.recognition_page.selected_image)
        self.assertIsNone(self.window.recognition_page.preview._photo)
        self.assertFalse(self.window.recognition_page.retry_button.isEnabled())
        self.wait_gallery()

    def test_settings_mark_unsaved_changes(self) -> None:
        self.assertFalse(self.window.settings_page.settings_save.isEnabled())
        self.window.settings_page.theme_choice.setCurrentIndex(1)
        self.assertTrue(self.window.settings_page.settings_save.isEnabled())
        self.assertIn(
            "*", self.window.tabs.tabText(self.window.tabs.indexOf(self.window.settings_page))
        )

    def test_slow_thumbnail_does_not_block_qt_event_loop(self) -> None:
        Image.new("RGB", (20, 20)).save(self.root / "slow.png")
        entered, release = Event(), Event()
        cache = self.window.recognition_page.thumbnail_cache
        decode = cache.thumbnail

        def slow_thumbnail(image):
            entered.set()
            release.wait(3)
            return decode(image)

        ticks = []
        timer = QTimer(self.window)
        timer.setInterval(5)
        timer.timeout.connect(lambda: ticks.append(True))
        try:
            with patch.object(cache, "thumbnail", side_effect=slow_thumbnail):
                self.window.recognition_page.refresh_images()
                timer.start()
                for _ in range(100):
                    QTest.qWait(10)
                    if entered.is_set():
                        break
                self.assertTrue(entered.is_set())
                QTest.qWait(50)
                self.assertGreater(len(ticks), 0)
                release.set()
                self.wait_gallery()
        finally:
            release.set()
            timer.stop()
            self.wait_gallery()

    def test_stale_gallery_result_cannot_replace_latest_page(self) -> None:
        page = self.window.recognition_page
        before = page.image_page_label.text()
        page.gallery_loaded(GalleryPage((), 99, 100, 100), page._gallery_generation - 1)
        self.assertEqual(before, page.image_page_label.text())

    def test_folder_switch_discards_in_flight_gallery_result(self) -> None:
        Image.new("RGB", (20, 20)).save(self.root / "old.png")
        page = self.window.recognition_page
        entered, release = Event(), Event()
        decode = page.thumbnail_cache.thumbnail

        def slow_thumbnail(image):
            entered.set()
            release.wait(3)
            return decode(image)

        with tempfile.TemporaryDirectory() as other:
            new_path = Path(other) / "new.png"
            Image.new("RGB", (20, 20)).save(new_path)
            try:
                with patch.object(page.thumbnail_cache, "thumbnail", side_effect=slow_thumbnail):
                    page.refresh_images()
                    for _ in range(100):
                        QTest.qWait(10)
                        if entered.is_set():
                            break
                    self.assertTrue(entered.is_set())
                    self.database.set_setting("image_directory", other)
                    page.refresh_images()
                    release.set()
                    self.wait_gallery()
                self.assertEqual({new_path.resolve()}, set(page._image_buttons))
            finally:
                release.set()
                self.wait_gallery()

    def test_slow_statistics_does_not_block_qt_and_stale_result_is_ignored(self) -> None:
        page = self.window.statistics_page
        entered, release = Event(), Event()
        calculate = self.window.service.statistics_summary

        def slow_summary(grouping):
            entered.set()
            release.wait(3)
            return calculate(grouping)

        ticks = []
        timer = QTimer(self.window)
        timer.setInterval(5)
        timer.timeout.connect(lambda: ticks.append(True))
        try:
            with patch.object(self.window.service, "statistics_summary", side_effect=slow_summary):
                page.refresh_statistics()
                timer.start()
                for _ in range(100):
                    QTest.qWait(10)
                    if entered.is_set():
                        break
                self.assertTrue(entered.is_set())
                QTest.qWait(50)
                self.assertGreater(len(ticks), 0)
                release.set()
                self.wait_gallery()
            rows = page.statistics_table.rowCount()
            page.statistics_loaded(
                {
                    "operations": {"2026-01": {"receipt": 1, "issue": 0}},
                    "services": {},
                    "models": {},
                },
                page._generation - 1,
            )
            self.assertEqual(rows, page.statistics_table.rowCount())
        finally:
            release.set()
            timer.stop()
            self.wait_gallery()

    def test_model_change_signal_refreshes_equipment_choices(self) -> None:
        self.window.service.add_model("Signal test", "modem", "internet")
        self.window.models_page.changed.emit()
        self.assertGreaterEqual(self.window.equipment_page.model_filter.findText("Signal test"), 0)

    def test_one_settings_action_saves_recognition_options(self) -> None:
        self.window.settings_page.recognition_rotate.setChecked(False)
        self.assertTrue(self.window.settings_page.settings_save.isEnabled())
        self.window.settings_page.save_all_settings()
        self.assertFalse(self.window.settings_page.settings_save.isEnabled())
        self.assertEqual(
            RecognitionOptions(rotate=False, enhance=True),
            self.window.service.recognition_options(),
        )

    def test_failed_settings_save_keeps_dirty_form_and_previous_appearance(self) -> None:
        self.window.settings_page.theme_choice.setCurrentIndex(1)
        previous = self.window.settings_page._settings_saved_values
        with patch.object(
            self.window.service, "save_all_settings", side_effect=OSError("disk unavailable")
        ):
            self.window.settings_page.save_all_settings()
        self.assertTrue(self.window.settings_page.settings_save.isEnabled())
        self.assertEqual(previous, self.window.settings_page._settings_saved_values)
        self.assertEqual("system", self.window.service.theme())
        self.assertIn("disk unavailable", self.window.settings_page.settings_status.text())

    def test_theme_can_be_saved_without_changing_an_unset_photo_folder(self) -> None:
        self.window.settings_page.settings_folder_path.setText("")
        self.window.settings_page._settings_saved_values = (
            self.window.settings_page.settings_values()
        )
        self.window.settings_page.theme_choice.setCurrentIndex(1)
        self.window.settings_page.save_all_settings()
        self.assertEqual("light", self.window.service.theme())
        self.assertFalse(self.window.settings_page.settings_save.isEnabled())

    def test_ai_action_stays_disabled_without_a_profile_after_recognition(self) -> None:
        self.window.recognition_page.selected_image = self.root / "image.png"
        self.window.recognition_page.set_recognition_busy(True)
        self.window.recognition_page.set_recognition_busy(False)
        self.assertFalse(self.window.recognition_page.ai_button.isEnabled())
        self.assertFalse(self.window.recognition_page.ai_result.isEnabled())

    def test_update_checks_repeat_and_respect_later_until_manual_check(self) -> None:
        self.assertTrue(self.window.updates.update_check_timer.isActive())
        self.assertEqual(4 * 60 * 60 * 1_000, self.window.updates.update_check_timer.interval())
        release = ReleaseInfo("0.7.0", "Changes", "https://example.test/setup.exe")
        self.window.updates._dismissed_update_version = release.version
        with patch.object(self.window.updates, "show_update_dialog") as show_dialog:
            self.window.updates.update_checked(release, show_status=False)
            show_dialog.assert_not_called()
            self.window.updates.update_checked(release, show_status=True)
            show_dialog.assert_called_once_with(release)

    def test_update_checksum_errors_are_localized_in_status_and_dialog(self) -> None:
        self.window.updates.update_close = QPushButton(self.window)
        self.window.updates.update_download_status = QLabel(self.window)
        for language in ("uk", "en", "pl"):
            self.window.updates.ui_locale = language
            for code in ("update_checksum_unavailable", "update_integrity_failed"):
                with (
                    self.subTest(language=language, code=code),
                    patch("serial_vision.ui.update_controller.QMessageBox.warning") as warning,
                ):
                    self.window.updates.update_download_failed(code)
                    expected = self.window.updates.translate(
                        "update_download_failed", error=self.window.updates.translate(code)
                    )
                    self.assertEqual(expected, self.window.updates.update_download_status.text())
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

    def test_camera_worker_removes_temporary_frame_after_decoder_failure(self) -> None:
        frame = self.root / "camera-frame.jpg"
        Image.new("RGB", (20, 20)).save(frame)
        worker = CameraScanWorker(frame, RecognitionOptions(), "Unavailable")
        failures = []
        worker.failed.connect(failures.append)
        with patch("serial_vision.ui.workers.BarcodeRecognizer") as recognizer:
            recognizer.return_value.recognize.side_effect = RuntimeError("decoder failure")
            worker.run()
        self.assertEqual(["decoder failure"], failures)
        self.assertFalse(frame.exists())

    def test_unreadable_photo_releases_recognition_busy_state(self) -> None:
        self.window.recognition_page.selected_image = self.root / "missing.jpg"
        with (
            patch("serial_vision.ui.workers.RapidOcrRecognizer") as ocr,
            patch("serial_vision.ui.workers.BarcodeRecognizer") as barcode,
            patch.object(RecognitionWorker, "start"),
        ):
            ocr.return_value.recognize.side_effect = FileNotFoundError("photo missing")
            barcode.return_value.recognize.side_effect = OSError("photo unreadable")
            self.window.recognition_page.start_recognition()
            worker = self.window.recognition_page.recognition_worker
            worker.run()
            self.assertFalse(self.window.recognition_page._recognition_busy)
            self.assertTrue(self.window.recognition_page.retry_button.isEnabled())
            self.assertIn("photo missing", self.window.recognition_page.ocr_result.toPlainText())
            worker.finished.emit()

    def test_old_ai_success_and_failure_cannot_replace_new_photo_results(self) -> None:
        for outcome in ("completed", "failed"):
            with self.subTest(outcome=outcome), patch.object(AiRecognitionWorker, "start"):
                self.window.recognition_page.agent_select.clear()
                self.window.recognition_page.agent_select.addItem("Profile", "profile-id")
                self.window.recognition_page.selected_image = self.root / "A.jpg"
                self.window.recognition_page.run_ai()
                worker = self.window.recognition_page.ai_worker
                self.window.recognition_page.clear_image_selection()
                self.window.recognition_page.selected_image = self.root / "B.jpg"
                self.window.recognition_page.ai_result.setPlainText("B RESULT")
                getattr(worker, outcome).emit("A RESULT")
                self.assertEqual("B RESULT", self.window.recognition_page.ai_result.toPlainText())
                self.assertFalse(self.window.recognition_page.ai_button.isEnabled())
                worker.finished.emit()
                self.assertTrue(self.window.recognition_page.ai_button.isEnabled())

    def test_ai_reply_is_ignored_after_switching_back_to_same_photo(self) -> None:
        with patch.object(AiRecognitionWorker, "start"):
            self.window.recognition_page.agent_select.addItem("Profile", "profile-id")
            self.window.recognition_page.agent_select.setCurrentIndex(1)
            self.window.recognition_page.selected_image = self.root / "A.jpg"
            self.window.recognition_page.run_ai()
            worker = self.window.recognition_page.ai_worker
            self.window.recognition_page.clear_image_selection()
            self.window.recognition_page.selected_image = self.root / "A.jpg"
            worker.completed.emit("STALE A")
            self.assertNotEqual("STALE A", self.window.recognition_page.ai_result.toPlainText())
            worker.finished.emit()

    def test_exit_stops_services_and_quits(self) -> None:
        self.window.show()
        with (
            patch.object(self.window.camera_page, "stop_camera") as stop_camera,
            patch.object(self.window.local_api, "stop") as stop_api,
            patch.object(QApplication, "quit") as quit_app,
        ):
            self.window.close()
            stop_camera.assert_called_once()
            stop_api.assert_called_once()
            quit_app.assert_called_once()
        self.assertFalse(self.window.updates.update_check_timer.isActive())
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
    assert not window.updates.update_check_timer.isActive()
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
            self.window.equipment_page.date_from,
            self.window.equipment_page.date_to,
            self.window.equipment_page.model_filter,
            self.window.equipment_page.operation_filter,
            self.window.equipment_page.type_filter,
            self.window.equipment_page.service_filter,
            self.window.equipment_page.device_search,
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
        self.window.equipment_page.refresh_equipment()
        controls = self.window.equipment_page.devices_table.cellWidget(0, 8).findChildren(
            QPushButton
        )
        self.assertEqual(
            {self.window.translate("edit"), self.window.translate("actions")},
            {control.text() for control in controls},
        )
        menu = next(control.menu() for control in controls if control.menu() is not None)
        self.assertEqual(self.window.translate("delete"), menu.actions()[-1].text())
        self.assertTrue(menu.actions()[-2].isSeparator())

    def test_selected_photo_opens_separate_editor(self) -> None:
        image = self.root / "label.png"
        Image.new("RGB", (120, 80), "white").save(image)
        self.window.recognition_page.selected_image = image
        self.window.recognition_page.edit_image()
        dialog = self.window.recognition_page.image_editor
        self.assertTrue(dialog.isVisible())
        self.assertEqual(image, dialog.session.source)
        dialog.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
