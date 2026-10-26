from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from serial_vision.application_service import SerialVisionService
from serial_vision.database import Database
from serial_vision.main import instance_lock_name
from serial_vision.ui.main_window import MainWindow
from serial_vision.ui.warehouse_forms import WarehouseForm
from serial_vision.warehouse.security import WarehouseError


class WarehouseUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        database = Database(self.root / "local.sqlite3")
        database.set_setting("license_accepted", "yes")
        database.set_setting("image_directory", str(self.root))
        self.environment = patch.dict(os.environ, {"SERIAL_VISION_WAREHOUSE_URL": ""})
        self.environment.start()
        self.window = MainWindow(SerialVisionService(database))
        self.page = self.window.warehouses_page
        self.wait()

    def wait(self):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            self.app.processEvents()
            if (
                self.page.worker is None
                and self.window.recognition_page.gallery_worker is None
                and self.window.statistics_page.worker is None
            ):
                return
            time.sleep(0.005)
        self.fail("Worker timeout")

    def tearDown(self):
        self.window.close()
        self.wait()
        self.app.processEvents()
        self.window.deleteLater()
        self.app.processEvents()
        self.environment.stop()
        self.temp.cleanup()

    def bootstrap(self):
        self.window.tabs.setCurrentWidget(self.page)
        self.wait()
        self.page.login_name.setText("Administrator")
        self.page.login_email.setText("admin@example.test")
        self.page.login_password.setText("AdminPass1_")
        self.page.login_confirm.setText("AdminPass1_")
        self.page.sign_in()
        self.wait()

    def test_startup_does_not_create_accounts_or_prompt_for_login(self):
        self.assertFalse((self.root / "warehouses.sqlite3").exists())
        self.assertIs(self.window.recognition_page, self.window.tabs.currentWidget())
        self.assertFalse(self.page.activated)

    def test_instance_lock_uses_windows_session_identity(self):
        name = instance_lock_name()
        self.assertTrue(name.endswith(".lock"))
        if sys.platform == "win32":
            self.assertTrue(name.startswith("serial-vision-session-"))
        else:
            self.assertEqual("serial-vision.lock", name)

    def test_first_open_explains_admin_setup_and_bootstrap_opens_workspace(self):
        self.window.tabs.setCurrentWidget(self.page)
        self.wait()
        self.assertEqual(self.page.translate("wh_first_admin"), self.page.status.text())
        self.bootstrap()
        self.assertEqual("admin", self.page.user["role"])
        self.assertEqual(2, self.page.stack.currentIndex())
        self.assertFalse(self.page.login_password.text())
        self.assertTrue(
            self.page.sections.isTabVisible(
                self.page.sections.indexOf(self.page.section_widgets["users"])
            )
        )

    def test_temporary_login_only_offers_password_replacement_then_warehouse_access(self):
        self.bootstrap()
        created = self.page.client.call(
            "create_user",
            {"email": "operator@example.test", "name": "Operator", "role": "storekeeper"},
        )
        self.page.sign_out()
        self.wait()
        self.page.login_email.setText("operator@example.test")
        self.page.login_password.setText(created["temporary_password"])
        self.page.sign_in()
        self.wait()
        self.assertEqual(1, self.page.stack.currentIndex())
        self.page.new_password.setText("NewPass2+")
        self.page.confirm_password.setText("NewPass2+")
        self.page.change_password()
        self.wait()
        self.assertEqual(2, self.page.stack.currentIndex())
        self.assertFalse(
            self.page.sections.isTabVisible(
                self.page.sections.indexOf(self.page.section_widgets["users"])
            )
        )
        self.assertFalse(self.window.api_page.isEnabled())

    def test_all_three_locales_can_build_and_open_warehouse_screen(self):
        for locale in ("uk", "en", "pl"):
            self.page.ui_locale = locale
            self.page.activated = False
            self.page.activate()
            self.wait()
            self.assertTrue(self.page.status.text())

    def test_warehouse_person_and_receipt_forms_save_into_visible_stock(self):
        self.bootstrap()
        self.page.edit_warehouse()
        form = self.page.findChildren(WarehouseForm)[-1]
        for key, value in {"code": "UI", "name": "UI warehouse", "address": "Address"}.items():
            form.fields[key].setText(value)
        form.save.click()
        self.wait()
        self.assertEqual("UI", self.page.snapshot["warehouses"][0]["code"])
        self.page.edit_person()
        form = self.page.findChildren(WarehouseForm)[-1]
        form.fields["name"].setText("Responsible")
        form.save.click()
        self.wait()
        self.page.tables["warehouses"].selectRow(0)
        self.page.edit_responsible()
        form = self.page.findChildren(WarehouseForm)[-1]
        form.save.click()
        self.wait()
        self.assertEqual("Responsible", self.page.snapshot["warehouses"][0]["responsible"])
        self.page.pending_serial = "UI-SN-1"
        self.page.movement("receipt")
        form = self.page.findChildren(WarehouseForm)[-1]
        form.save.click()
        self.wait()
        self.assertEqual(1, self.page.snapshot["balances"][0]["quantity"])

    def test_failed_form_save_retains_fields_and_shows_localized_error(self):
        self.bootstrap()
        self.page.edit_warehouse()
        form = self.page.findChildren(WarehouseForm)[-1]
        form.fields["code"].setText("KEEP")
        form.save.click()
        self.wait()
        self.assertTrue(form.isVisible())
        self.assertEqual("KEEP", form.fields["code"].text())
        self.assertTrue(form.feedback.text())
        form.reject()

    def test_logout_clears_visible_data_even_when_server_is_unreachable(self):
        self.bootstrap()
        with patch.object(
            self.page.client, "call", side_effect=WarehouseError("wh_connection", 503)
        ):
            self.page.sign_out()
            self.assertEqual(0, self.page.stack.currentIndex())
            self.wait()
        self.assertEqual({}, self.page.user)
        self.assertEqual("", self.page.client.token)
        self.assertEqual(self.page.translate("wh_login"), self.page.login_button.text())
        self.assertTrue(self.page.login_confirm.isHidden())
        self.assertTrue(all(table.rowCount() == 0 for table in self.page.tables.values()))
