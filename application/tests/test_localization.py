from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from string import Formatter
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch

from PIL import Image
from PySide6.QtCore import QObject
from serial_vision.ai_vision import AiVisionRecognizer
from serial_vision.application_service import SerialVisionService
from serial_vision.barcode import BarcodeRecognizer
from serial_vision.database import Database
from serial_vision.i18n import TEXT, error_message
from serial_vision.image_catalog import ImageCatalog
from serial_vision.image_editing import ImageEditSession
from serial_vision.recognition_strategies import RecognitionOptions
from serial_vision.ui.workers import AiRecognitionWorker, RecognitionWorker

UPDATER_PATH = (
    Path(__file__).resolve().parents[2] / "tools" / "advance_serial_vision_path_updater.py"
)
ERROR_KEYS = (
    "ocr_no_text",
    "api_bearer_required",
    "api_key_invalid",
    "api_key_expired",
    "api_rate_exceeded",
    "editor_rotation_range",
    "editor_rotation_invalid",
    "editor_crop_invalid",
    "editor_resize_range",
    "editor_resize_invalid",
    "editor_adjustment_range",
    "image_outside_folder",
    "barcode_module_unavailable",
    "splitter_unknown",
    "folder_missing",
    "ai_no_text",
    "startup_log_retry",
)


