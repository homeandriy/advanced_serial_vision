from __future__ import annotations

import argparse
import json
import logging
import signal
import sqlite3
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from serial_vision.warehouse.client import object_response
from serial_vision.warehouse.inventory import InventoryRepository
from serial_vision.warehouse.security import WarehouseError
from serial_vision.warehouse.service import WarehouseService


class WarehouseHttpServer(ThreadingHTTPServer):
    daemon_threads = False
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int], service: WarehouseService, tls: ssl.SSLContext | None = None
    ) -> None:
        self.service = service
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)
        if tls is not None:
            self.socket = tls.wrap_socket(
                self.socket, server_side=True, do_handshake_on_connect=False
            )

    def process_request(self, request, client_address) -> None:
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address) -> None:
        logging.warning("Warehouse connection closed during protocol or TLS negotiation")


class Handler(BaseHTTPRequestHandler):
    server: WarehouseHttpServer

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format: str, *args: object) -> None:
        pass  # Credentials, tokens and request bodies never enter access logs.

    def do_GET(self) -> None:
        self.handle_request(get=True)

    def do_POST(self) -> None:
        self.handle_request()

    def handle_request(self, get: bool = False) -> None:
        try:
            if self.headers.get("Origin") or self.headers.get("Host", "").split(":")[0] not in {
                "127.0.0.1",
                "localhost",
            }:
                raise WarehouseError("wh_forbidden", 403)
            prefix = "/api/v1/warehouse/"
            action = self.path.removeprefix(prefix)
            if not self.path.startswith(prefix) or "/" in action or "?" in action:
                raise WarehouseError("wh_not_found", 404)
            data: dict[str, object] = {}
            if get:
                if action != "status":
                    raise WarehouseError("wh_not_found", 404)
            else:
                if self.headers.get_content_type() != "application/json":
                    raise WarehouseError("wh_input_invalid", 415)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2 * 1024 * 1024:
                    raise WarehouseError("wh_input_invalid", 413)
                data = object_response(json.loads(self.rfile.read(length)))
            authorization = self.headers.get("Authorization", "")
            token = authorization[7:] if authorization.startswith("Bearer ") else ""
            result = self.server.service.invoke(action, data, token)
            self.reply(200, result)
        except WarehouseError as error:
            self.reply(error.status, {"error": error.code})
        except (ValueError, TypeError, sqlite3.IntegrityError):
            self.reply(422, {"error": "wh_input_invalid"})
        except Exception:
            logging.exception("Warehouse request failed")
            self.reply(503, {"error": "wh_connection"})

    def reply(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serial Vision shared warehouse service (RDP loopback)"
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-key-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=4557)
    parser.add_argument("--tls-cert", type=Path, required=True)
    parser.add_argument("--tls-key", type=Path, required=True)
    args = parser.parse_args()
    key = args.bootstrap_key_file.read_text(encoding="utf-8").strip()
    if len(key) < 32:
        parser.error(
            "Bootstrap key must contain at least 32 characters; keep this file private to Windows administrators and the service account."
        )
    service = WarehouseService(InventoryRepository(args.data_dir / "warehouses.sqlite3"), key)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.tls_cert, args.tls_key)
    server = WarehouseHttpServer(("127.0.0.1", args.port), service, context)

    def stop(*_args: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
