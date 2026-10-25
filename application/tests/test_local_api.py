from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.local_api import ApiError, GeneratedCodeStream, ImageStream, LocalApiServer


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
            check_status, check = api.image(
                "GET", ["api", "v1", "image", "check", str(record["id"])], {}
            )
            get_status, stream = api.image(
                "POST", ["api", "v1", "image", "get"], {"record_id": record["id"]}
            )
            streamed_bytes = stream.path.read_bytes()

        self.assertNotIn("source_image_path", response)
        self.assertEqual("label photo.jpg", response["source_image_name"])
        self.assertEqual(200, check_status)
        self.assertEqual(
            {"record_id": record["id"], "image_name": "label photo.jpg", "available": True}, check
        )
        self.assertEqual(200, get_status)
        self.assertIsInstance(stream, ImageStream)
        self.assertEqual("label photo.jpg", stream.path.name)
        self.assertEqual(b"image-bytes", streamed_bytes)

    def test_generates_code_stream_for_equipment_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = SerialVisionService(Database(Path(directory) / "database.sqlite3"))
            model = service.models()[0]
            service.add_device(
                {
                    "recognized_text": "AA:BB:CC:DD",
                    "contract_number": "",
                    "operation_type": "receipt",
                    "source_image_path": "",
                    "device_model_id": model["id"],
                    "registered_at": "2026-08-26T12:00:00",
                }
            )
            record = service.all_filtered_devices(search="AA:BB")[0]
            status, stream = LocalApiServer(service).code(
                "POST", ["api", "v1", "code", "get"], {"record_id": record["id"], "type": "barcode"}
            )

        self.assertEqual(200, status)
        self.assertIsInstance(stream, GeneratedCodeStream)
        self.assertTrue(stream.data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertRegex(stream.filename, r"^barcode_AABBCCDD_\d{2}_\d{2}_\d{2}_\d{2}_\d{4}\.png$")


class LocalApiValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.service = SerialVisionService(Database(Path(self.directory.name) / "database.sqlite3"))
        self.api = LocalApiServer(self.service)
        self.data = {
            "recognized_text": "SN-VALID",
            "contract_number": None,
            "operation_type": "receipt",
            "device_model_id": self.service.models()[0]["id"],
            "registered_at": "2026-10-25T12:00:00",
        }

    def request(self, method: str, path: str, body: bytes) -> tuple[int, object]:
        request = SimpleNamespace(
            command=method,
            path=path,
            headers={"Content-Length": str(len(body))},
            rfile=io.BytesIO(body),
            client_address=("127.0.0.1", 12345),
        )
        with (
            patch.object(self.api, "authorize", return_value=None),
            patch.object(self.api, "reply") as reply,
        ):
            self.api.handle(request)
        return reply.call_args.args[1:]

    def test_invalid_equipment_is_rejected_without_writing(self) -> None:
        for key, value in (
            ("recognized_text", "  "),
            ("recognized_text", None),
            ("recognized_text", 42),
            ("contract_number", 123),
            ("contract_number", "x" * 21),
            ("operation_type", "invalid"),
            ("device_model_id", 99999),
            ("device_model_id", True),
            ("registered_at", "invalid"),
            ("registered_at", None),
            ("source_image_path", []),
        ):
            with self.subTest(key=key, value=value):
                import json

                status, _ = self.request(
                    "POST", "/api/v1/equipment", json.dumps({**self.data, key: value}).encode()
                )
                self.assertEqual(422, status)
        self.assertEqual([], self.service.all_filtered_devices())

    def test_non_object_json_is_rejected(self) -> None:
        for body in (b"[]", b"null", b"42", b"broken-json"):
            with self.subTest(body=body):
                status, _ = self.request("POST", "/api/v1/equipment", body)
                self.assertEqual(422, status)

    def test_missing_record_updates_and_deletes_return_404(self) -> None:
        for resource in ("equipment", "models"):
            for method in ("PATCH", "DELETE"):
                with self.subTest(resource=resource, method=method):
                    with self.assertRaises(ApiError) as raised:
                        self.api.dispatch(method, f"/api/v1/{resource}/999999", {}, self.data)
                    self.assertEqual(404, raised.exception.status)

    def test_optional_photo_path_and_null_contract_are_normalized(self) -> None:
        status, _ = self.api.equipment("POST", None, {}, self.data)
        self.assertEqual(201, status)
        record = self.service.all_filtered_devices()[0]
        self.assertIsNone(record["source_image_path"])
        self.assertIsNone(record["contract_number"])
        self.service.update_device(record["id"], {**self.data, "source_image_path": "original.jpg"})
        self.api.equipment("PATCH", record["id"], {}, self.data)
        self.assertEqual("original.jpg", str(self.service.source_image_path(record["id"])))

    def test_service_rejects_missing_record_update(self) -> None:
        with self.assertRaisesRegex(ValueError, "record_missing"):
            self.service.update_device(999999, self.data)

    def test_models_require_valid_name_type_and_service(self) -> None:
        for name, device_type, service in (
            (" ", "modem", "internet"),
            (None, "modem", "internet"),
            ("Model", "invalid", "internet"),
            ("Model", "modem", "invalid"),
        ):
            with self.subTest(name=name, device_type=device_type, service=service):
                with self.assertRaises(ValueError):
                    self.service.add_model(name, device_type, service)


if __name__ == "__main__":
    unittest.main()