class LocalizationTest(unittest.TestCase):
    def test_requested_errors_have_explicit_translations_and_matching_placeholders(self) -> None:
        for key in ERROR_KEYS:
            fields = None
            for language in ("uk", "en", "pl"):
                with self.subTest(key=key, language=language):
                    self.assertIn(key, TEXT[language])
                    translated = error_message(language, RuntimeError(key))
                    self.assertEqual(TEXT[language][key], translated)
                    current_fields = {
                        field for _, field, _, _ in Formatter().parse(translated) if field
                    }
                    if fields is not None:
                        self.assertEqual(fields, current_fields)
                    fields = current_fields
        self.assertEqual(
            "OS error: access denied", error_message("pl", OSError("OS error: access denied"))
        )

    def test_standalone_catalog_matches_central_catalog_without_application_imports(self) -> None:
        tree = ast.parse(UPDATER_PATH.read_text(encoding="utf-8"))
        catalog = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "UPDATER_TEXT"
                for target in node.targets
            )
        )
        for language in ("uk", "en", "pl"):
            expected = {
                key: value for key, value in TEXT[language].items() if key.startswith("updater_")
            }
            self.assertEqual(expected, catalog[language])
        imported_modules = [
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        self.assertFalse(
            any(name.startswith(("serial_vision", "PySide6")) for name in imported_modules)
        )

    def test_domain_validation_raises_translatable_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo = root / "photo.png"
            Image.new("RGB", (20, 10)).save(photo)
            session = ImageEditSession(photo)
            actions = (
                (lambda: session.rotate_degrees(181), "editor_rotation_range"),
                (lambda: session.crop(-1, 0, 10, 10), "editor_crop_invalid"),
                (lambda: session.resize(301), "editor_resize_range"),
                (
                    lambda: session.set_adjustments(
                        brightness=201, contrast=100, color=100, sharpness=100
                    ),
                    "editor_adjustment_range",
                ),
                (
                    lambda: ImageCatalog(root)._require_owned(root.parent / "outside.png"),
                    "image_outside_folder",
                ),
                (lambda: AiVisionRecognizer._require_text(""), "ai_no_text"),
            )
            for action, key in actions:
                with (
                    self.subTest(key=key),
                    self.assertRaisesRegex((ValueError, RuntimeError), "^" + key + "$"),
                ):
                    action()
            with patch.object(
                ImageEditSession, "size", new_callable=PropertyMock, return_value=(12000, 12000)
            ):
                with self.assertRaisesRegex(ValueError, "editor_rotation_invalid"):
                    session.rotate_degrees(45)
                with self.assertRaisesRegex(ValueError, "editor_resize_invalid"):
                    session.resize(300)
            service = SerialVisionService(Database(root / "test.sqlite3"))
            with self.assertRaisesRegex(ValueError, "splitter_unknown"):
                service.splitter_state("invalid")
            with self.assertRaisesRegex(ValueError, "folder_missing"):
                service.complete_setup(root / "missing")
            self.assertEqual(
                "barcode_module_unavailable", BarcodeRecognizer().module_unavailable_message
            )

    def test_ocr_uses_interface_language_independently_of_recognition_language(self) -> None:
        for language in ("uk", "en", "pl"):
            parent = QObject()
            parent.ui_locale = language
            worker = RecognitionWorker(
                Path("test.png"),
                "eng",
                "OCR",
                TEXT[language]["barcode_module_unavailable"],
                RecognitionOptions(),
                parent,
            )
            completed = []
            worker.completed.connect(lambda *args: completed.append(args))
            with (
                patch("serial_vision.ui.workers.RapidOcrRecognizer") as ocr,
                patch("serial_vision.ui.workers.BarcodeRecognizer") as barcode,
            ):
                ocr.return_value.recognize.side_effect = RuntimeError("ocr_no_text")
                barcode.return_value.recognize.return_value = ""
                worker.run()
            self.assertEqual(TEXT[language]["ocr_no_text"], completed[0][1])

    def test_ai_worker_translates_empty_provider_response(self) -> None:
        service = SimpleNamespace(
            locale=lambda: "pl", recognize_ai=Mock(side_effect=RuntimeError("ai_no_text"))
        )
        worker = AiRecognitionWorker(service, "profile", Path("test.png"))
        failed = []
        worker.failed.connect(failed.append)
        worker.run()
        self.assertEqual([TEXT["pl"]["ai_no_text"]], failed)

    def test_api_authentication_errors_follow_configured_locale(self) -> None:
        from serial_vision.local_api import LocalApiServer

        with tempfile.TemporaryDirectory() as directory:
            service = SerialVisionService(Database(Path(directory) / "test.sqlite3"))
            for language in ("uk", "en", "pl"):
                service.save_locale(language)
                api = LocalApiServer(service)
                revoked = service.issue_api_key("revoked", "", None, 500)
                expired = service.issue_api_key(
                    "expired", "", datetime(2000, 1, 1, tzinfo=UTC).isoformat(), 500
                )
                active = service.issue_api_key("active", "", None, 500)
                key = service._database.api_key_by_hash(
                    hashlib.sha256(revoked.encode()).hexdigest()
                )
                service.revoke_api_key(key["id"])
                cases = (
                    (None, "api_bearer_required", 401),
                    ("invalid", "api_key_invalid", 401),
                    (revoked, "api_key_invalid", 401),
                    (expired, "api_key_expired", 401),
                    (active, "api_rate_exceeded", 429),
                )
                for token, code, expected_status in cases:
                    with self.subTest(language=language, code=code):
                        headers = {"Authorization": "Bearer " + token} if token else {}
                        request = SimpleNamespace(
                            command="GET",
                            path="/api/v1/models",
                            headers=headers,
                            rfile=io.BytesIO(),
                            client_address=("127.0.0.1", 1234),
                        )
                        if code == "api_rate_exceeded":
                            api.authorize(request)
                        with patch.object(api, "reply") as reply:
                            api.handle(request)
                        self.assertEqual(
                            (expected_status, {"error": TEXT[language][code]}),
                            reply.call_args.args[1:],
                        )


class StandaloneUpdaterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("standalone_updater_test", UPDATER_PATH)
        cls.updater = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(cls.updater)
        except ImportError as error:
            raise unittest.SkipTest(f"Tk is unavailable: {error}") from error

    def test_windows_ui_language_and_unsupported_fallback(self) -> None:
        for identifier, expected in ((1058, "uk"), (1033, "en"), (1045, "pl"), (1049, "uk")):
            kernel = SimpleNamespace(GetUserDefaultUILanguage=lambda: identifier)
            with (
                self.subTest(identifier=identifier),
                patch.object(self.updater.os, "name", "nt"),
                patch("ctypes.windll", SimpleNamespace(kernel32=kernel), create=True),
            ):
                self.assertEqual(expected, self.updater.system_language())

    def test_fallback_when_os_language_is_unavailable(self) -> None:
        kernel = SimpleNamespace(GetUserDefaultUILanguage=lambda: 0)
        with (
            patch("ctypes.windll", SimpleNamespace(kernel32=kernel), create=True),
            patch.object(self.updater.locale, "getlocale", return_value=(None, None)),
        ):
            self.assertEqual("uk", self.updater.system_language())

    def create_window(self):
        import tkinter

        try:
            window = self.updater.LegacyUpdater()
        except tkinter.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        window.root.withdraw()
        self.addCleanup(window.root.destroy)
        return window

    def test_switching_language_translates_live_progress_and_existing_log(self) -> None:
        window = self.create_window()
        window.install_button.configure(state="disabled")
        window.events.put(("progress", (1024 * 1024, 2 * 1024 * 1024)))
        window.process_events()
        window.add_log("updater_error_log", error="updater_digest_mismatch")
        for index, language in enumerate(("uk", "en", "pl"), start=1):
            window.language_choice.current(index)
            window.change_language()
            self.assertEqual(language, window.locale)
            self.assertEqual(TEXT[language]["updater_title"], window.root.title())
            self.assertIn("50%", window.status.get())
            self.assertIn(TEXT[language]["updater_digest_mismatch"], window.log.get("1.0", "end"))
            self.assertEqual("disabled", str(window.install_button["state"]))
            self.assertEqual(50, window.progress["value"])
        window.language_choice.current(0)
        with patch.object(self.updater, "system_language", return_value="en"):
            window.change_language()
        self.assertEqual("en", window.locale)

    def test_error_dialog_uses_language_selected_after_worker_event(self) -> None:
        window = self.create_window()
        window.events.put(("error", "updater_no_digest"))
        window.language_choice.current(3)
        window.change_language()
        with patch.object(self.updater.messagebox, "showerror") as show:
            window.process_events()
        self.assertIn(TEXT["pl"]["updater_no_digest"], show.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
