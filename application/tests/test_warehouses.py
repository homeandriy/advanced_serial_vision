from __future__ import annotations

import ipaddress
import ssl
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from openpyxl import Workbook
from serial_vision.warehouse.client import WarehouseClient
from serial_vision.warehouse.excel import HEADERS, read_warehouse_xlsx, save_template
from serial_vision.warehouse.inventory import InventoryRepository
from serial_vision.warehouse.security import WarehouseError, validate_password
from serial_vision.warehouse.server import WarehouseHttpServer
from serial_vision.warehouse.service import WarehouseService

PASSWORD = "AdminPass1_"
PERMANENT = "NewPass2+"


class WarehouseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.repository = InventoryRepository(self.root / "warehouse.sqlite3")
        self.service = WarehouseService(self.repository)
        self.admin = self.service.invoke(
            "bootstrap", {"email": "ADMIN@example.test", "name": "Admin", "password": PASSWORD}
        )
        self.token = str(self.admin["token"])
        self.model = self.invoke("models")["rows"][0]["id"]
        self.a = self.invoke(
            "save_warehouse", {"code": "A", "name": "Alpha", "address": "Address A"}
        )["id"]
        self.b = self.invoke(
            "save_warehouse", {"code": "B", "name": "Beta", "address": "Address B"}
        )["id"]

    def tearDown(self) -> None:
        self.directory.cleanup()

    def invoke(self, action, data=None, token=None):
        return self.service.invoke(action, data or {}, self.token if token is None else token)

    def new_user(self, role="storekeeper", warehouse_ids=None):
        created = self.invoke(
            "create_user",
            {
                "email": f"{uuid.uuid4()}@example.test",
                "name": "Operator",
                "role": role,
                "warehouse_ids": warehouse_ids or [],
            },
        )
        user = next(row for row in self.invoke("users")["rows"] if row["id"] == created["id"])
        login = self.invoke(
            "login", {"email": user["email"], "password": created["temporary_password"]}, token=""
        )
        return created, login

    def ready_user(self, role="storekeeper", warehouse_ids=None):
        created, login = self.new_user(role, warehouse_ids)
        changed = self.invoke(
            "change_password",
            {"old_password": created["temporary_password"], "password": PERMANENT},
            token=login["token"],
        )
        return created, changed

    def receipt(self, serial="SN-1", destination=None, token=None, request_id=None):
        return self.invoke(
            "move",
            {
                "kind": "receipt",
                "serial": serial,
                "destination_id": destination or self.a,
                "model_id": self.model,
                "request_id": request_id or str(uuid.uuid4()),
            },
            token,
        )

    def assert_error(self, code, action, data=None, token=None):
        with self.assertRaises(WarehouseError) as error:
            self.invoke(action, data, token)
        self.assertEqual(code, error.exception.code)

    def test_first_admin_is_unique_even_during_concurrent_setup(self):
        other = WarehouseService(InventoryRepository(self.root / "other.sqlite3"))

        def bootstrap(index):
            try:
                other.invoke(
                    "bootstrap",
                    {"email": f"{index}@example.test", "name": "Admin", "password": PASSWORD},
                )
                return "ok"
            except WarehouseError as error:
                return error.code

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(bootstrap, [1, 2]))
        self.assertCountEqual(["ok", "wh_already_initialized"], results)

    def test_bootstrap_shared_service_requires_private_key(self):
        protected = WarehouseService(
            InventoryRepository(self.root / "shared.sqlite3"), "private-key-" * 4
        )
        with self.assertRaises(WarehouseError):
            protected.invoke(
                "bootstrap", {"email": "admin@example.test", "name": "Admin", "password": PASSWORD}
            )
        self.assertFalse(protected.invoke("status", {})["initialized"])
        self.assertTrue(
            protected.invoke(
                "bootstrap",
                {
                    "email": "admin@example.test",
                    "name": "Admin",
                    "password": PASSWORD,
                    "bootstrap_key": "private-key-" * 4,
                },
            )["token"]
        )

    def test_password_policy_includes_all_requested_requirements(self):
        for value in (
            "Short1_",
            "nocapital1_",
            "NOLOWER1_",
            "NoDigits_",
            "NoSpecial1",
            "a" * 300,
            None,
        ):
            with self.subTest(value=value), self.assertRaises(WarehouseError):
                validate_password(value)
        for value in (
            "Abcdef1+",
            "Abcdef1-",
            "Abcdef1*",
            "Abcdef1/",
            "Abcdef1=",
            "Abcdef1_",
            "Abcdef1<",
            "Abcdef1>",
            "Abcdef1?",
            "Abcdef1`",
            "Abcdef1~",
            "Пароль12_",
        ):
            self.assertEqual(value, validate_password(value))

    def test_temporary_password_cannot_access_any_business_or_admin_action(self):
        created, login = self.new_user("admin")
        for action in ("warehouses", "move", "create_user", "issue_token", "translations"):
            self.assert_error("wh_password_change_required", action, token=login["token"])
        self.assert_error(
            "wh_password_reused",
            "change_password",
            {
                "old_password": created["temporary_password"],
                "password": created["temporary_password"],
            },
            login["token"],
        )
        changed = self.invoke(
            "change_password",
            {"old_password": created["temporary_password"], "password": PERMANENT},
            login["token"],
        )
        self.assertFalse(changed["user"]["must_change"])
        self.assert_error("wh_login_required", "me", token=login["token"])
        self.assertTrue(self.invoke("users", token=changed["token"])["rows"])

    def test_login_normalizes_email_and_rate_limits_failures(self):
        signed = self.invoke(
            "login", {"email": " admin@EXAMPLE.TEST ", "password": PASSWORD}, token=""
        )
        self.assertEqual("admin@example.test", signed["user"]["email"])
        for _ in range(5):
            self.assert_error(
                "wh_login_invalid",
                "login",
                {"email": "admin@example.test", "password": "bad"},
                token="",
            )
        self.assert_error(
            "wh_login_limited",
            "login",
            {"email": "admin@example.test", "password": PASSWORD},
            token="",
        )

    def test_permissions_apply_to_queries_writes_and_token_api(self):
        created, login = self.ready_user(warehouse_ids=[self.a])
        token = login["token"]
        self.assertEqual(
            [self.a], [row["id"] for row in self.invoke("warehouses", token=token)["rows"]]
        )
        self.assert_error("wh_forbidden", "users", token=token)
        self.assert_error(
            "wh_forbidden",
            "save_warehouse",
            {"code": "X", "name": "Hidden", "address": "Hidden"},
            token,
        )
        self.assert_error("wh_forbidden", "responsible_history", {"warehouse_id": self.b}, token)
        self.receipt(token=token)
        self.assert_error(
            "wh_forbidden",
            "move",
            {
                "kind": "transfer",
                "serial": "SN-1",
                "source_id": self.a,
                "destination_id": self.b,
                "model_id": self.model,
                "request_id": "blocked",
            },
            token,
        )
        self.invoke(
            "update_user",
            {"id": created["id"], "role": "storekeeper", "active": True, "warehouse_ids": []},
        )
        self.assertEqual([], self.invoke("balances", token=token)["rows"])

    def test_manager_sees_every_warehouse_but_cannot_manage_users(self):
        _, login = self.ready_user("manager")
        self.assertEqual(2, len(self.invoke("warehouses", token=login["token"])["rows"]))
        self.assert_error("wh_forbidden", "create_user", token=login["token"])

    def test_transfers_are_atomic_and_retries_are_idempotent(self):
        first = self.receipt(request_id="receipt-1")
        self.assertEqual(first, self.receipt(request_id="receipt-1"))
        data = {
            "kind": "transfer",
            "serial": "sn-1",
            "source_id": self.a,
            "destination_id": self.b,
            "model_id": self.model,
            "request_id": "transfer-1",
        }
        transfer = self.invoke("move", data)
        self.assertEqual(transfer, self.invoke("move", data))
        self.assert_error("wh_request_conflict", "move", {**data, "serial": "SN-2"})
        self.assertEqual(self.b, self.invoke("balances")["rows"][0]["warehouse_id"])
        self.assertEqual(2, self.invoke("movements")["total"])
        self.assert_error("wh_no_stock", "move", {**data, "request_id": "new"})
        self.assertEqual(2, self.invoke("movements")["total"])

    def test_concurrent_issues_cannot_produce_negative_stock(self):
        self.receipt()

        def issue(index):
            try:
                self.invoke(
                    "move",
                    {
                        "kind": "issue",
                        "serial": "SN-1",
                        "source_id": self.a,
                        "model_id": self.model,
                        "request_id": str(index),
                    },
                )
                return "ok"
            except WarehouseError as error:
                return error.code

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(issue, [1, 2]))
        self.assertCountEqual(["ok", "wh_no_stock"], results)
        self.assertEqual([], self.invoke("balances")["rows"])
        self.assertEqual(2, self.invoke("movements")["total"])

    def test_responsible_history_and_movement_snapshots_are_preserved(self):
        self.invoke(
            "save_responsible",
            {
                "warehouse_id": self.a,
                "name": "First",
                "position": "Head",
                "phone": "+380000000000",
                "email": "first@example.test",
            },
        )
        self.receipt()
        self.invoke("save_responsible", {"warehouse_id": self.a, "name": "Second"})
        rows = self.invoke("responsible_history", {"warehouse_id": self.a})["rows"]
        self.assertEqual(2, len(rows))
        self.assertIsNone(rows[0]["ended_at"])
        self.assertIsNotNone(rows[1]["ended_at"])
        self.assertEqual("First", self.invoke("movements")["rows"][0]["destination_responsible"])
        self.assertEqual("Second", self.invoke("balances")["rows"][0]["responsible"])

    def test_import_is_atomic_and_repeated_codes_are_skipped(self):
        rows = [
            {
                "code": "NEW",
                "name": "New",
                "address": "Address",
                "responsible_name": "Person",
                "email": "person@example.test",
            }
        ]
        self.assert_error(
            "wh_input_invalid", "import_warehouses", {"rows": [*rows, {"code": "BAD", "name": ""}]}
        )
        self.assertEqual(2, len(self.invoke("warehouses")["rows"]))
        self.assertEqual(
            {"added": 1, "skipped": 0}, self.invoke("import_warehouses", {"rows": rows})
        )
        self.assertEqual(
            {"added": 0, "skipped": 1}, self.invoke("import_warehouses", {"rows": rows})
        )
        warehouse = next(row for row in self.invoke("warehouses")["rows"] if row["code"] == "NEW")
        self.assertEqual("Person", warehouse["responsible"])

    def test_cannot_deactivate_last_admin_or_warehouse_with_stock(self):
        self.assert_error(
            "wh_last_admin",
            "update_user",
            {"id": self.admin["user"]["id"], "role": "storekeeper", "active": False},
        )
        self.receipt()
        self.assert_error(
            "wh_has_stock",
            "save_warehouse",
            {"id": self.a, "code": "A", "name": "Alpha", "address": "Address", "active": False},
        )

    def test_api_tokens_scopes_revocation_and_user_creation(self):
        limited = self.invoke("issue_token", {"name": "Stock API", "scope": "warehouse"})["token"]
        self.assert_error("wh_forbidden", "create_user", token=limited)
        token = self.invoke("issue_token", {"name": "Admin API", "scope": "admin"})["token"]
        created = self.invoke(
            "create_user",
            {"email": "via-api@example.test", "name": "API", "role": "storekeeper"},
            token,
        )
        self.assertTrue(created["temporary_password"])
        row = next(row for row in self.invoke("tokens")["rows"] if row["name"] == "Admin API")
        self.invoke("revoke_token", {"hash": row["hash"]})
        self.assert_error("wh_login_required", "users", token=token)

    def test_translation_requires_original_placeholders(self):
        self.assert_error(
            "wh_translation_invalid",
            "save_translation",
            {"locale": "uk", "key": "wh_page", "value": "Wrong {secret}"},
        )
        self.invoke(
            "save_translation",
            {"locale": "uk", "key": "wh_page", "value": "{page}/{pages}: {total}"},
        )
        self.assertEqual("{page}/{pages}: {total}", self.invoke("translations")["rows"][0]["value"])

    def test_disabled_users_and_expired_tokens_lose_access(self):
        created, login = self.ready_user(warehouse_ids=[self.a])
        self.invoke("update_user", {"id": created["id"], "role": "storekeeper", "active": False})
        self.assert_error("wh_login_required", "warehouses", token=login["token"])
        with self.repository.connection(True) as db:
            db.execute("UPDATE wh_tokens SET expires=?", (time.time() - 1,))
        self.assert_error("wh_login_required", "me")

    def test_xlsx_template_and_parser_preserve_contact_fields(self):
        destination = self.root / "template.xlsx"
        save_template(destination)
        book = Workbook()
        sheet = book.active
        sheet.title = "Warehouses"
        sheet.append(HEADERS)
        sheet.append(
            [
                "EXCEL",
                "Excel",
                "Address",
                "Note",
                True,
                "Person",
                "Position",
                "+380123",
                "person@example.test",
            ]
        )
        book.save(destination)
        book.close()
        values = read_warehouse_xlsx(destination)
        self.assertTrue(values[0]["active"])
        self.assertEqual("+380123", values[0]["phone"])

    def test_http_clients_share_one_database_and_sessions_stay_separate(self):
        server = WarehouseHttpServer(("127.0.0.1", 0), self.service)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            first, second = (
                WarehouseClient(self.root / "unused1", url),
                WarehouseClient(self.root / "unused2", url),
            )
            first.call("login", {"email": "admin@example.test", "password": PASSWORD})
            second.call("login", {"email": "admin@example.test", "password": PASSWORD})
            self.assertNotEqual(first.token, second.token)
            first.call("save_warehouse", {"code": "RDP", "name": "Shared", "address": "Server"})
            self.assertEqual(3, len(second.call("warehouses")["rows"]))
            first.call("logout")
            self.assertEqual(3, len(second.call("warehouses")["rows"]))
            self.assertFalse((self.root / "unused1").exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_tls_clients_require_trusted_server_identity(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
            .not_valid_after(datetime.now(UTC) + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
                ),
                critical=False,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False
            )
            .sign(key, hashes.SHA256())
        )
        certificate, private = self.root / "test.crt", self.root / "test.key"
        certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        private.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, private)
        server = WarehouseHttpServer(("127.0.0.1", 0), self.service, context)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            url = f"https://127.0.0.1:{server.server_port}"
            trusted = WarehouseClient(self.root / "unused", url, certificate)
            self.assertTrue(
                trusted.call("login", {"email": "admin@example.test", "password": PASSWORD})[
                    "token"
                ]
            )
            untrusted = WarehouseClient(self.root / "unused", url)
            with self.assertRaises(WarehouseError):
                untrusted.call("status")
            self.assertFalse((self.root / "unused").exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_filters_preserve_warehouse_model_and_responsible_scopes(self):
        self.invoke("save_responsible", {"warehouse_id": self.a, "name": "АНДРІЙ"})
        self.receipt()
        self.assertEqual(
            1,
            len(
                self.invoke(
                    "balances",
                    {"warehouse_id": self.a, "model_id": self.model, "responsible": "андрій"},
                )["rows"]
            ),
        )
        self.assertEqual(
            1,
            self.invoke(
                "movements",
                {"warehouse_id": self.a, "model_id": self.model, "responsible": "андрій"},
            )["total"],
        )
        self.assertEqual(0, self.invoke("movements", {"warehouse_id": self.b})["total"])

    def test_people_directory_updates_append_history_in_every_assigned_warehouse(self):
        person = self.invoke(
            "save_person",
            {
                "name": "Person",
                "position": "Position",
                "phone": "123",
                "email": "person@example.test",
            },
        )["id"]
        for warehouse in (self.a, self.b):
            self.invoke("save_responsible", {"warehouse_id": warehouse, "person_id": person})
        self.receipt()
        self.invoke(
            "save_person",
            {
                "id": person,
                "name": "Changed",
                "position": "Head",
                "phone": "456",
                "email": "person@example.test",
            },
        )
        for warehouse in (self.a, self.b):
            rows = self.invoke("responsible_history", {"warehouse_id": warehouse})["rows"]
            self.assertEqual("Changed", rows[0]["name"])
            self.assertEqual("Person", rows[1]["name"])
            self.assertEqual("123", rows[1]["phone"])
        self.assertEqual("Person", self.invoke("movements")["rows"][0]["destination_responsible"])
        self.assert_error(
            "wh_person_assigned", "save_person", {"id": person, "name": "Changed", "active": False}
        )

    def test_http_rejects_browser_origins_and_has_no_anonymous_data_routes(self):
        server = WarehouseHttpServer(("127.0.0.1", 0), self.service)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = urllib.request.Request(
                base + "/api/v1/warehouse/warehouses",
                data=b"{}",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(401, error.exception.code)
            request = urllib.request.Request(
                base + "/api/v1/warehouse/status", headers={"Origin": "https://malicious.example"}
            )
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(403, error.exception.code)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
