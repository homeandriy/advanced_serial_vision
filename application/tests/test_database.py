from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database


class DatabaseTest(unittest.TestCase):
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
            service.add_device({"recognized_text": "SN-UTC", "contract_number": "42", "operation_type": "receipt", "source_image_path": "", "device_model_id": model["id"], "registered_at": "2026-08-26T12:00:00"})
            records, _ = service.devices(date_from="2026-08-26", date_to="2026-08-26")
        self.assertEqual(1, len(records))
        self.assertTrue(records[0]["registered_at"].endswith("+00:00"))

    def test_protects_model_with_related_device(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "database.sqlite3")
            model = database.models()[0]
            database.save_device(None, {"recognized_text": "SN-ABC12345", "contract_number": "", "operation_type": "receipt", "source_image_path": "", "device_model_id": model["id"], "registered_at": "2026-08-26T12:00:00"})

            with self.assertRaises(sqlite3.IntegrityError):
                database.delete_model(model["id"])

    def test_forward_migration_preserves_existing_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database.sqlite3"
            database = Database(path)
            model = database.models()[0]
            database.save_device(None, {"recognized_text": "SN-MIGRATION", "contract_number": "7", "operation_type": "receipt", "source_image_path": "", "device_model_id": model["id"], "registered_at": "2026-08-26T12:00:00"})
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
