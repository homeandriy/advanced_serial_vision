from __future__ import annotations

import json
import ssl
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from serial_vision.warehouse.inventory import InventoryRepository
from serial_vision.warehouse.security import WarehouseError
from serial_vision.warehouse.service import WarehouseService


def object_response(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise WarehouseError("wh_connection", 503)
    return dict(value)


def response_rows(result: dict[str, object]) -> list[dict[str, object]]:
    values = result.get("rows", [])
    if not isinstance(values, list):
        raise WarehouseError("wh_connection", 503)
    return [object_response(row) for row in values]


class WarehouseClient:
    def __init__(self, local_path: Path, server_url: str = "", ca_file: Path | None = None) -> None:
        self.path, self.server_url, self.token = local_path, server_url.rstrip("/"), ""
        self._service: WarehouseService | None = None
        self._init_lock = threading.Lock()
        self.ca_file = ca_file
        self._ssl_context: ssl.SSLContext | None = None
        self.configuration_error: WarehouseError | None = None
        if server_url:
            parsed = urlsplit(server_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
                or (
                    parsed.scheme == "http"
                    and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                )
            ):
                self.configuration_error = WarehouseError("wh_server_url")

    def requires_account_hint(self) -> bool:
        return bool(self.server_url) or self.path.exists()

    def call(self, action: str, data: dict[str, object] | None = None) -> dict[str, object]:
        if self.configuration_error:
            raise self.configuration_error
        payload = data or {}
        if self.server_url:
            request = urllib.request.Request(
                self.server_url + "/api/v1/warehouse/" + action,
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                {"Content-Type": "application/json", "Authorization": "Bearer " + self.token},
            )
            try:
                # Warehouse sessions never follow redirects with credentials.
                if self.server_url.startswith("https://") and self._ssl_context is None:
                    self._ssl_context = ssl.create_default_context(
                        cafile=str(self.ca_file) if self.ca_file else None
                    )
                opener = urllib.request.build_opener(
                    NoRedirect(),
                    urllib.request.ProxyHandler({}),
                    urllib.request.HTTPSHandler(context=self._ssl_context),
                )
                with opener.open(request, timeout=20) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024:
                        raise WarehouseError("wh_connection", 503)
                    result = object_response(json.loads(raw))
            except urllib.error.HTTPError as error:
                try:
                    failure = object_response(json.loads(error.read(16384)))
                    code = str(failure.get("error", "wh_connection"))
                except (ValueError, WarehouseError):
                    code = "wh_connection"
                raise WarehouseError(code, error.code) from error
            except (OSError, ValueError) as error:
                raise WarehouseError("wh_connection", 503) from error
        else:
            with self._init_lock:
                if self._service is None:
                    self._service = WarehouseService(InventoryRepository(self.path))
            result = self._service.invoke(action, payload, self.token)
        if action in {"bootstrap", "login", "change_password"}:
            self.token = str(result["token"])
        if action == "logout":
            self.token = ""
        return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
