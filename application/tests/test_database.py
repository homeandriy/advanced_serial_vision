from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.recognition_strategies import RecognitionOptions


class DatabaseTest(unittest.TestCase):
    def test_splitter_positions_are_saved_per_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = SerialVisionService(Database(Path(directory) / "database.sqlite3"))
            self.assertIsNone(service.splitter_state("recognition_horizontal"))
            service.save_splitter_state("recognition_horizontal", b"Qt splitter state")
            self.assertEqual(b"Qt splitter state", service.splitter_state("recognition_horizontal"))

    def test_recognition_strategy_options_are_saved_per_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = SerialVisionService(Database(Path(directory) / "database.sqlite3"))
            self.assertEqual(RecognitionOptions(), service.recognition_options())
            service.save_recognition_options(RecognitionOptions(rotate=False, enhance=True))
            self.assertEqual(
                RecognitionOptions(rotate=False, enhance=True), service.recognition_options()
            )

    def test_saves_and_filters_devices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "database.sqlite3")
            model = database.models()[0]
            database.save_device(
                None,
                {
                    "recognized_text": "SN-ABC12345",
                    "contract_number": "42/7",
                    "operation_type": "receipt",
                    "source_image_path": "C:/photo.jpg",
                    "device_model_id": model["id"],
                    "registered_at": "2026-08-26T12:00:00",
                },
            )
            records, pagination = database.devices(search="ABC")

        self.assertEqual(1, len(records))
        self.assertIsNone(pagination)
        self.assertEqual("SN-ABC12345", records[0]["recognized_text"])
        self.assertEqual("receipt", records[0]["operation_type"])

    def test_service_stores_local_kyiv_input_as_utc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = SerialVisionService(Database(Path(directory) / "database.sqlite3"))
            model = service.models()[0]
            service.add_device(
                {
                    "recognized_text": "SN-UTC",
                    "contract_number": "42",
                    "operation_type": "receipt",
                    "source_image_path": "",
                    "device_model_id": model["id"],
                    "registered_at": "2026-08-26T12:00:00",
                }
            )
            records, _ = service.devices(date_from="2026-08-26", date_to="2026-08-26")
        self.assertEqual(1, len(records))
        self.assertTrue(records[0]["registered_at"].endswith("+00:00"))

    def test_protects_model_with_related_device(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "database.sqlite3")
            model = database.models()[0]
            database.save_device(
                None,
                {
                    "recognized_text": "SN-ABC12345",
                    "contract_number": "",
                    "operation_type": "receipt",
                    "source_image_path": "",
                    "device_model_id": model["id"],
                    "registered_at": "2026-08-26T12:00:00",
                },
            )

            with self.assertRaises(sqlite3.IntegrityError):
                database.delete_model(model["id"])

    def test_date_filter_includes_fractional_seconds_and_dst_days(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = SerialVisionService(Database(Path(directory) / "database.sqlite3"))
            for day, tomorrow in (("2026-03-29", "2026-03-30"), ("2026-10-25", "2026-10-26")):
                with self.subTest(day=day):
                    for text, timestamp in (
                        ("start", day + "T00:00:00"),
                        ("end", day + "T23:59:59.999999"),
                        ("next", tomorrow + "T00:00:00"),
                    ):
                        service.add_device(
                            {
                                "recognized_text": text,
                                "contract_number": "",
                                "operation_type": "receipt",
                                "device_model_id": service.models()[0]["id"],
                                "registered_at": timestamp,
                            }
                        )
                    rows = service.all_filtered_devices(date_from=day, date_to=day)
                    self.assertEqual({"start", "end"}, {row["recognized_text"] for row in rows})
                    destination = Path(directory) / "filtered.csv"
                    service.export_devices(destination, rows)
                    exported = destination.read_text(encoding="cp1251")
                    self.assertIn("end", exported)
                    self.assertNotIn("next", exported)

    def test_forward_migration_preserves_existing_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database.sqlite3"
            database = Database(path)
            model = database.models()[0]
            database.save_device(
                None,
                {
                    "recognized_text": "SN-MIGRATION",
                    "contract_number": "7",
                    "operation_type": "receipt",
                    "source_image_path": "",
                    "device_model_id": model["id"],
                    "registered_at": "2026-08-26T12:00:00",
                },
            )
            connection = sqlite3.connect(path)
            try:
                connection.execute("DROP INDEX devices_recognized_text_idx")
                connection.execute("PRAGMA user_version = 1")
                connection.commit()
            finally:
                connection.close()

            migrated = Database(path)
            records, _ = migrated.devices(search="SN-MIGRATION")
            connection = sqlite3.connect(path)
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                indexes = {row[1] for row in connection.execute("PRAGMA index_list(devices)")}
            finally:
                connection.close()

        self.assertEqual(4, version)
        self.assertEqual(1, len(records))
        self.assertIn("devices_recognized_text_idx", indexes)
