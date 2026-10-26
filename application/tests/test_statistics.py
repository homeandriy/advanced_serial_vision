from __future__ import annotations

import csv
import tempfile
import unittest
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database


class AggregatedStatisticsTest(unittest.TestCase):
    def test_sql_summary_matches_local_time_reference_and_never_fetches_raw_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.sqlite3")
            service = SerialVisionService(database)
            model = service.models()[0]
            timestamps = [
                "2026-03-28T22:30:00+00:00",
                "2026-03-29T00:30:00+00:00",
                "2026-03-29T01:30:00+00:00",
                "2026-03-31T22:30:00+00:00",
                "2026-10-24T22:30:00+00:00",
                "2026-10-25T00:30:00+00:00",
                "2026-10-25T01:30:00+00:00",
                "2026-10-31T22:30:00",
                "2026-12-31T22:30:00+00:00",
            ]
            for index, timestamp in enumerate(timestamps):
                database.save_device(
                    None,
                    {
                        "recognized_text": str(index),
                        "contract_number": "",
                        "source_image_path": "",
                        "operation_type": "receipt" if index % 2 else "issue",
                        "device_model_id": model["id"],
                        "registered_at": timestamp,
                    },
                )
            raw = database.statistics_rows()
            for grouping in ("day", "month"):
                expected = defaultdict(lambda: {"receipt": 0, "issue": 0})
                for row in raw:
                    stamp = datetime.fromisoformat(row["registered_at"])
                    stamp = stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)
                    period = stamp.astimezone(ZoneInfo("Europe/Kyiv")).strftime(
                        "%Y-%m-%d" if grouping == "day" else "%Y-%m"
                    )
                    expected[period][row["operation_type"]] += 1
                with (
                    self.subTest(grouping=grouping),
                    patch.object(
                        database, "statistics_rows", side_effect=AssertionError("raw table read")
                    ),
                ):
                    summary = service.statistics_summary(grouping)
                self.assertEqual(dict(sorted(expected.items())), summary["operations"])
                self.assertEqual({model["service"]: len(raw)}, summary["services"])
                self.assertEqual({model["name"]: len(raw)}, summary["models"])

    def test_empty_database_has_empty_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = SerialVisionService(Database(Path(directory) / "test.sqlite3"))
            self.assertEqual(
                {"operations": {}, "services": {}, "models": {}}, service.statistics_summary()
            )

    def test_export_contains_all_filtered_records_beyond_ui_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "test.sqlite3")
            service = SerialVisionService(database)
            model = service.models()[0]
            with database.connection() as db:
                db.executemany(
                    "INSERT INTO devices(recognized_text, contract_number, operation_type, device_model_id, registered_at) VALUES (?, '', 'receipt', ?, '2026-01-01T12:00:00+00:00')",
                    ((f"SN-{index}", model["id"]) for index in range(5001)),
                )
            visible, metadata = service.devices()
            self.assertEqual(100, len(visible))
            self.assertEqual(5001, metadata["total"])
            destination = root / "export.csv"
            service.export_devices(destination, service.all_filtered_devices())
            with destination.open(encoding="cp1251", newline="") as stream:
                rows = list(csv.reader(stream, delimiter=";"))
            self.assertEqual(5002, len(rows))
            self.assertEqual({f"SN-{index}" for index in range(5001)}, {row[3] for row in rows[1:]})
