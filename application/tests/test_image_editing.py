from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QSlider
from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.image_editing import ImageEditSession
from serial_vision.ui.image_editor import ImageEditorDialog
from serial_vision.ui.workers import AiRecognitionWorker, RecognitionWorker


class ImageEditingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / "source.png"
        Image.new("RGB", (400, 200), (100, 60, 20)).save(self.source)
        self.original_bytes = self.source.read_bytes()

    def tearDown(self) -> None:
        self.app.processEvents()
        self.directory.cleanup()

    def test_crop_rotate_resize_and_adjustments_leave_original_unchanged(self) -> None:
        session = ImageEditSession(self.source)
        session.crop(20, 10, 100, 80)
        session.rotate_clockwise()
        session.resize(150)
        session.set_adjustments(brightness=120, contrast=130, color=80, sharpness=140)
        snapshot = self.root / "recognition.png"
        session.save_snapshot(snapshot)
        with Image.open(snapshot) as image:
            self.assertEqual((120, 150), image.size)
        self.assertEqual(self.original_bytes, self.source.read_bytes())
        session.reset()
        self.assertEqual((400, 200), session.size)

    def test_invalid_crop_cannot_escape_photo(self) -> None:
        session = ImageEditSession(self.source)
        with self.assertRaises(ValueError):
            session.crop(350, 0, 100, 100)
        self.assertEqual((400, 200), session.size)

    def test_free_rotation_expands_working_image_only(self) -> None:
        session = ImageEditSession(self.source)
        session.rotate_degrees(45)
        width, height = session.size
        self.assertGreater(width, 400)
        self.assertGreater(height, 200)
        self.assertEqual(self.original_bytes, self.source.read_bytes())
        session.reset()
        self.assertEqual((400, 200), session.size)
        with self.assertRaises(ValueError):
            session.rotate_degrees(181)

    def test_editor_uses_snapshot_and_does_not_start_ai_by_default(self) -> None:
        database = Database(self.root / "database.sqlite3")
        service = SerialVisionService(database)
        dialog = ImageEditorDialog(
            service, self.source, "uk", "eng", RecognitionWorker, AiRecognitionWorker
        )
        self.assertEqual((0, 0, 400, 200), dialog._crop_values())
        dialog.crop_values["editor_x"].setValue(10)
        dialog.crop_values["editor_y"].setValue(10)
        dialog.crop_values["editor_width"].setValue(100)
        dialog.crop_values["editor_height"].setValue(50)
        dialog.apply_crop()
        self.assertEqual((100, 50), dialog.session.size)
        self.assertEqual("", dialog.ai_profile.currentData())
        with (
            patch.object(RecognitionWorker, "start"),
            patch.object(AiRecognitionWorker, "start") as ai_start,
        ):
            dialog.recognize()
            self.assertTrue(dialog._snapshot.is_file())
            with Image.open(dialog._snapshot) as image:
                self.assertEqual((100, 50), image.size)
            worker = next(iter(dialog._workers))
            worker.completed.emit(str(dialog._snapshot), "SERIAL", "CODE128: SERIAL", "")
            worker.finished.emit()
            self.app.processEvents()
            ai_start.assert_not_called()
        self.assertEqual("SERIAL", dialog.results["ocr"].toPlainText())
        self.assertEqual("CODE128: SERIAL", dialog.results["barcodes"].toPlainText())
        self.assertEqual(self.original_bytes, self.source.read_bytes())
        dialog.close()
        self.app.processEvents()

    def test_mouse_selection_maps_to_source_pixels(self) -> None:
        database = Database(self.root / "database.sqlite3")
        dialog = ImageEditorDialog(
            SerialVisionService(database),
            self.source,
            "en",
            "eng",
            RecognitionWorker,
            AiRecognitionWorker,
        )
        preview_width, preview_height = dialog._preview_size
        dialog.set_crop_from_selection(
            QRectF(preview_width / 4, preview_height / 4, preview_width / 2, preview_height / 2)
        )
        self.assertEqual((100, 50, 200, 100), dialog._crop_values())
        dialog.close()
        self.app.processEvents()

    def test_crop_handles_resize_and_move_existing_selection(self) -> None:
        database = Database(self.root / "database.sqlite3")
        dialog = ImageEditorDialog(
            SerialVisionService(database),
            self.source,
            "en",
            "eng",
            RecognitionWorker,
            AiRecognitionWorker,
        )
        dialog.show()
        self.app.processEvents()
        dialog.preview.set_selection(QRectF(100, 50, 100, 80))
        self.assertEqual(8, len(dialog.preview._handles))

        def drag(start: QPoint, end: QPoint) -> None:
            viewport = dialog.preview.viewport()
            QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(viewport, pos=end)
            QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
            self.app.processEvents()

        right_edge = dialog.preview.mapFromScene(QPointF(200, 90))
        drag(right_edge, dialog.preview.mapFromScene(QPointF(240, 90)))
        self.assertEqual((100, 50, 140, 80), dialog._crop_values())

        center = dialog.preview.mapFromScene(QPointF(150, 90))
        drag(center, dialog.preview.mapFromScene(QPointF(170, 100)))
        self.assertEqual((120, 60, 140, 80), dialog._crop_values())

        corner = dialog.preview.mapFromScene(QPointF(120, 60))
        drag(corner, dialog.preview.mapFromScene(QPointF(160, 90)))
        self.assertEqual((160, 90, 100, 50), dialog._crop_values())

        dialog.close()
        self.app.processEvents()

    def test_rotation_handle_rotates_photo_and_advanced_controls_are_sliders(self) -> None:
        database = Database(self.root / "database.sqlite3")
        dialog = ImageEditorDialog(
            SerialVisionService(database),
            self.source,
            "en",
            "eng",
            RecognitionWorker,
            AiRecognitionWorker,
        )
        dialog.show()
        self.app.processEvents()
        self.assertTrue(
            all(isinstance(control, QSlider) for control in dialog.adjustments.values())
        )
        dialog.adjustments["contrast"].setValue(135)
        self.assertEqual("135 %", dialog.adjustment_values["contrast"].text())
        dialog.refresh_preview()
        self.assertEqual(135, dialog.session.contrast)

        viewport = dialog.preview.viewport()
        handle = dialog.preview._rotation_handle_position()
        self.assertTrue(viewport.rect().contains(handle))
        target = dialog.preview.mapFromScene(QPointF(400, 100))
        QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=handle)
        QTest.mouseMove(viewport, pos=target)
        self.assertGreaterEqual(dialog.rotation_degrees.value(), 85)
        self.assertLessEqual(dialog.rotation_degrees.value(), 95)
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=target)
        self.app.processEvents()
        self.assertNotEqual((400, 200), dialog.session.size)
        self.assertEqual(0, dialog.rotation_degrees.value())
        previous_size = dialog.session.size
        dialog.rotation_degrees.setValue(30)
        angle_button = next(
            control
            for control in dialog.findChildren(QPushButton)
            if control.text() == dialog.translate("editor_apply_rotation")
        )
        angle_button.click()
        self.assertNotEqual(previous_size, dialog.session.size)
        self.assertEqual(0, dialog.rotation_degrees.value())
        self.assertEqual(self.original_bytes, self.source.read_bytes())
        dialog.close()
        self.app.processEvents()

    def test_ai_only_starts_after_explicit_profile_selection(self) -> None:
        database = Database(self.root / "database.sqlite3")
        dialog = ImageEditorDialog(
            SerialVisionService(database),
            self.source,
            "uk",
            "eng",
            RecognitionWorker,
            AiRecognitionWorker,
        )
        dialog.ai_profile.addItem("Test profile", "profile-id")
        dialog.ai_profile.setCurrentIndex(1)
        with (
            patch.object(RecognitionWorker, "start"),
            patch.object(AiRecognitionWorker, "start") as ai_start,
        ):
            dialog.recognize()
            local_worker = next(iter(dialog._workers))
            local_worker.completed.emit(str(dialog._snapshot), "OCR", "BARCODE", "")
            self.app.processEvents()
            ai_start.assert_called_once()
            ai_worker = next(
                worker for worker in dialog._workers if isinstance(worker, AiRecognitionWorker)
            )
            ai_worker.completed.emit("AI RESULT")
            ai_worker.finished.emit()
            local_worker.finished.emit()
            self.app.processEvents()
        self.assertEqual("AI RESULT", dialog.results["ai"].toPlainText())
        dialog.close()
        self.app.processEvents()

    def test_closing_during_recognition_waits_to_remove_snapshot(self) -> None:
        database = Database(self.root / "database.sqlite3")
        dialog = ImageEditorDialog(
            SerialVisionService(database),
            self.source,
            "uk",
            "eng",
            RecognitionWorker,
            AiRecognitionWorker,
        )
        with patch.object(RecognitionWorker, "start"):
            dialog.recognize()
            snapshot = dialog._snapshot
            worker = next(iter(dialog._workers))
            dialog.close()
            self.assertTrue(snapshot.is_file())
            worker.finished.emit()
            self.app.processEvents()
        self.assertFalse(snapshot.exists())


if __name__ == "__main__":
    unittest.main()
