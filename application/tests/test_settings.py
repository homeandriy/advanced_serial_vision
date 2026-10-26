from __future__ import annotations

import socket
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.local_api import LocalApiServer
from serial_vision.settings import SettingsRecoveryError, SettingsSaveError, SettingsValues


class AtomicSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = Database(self.root / "test.sqlite3")
        self.service = SerialVisionService(self.database)
        self.initial = SettingsValues(
            "uk", str(self.root), "system", "system", True, True, False, "4556"
        )
        self.service.save_all_settings(self.initial)
        self.modified = replace(
            self.initial,
            locale="pl",
            theme="dark",
            icon_style="modern",
            rotate=False,
            api_enabled=True,
            api_port="4557",
        )

    def snapshot(self) -> dict[str, str]:
        with self.database.connection() as db:
            return dict(db.execute("SELECT key, value FROM settings").fetchall())

    def test_write_failure_rolls_back_every_setting_before_runtime_changes(self) -> None:
        before = self.snapshot()
        with self.database.connection() as db:
            db.execute(
                "CREATE TRIGGER fail_theme BEFORE INSERT ON settings WHEN NEW.key='theme' BEGIN SELECT RAISE(ABORT, 'injected settings failure'); END"
            )
        calls = []
        with self.assertRaises(SettingsSaveError):
            self.service.save_all_settings(
                self.modified, lambda enabled, port: calls.append((enabled, port))
            )
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], calls)

    def test_runtime_failure_rolls_back_settings_and_restores_previous_configuration(self) -> None:
        before = self.snapshot()
        calls = []

        def configure(enabled: bool, port: int) -> None:
            calls.append((enabled, port))
            if enabled:
                raise OSError("injected bind failure")

        with self.assertRaisesRegex(OSError, "injected bind failure"):
            self.service.save_all_settings(self.modified, configure)
        self.assertEqual(before, self.snapshot())
        self.assertEqual([(True, 4557), (False, 4556)], calls)

    def test_failed_runtime_recovery_is_explicit_and_database_still_rolls_back(self) -> None:
        before = self.snapshot()

        def configure(_enabled: bool, _port: int) -> None:
            raise OSError("runtime unavailable")

        with self.assertRaises(SettingsRecoveryError) as raised:
            self.service.save_all_settings(self.modified, configure)
        self.assertEqual("settings_api_restore_failed", str(raised.exception))
        self.assertIsInstance(raised.exception.recovery, OSError)
        self.assertEqual(before, self.snapshot())

    def test_occupied_port_does_not_persist_any_changes(self) -> None:
        api = LocalApiServer(self.service)
        self.addCleanup(api.stop)
        before = self.snapshot()
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            port = blocker.getsockname()[1]
            with self.assertRaises(OSError):
                self.service.save_all_settings(
                    replace(self.modified, api_port=str(port)), api.configure
                )
        self.assertIsNone(api.server)
        self.assertEqual(before, self.snapshot())

    def test_commit_failure_restores_runtime_after_database_rollback(self) -> None:
        before = self.snapshot()
        calls = []

        @contextmanager
        def failing_commit():
            connection = sqlite3.connect(self.database.path)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
                if connection.in_transaction:
                    connection.rollback()
                    raise sqlite3.OperationalError("injected commit failure")
            finally:
                connection.close()

        with (
            patch.object(self.database, "connection", failing_commit),
            self.assertRaises(SettingsSaveError),
        ):
            self.service.save_all_settings(
                self.modified, lambda enabled, port: calls.append((enabled, port))
            )
        self.assertEqual(before, self.snapshot())
        self.assertEqual([(True, 4557), (False, 4556)], calls)

    def test_busy_new_port_restores_previously_running_server(self) -> None:
        api = LocalApiServer(self.service)
        api.start(0)
        self.addCleanup(api.stop)
        assert api.server is not None
        previous_port = api.server.server_port
        self.service.save_api_settings(True, previous_port)
        before = self.snapshot()
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            with self.assertRaises(OSError):
                self.service.save_all_settings(
                    replace(self.modified, api_port=str(blocker.getsockname()[1])), api.configure
                )
        self.assertIsNotNone(api.server)
        self.assertEqual(previous_port, api.server.server_port)
        self.assertEqual(before, self.snapshot())

    def test_success_saves_all_options_and_api_uses_explicit_uncommitted_port(self) -> None:
        calls = []
        self.service.save_all_settings(
            self.modified, lambda enabled, port: calls.append((enabled, port))
        )
        saved = self.snapshot()
        self.assertEqual("pl", saved["locale"])
        self.assertEqual("dark", saved["theme"])
        self.assertEqual("modern", saved["icon_style"])
        self.assertEqual("no", saved["recognition_rotate"])
        self.assertEqual("yes", saved["api_enabled"])
        self.assertEqual("4557", saved["api_port"])
        self.assertEqual([(True, 4557)], calls)

    def test_invalid_input_changes_neither_database_nor_runtime(self) -> None:
        before = self.snapshot()
        for settings in (
            replace(self.modified, image_directory=str(self.root / "missing")),
            replace(self.modified, api_port="not a port"),
            replace(self.modified, locale="unsupported"),
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.service.save_all_settings(settings)
            self.assertEqual(before, self.snapshot())
