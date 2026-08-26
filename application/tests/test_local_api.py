from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.local_api import ImageStream, LocalApiServer


class LocalApiImageTest(unittest.TestCase):
    def test_exposes_only_image_name_and_streams_source_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "label photo.jpg"
            image.write_bytes(b"image-bytes")
            service = SerialVisionService(Database(root / "database.sqlite3"))
            model = service.models()[0]
            service.add_device(
                {
                    "recognized_text": "SN-IMAGE",
                    "contract_number": "42",
                    "operation_type": "receipt",
                    "source_image_path": str(image),
                    "device_model_id": model["id"],
                    "registered_at": "2026-08-26T12:00:00",
                }
            )
            record = service.all_filtered_devices(search="SN-IMAGE")[0]
            api = LocalApiServer(service)

            response = api.device(record)
            check_status, check = api.image("GET", ["api", "v1", "image", "check", str(record["id"])], {})
            get_status, stream = api.image("POST", ["api", "v1", "image", "get"], {"record_id": record["id"]})
            streamed_bytes = stream.path.read_bytes()

        self.assertNotIn("source_image_path", response)
        self.assertEqual("label photo.jpg", response["source_image_name"])
        self.assertEqual(200, check_status)
        self.assertEqual({"record_id": record["id"], "image_name": "label photo.jpg", "available": True}, check)
        self.assertEqual(200, get_status)
        self.assertIsInstance(stream, ImageStream)
        self.assertEqual("label photo.jpg", stream.path.name)
        self.assertEqual(b"image-bytes", streamed_bytes)


if __name__ == "__main__":
    unittest.main()
