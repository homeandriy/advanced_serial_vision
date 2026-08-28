from __future__ import annotations

import hashlib
import json
import mimetypes
import threading
from pathlib import Path
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from serial_vision.application_service import SerialVisionService


class LocalApiServer:
    def __init__(self, service: SerialVisionService) -> None:
        self.service = service
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.last_request: dict[str, float] = {}
        self.lock = threading.Lock()

    def start(self) -> None:
        if self.server is not None:
            return
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None: pass
            def do_GET(self) -> None: owner.handle(self)
            def do_POST(self) -> None: owner.handle(self)
            def do_PATCH(self) -> None: owner.handle(self)
            def do_DELETE(self) -> None: owner.handle(self)
        self.server = ThreadingHTTPServer(("127.0.0.1", self.service.api_port()), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, name="serial-vision-api", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is None:
            return
        self.server.shutdown(); self.server.server_close(); self.server = None; self.thread = None

    def restart(self) -> None:
        self.stop()
        if self.service.api_enabled(): self.start()

    def handle(self, request: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(request.path); path = parsed.path; key_id: str | None = None; status = 500; detail = ""
        try:
            if path == "/api/v1/health":
                status = 200; return self.reply(request, status, {"status": "ok"})
            if path == "/api/v1/openapi.json":
                status = 200; return self.reply(request, status, self.openapi())
            if path == "/api/v1/docs":
                status = 200; return self.html(request, self.docs_html())
            key_id = self.authorize(request)
            status, payload = self.dispatch(request.command, path, parse_qs(parsed.query), self.body(request))
            if isinstance(payload, ImageStream):
                return self.file_reply(request, status, payload)
            if isinstance(payload, GeneratedCodeStream):
                return self.generated_code_reply(request, status, payload)
            return self.reply(request, status, payload)
        except ApiError as error:
            status, detail = error.status, error.message; return self.reply(request, status, {"error": detail})
        except (ValueError, KeyError) as error:
            status, detail = 422, str(error); return self.reply(request, status, {"error": detail})
        finally:
            self.service._database.audit_api(key_id, request.command, path, status, request.client_address[0], detail)

    def authorize(self, request: BaseHTTPRequestHandler) -> str:
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise ApiError(401, "Bearer token required")
        token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
        key = self.service._database.api_key_by_hash(token_hash)
        if key is None or key["revoked_at"]:
            raise ApiError(401, "Invalid or revoked API key")
        if key["expires_at"] and datetime.fromisoformat(key["expires_at"]) <= datetime.now(UTC):
            raise ApiError(401, "API key has expired")
        with self.lock:
            now = time.monotonic(); previous = self.last_request.get(key["id"], 0.0)
            if now - previous < int(key["min_interval_ms"]) / 1000:
                raise ApiError(429, "Rate limit exceeded")
            self.last_request[key["id"]] = now
        self.service._database.touch_api_key(key["id"])
        return str(key["id"])

    def dispatch(self, method: str, path: str, query: dict[str, list[str]], data: dict[str, object]) -> tuple[int, object]:
        parts = path.strip("/").split("/")
        if parts[:2] != ["api", "v1"] or len(parts) < 3:
            raise ApiError(404, "Not found")
        resource = parts[2]
        identifier = int(parts[3]) if len(parts) == 4 and parts[3].isdigit() else None
        if resource == "models":
            return self.models(method, identifier, data)
        if resource == "equipment":
            return self.equipment(method, identifier, query, data)
        if resource == "image":
            return self.image(method, parts, data)
        if resource == "code":
            return self.code(method, parts, data)
        raise ApiError(404, "Not found")

    def models(self, method: str, identifier: int | None, data: dict[str, object]) -> tuple[int, object]:
        rows = self.service.models()
        if method == "GET":
            result = [self.model(row) for row in rows]
            return 200, next((row for row in result if row["id"] == identifier), result) if identifier else result
        if method == "POST":
            self.service.add_model(str(data["name"]), str(data["device_type"]), str(data["service"])); return 201, {"created": True}
        if method == "PATCH" and identifier:
            self.service.update_model(identifier, str(data["name"]), str(data["device_type"]), str(data["service"])); return 200, {"updated": True}
        if method == "DELETE" and identifier:
            self.service.delete_model(identifier); return 204, None
        raise ApiError(405, "Method not allowed")

    def equipment(self, method: str, identifier: int | None, query: dict[str, list[str]], data: dict[str, object]) -> tuple[int, object]:
        rows = self.service.all_filtered_devices(query.get("search", [""])[0], query.get("type", [""])[0], query.get("service", [""])[0], query.get("date_from", [""])[0], query.get("date_to", [""])[0], int(query["model_id"][0]) if "model_id" in query else None, query.get("operation", [""])[0])
        if method == "GET":
            result = [self.device(row) for row in rows]
            return 200, next((row for row in result if row["id"] == identifier), result) if identifier else result
        required = {"recognized_text", "contract_number", "operation_type", "device_model_id", "registered_at"}
        if method in {"POST", "PATCH"} and not required <= data.keys(): raise ApiError(422, "Missing equipment fields")
        if method == "POST": self.service.add_device(data); return 201, {"created": True}
        if method == "PATCH" and identifier: self.service.update_device(identifier, data); return 200, {"updated": True}
        if method == "DELETE" and identifier: self.service.delete_device(identifier); return 204, None
        raise ApiError(405, "Method not allowed")

    def image(self, method: str, parts: list[str], data: dict[str, object]) -> tuple[int, object]:
        if method == "GET" and len(parts) == 5 and parts[3] == "check" and parts[4].isdigit():
            record_id = int(parts[4])
            image_path = self.available_image(record_id)
            return 200, {"record_id": record_id, "image_name": image_path.name, "available": True}
        if method == "POST" and len(parts) == 4 and parts[3] == "get":
            try:
                record_id = int(data["record_id"])
            except (KeyError, TypeError, ValueError) as error:
                raise ApiError(422, "record_id must be an integer") from error
            image_path = self.available_image(record_id)
            content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
            return 200, ImageStream(image_path, content_type)
        raise ApiError(405, "Method not allowed")

    def code(self, method: str, parts: list[str], data: dict[str, object]) -> tuple[int, object]:
        if method != "POST" or len(parts) != 4 or parts[3] != "get":
            raise ApiError(405, "Method not allowed")
        try:
            record_id = int(data["record_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ApiError(422, "record_id must be an integer") from error
        content = self.service.device_recognized_text(record_id)
        if content is None:
            raise ApiError(404, "Equipment record not found")
        try:
            image_data = self.service.generate_code_png(content, str(data["type"]))
            filename = self.service.generated_code_filename(content, str(data["type"]))
        except KeyError as error:
            raise ApiError(422, "type must be qrcode or barcode") from error
        except ValueError as error:
            if str(error) == "code_type_invalid":
                raise ApiError(422, "type must be qrcode or barcode") from error
            raise ApiError(422, str(error)) from error
        return 200, GeneratedCodeStream(image_data, filename)

    def available_image(self, record_id: int) -> Path:
        image_path = self.service.source_image_path(record_id)
        if image_path is None:
            raise ApiError(404, "Equipment record not found")
        try:
            if not image_path.is_file():
                raise ApiError(409, "Source image is unavailable")
            with image_path.open("rb") as image:
                image.read(1)
        except OSError as error:
            raise ApiError(409, f"Source image is unreadable: {error.strerror or error}") from error
        return image_path

    @staticmethod
    def model(row: object) -> dict[str, object]: return {"id": row["id"], "name": row["name"], "device_type": row["device_type"], "service": row["service"], "usage_count": row["usage_count"]}
    @staticmethod
    def device(row: object) -> dict[str, object]:
        image_path = row["source_image_path"]
        return {
            "id": row["id"],
            "recognized_text": row["recognized_text"],
            "contract_number": row["contract_number"],
            "operation_type": row["operation_type"],
            "source_image_name": Path(image_path).name if image_path else None,
            "device_model_id": row["device_model_id"],
            "model_name": row["model_name"],
            "registered_at": row["registered_at"],
        }
    @staticmethod
    def body(request: BaseHTTPRequestHandler) -> dict[str, object]:
        length = int(request.headers.get("Content-Length", "0")); return json.loads(request.rfile.read(length) or b"{}") if length else {}
    @staticmethod
    def reply(request: BaseHTTPRequestHandler, status: int, payload: object) -> None:
        request.send_response(status)
        if status != 204:
            content = json.dumps(payload, ensure_ascii=False).encode(); request.send_header("Content-Type", "application/json; charset=utf-8"); request.send_header("Content-Length", str(len(content)))
        request.end_headers()
        if status != 204: request.wfile.write(content)
    @staticmethod
    def file_reply(request: BaseHTTPRequestHandler, status: int, image: "ImageStream") -> None:
        try:
            size = image.path.stat().st_size
            source = image.path.open("rb")
        except OSError as error:
            raise ApiError(409, f"Source image is unreadable: {error.strerror or error}") from error
        with source:
            filename = quote(image.path.name)
            request.send_response(status)
            request.send_header("Content-Type", image.content_type)
            request.send_header("Content-Length", str(size))
            request.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{filename}")
            request.end_headers()
            while chunk := source.read(64 * 1024):
                request.wfile.write(chunk)

    @staticmethod
    def generated_code_reply(request: BaseHTTPRequestHandler, status: int, image: "GeneratedCodeStream") -> None:
        filename = quote(image.filename)
        request.send_response(status)
        request.send_header("Content-Type", "image/png")
        request.send_header("Content-Length", str(len(image.data)))
        request.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{filename}")
        request.end_headers()
        request.wfile.write(image.data)

    @staticmethod
    def html(request: BaseHTTPRequestHandler, content: str) -> None:
        data = content.encode(); request.send_response(200); request.send_header("Content-Type", "text/html; charset=utf-8"); request.send_header("Content-Length", str(len(data))); request.end_headers(); request.wfile.write(data)
    def openapi(self) -> dict[str, object]:
        model = {
            "type": "object",
            "required": ["name", "device_type", "service"],
            "properties": {
                "id": {"type": "integer", "example": 1},
                "name": {"type": "string", "example": "Arris CM820"},
                "device_type": {"type": "string", "enum": ["modem", "tuner"]},
                "service": {"type": "string", "enum": ["internet", "television"]},
                "usage_count": {"type": "integer", "example": 3},
            },
        }
        equipment = {
            "type": "object",
            "required": ["recognized_text", "contract_number", "operation_type", "device_model_id", "registered_at"],
            "properties": {
                "id": {"type": "integer", "example": 1},
                "recognized_text": {"type": "string", "example": "SN: ABC123"},
                "contract_number": {"type": "string", "example": "12345", "nullable": True},
                "operation_type": {"type": "string", "enum": ["receipt", "issue"]},
                "source_image_name": {"type": "string", "example": "photo.jpg", "nullable": True, "readOnly": True, "description": "File name only; the local source path is never returned."},
                "device_model_id": {"type": "integer", "example": 2},
                "model_name": {"type": "string", "readOnly": True},
                "registered_at": {"type": "string", "format": "date-time", "example": "2026-08-26T18:00:00+00:00"},
            },
        }
        equipment_write = {
            **equipment,
            "properties": {
                **equipment["properties"],
                "source_image_path": {"type": "string", "nullable": True, "writeOnly": True},
            },
        }
        image_status = {
            "type": "object",
            "required": ["record_id", "image_name", "available"],
            "properties": {
                "record_id": {"type": "integer", "example": 1, "description": "Equipment record id, not device_model_id."},
                "image_name": {"type": "string", "example": "photo.jpg"},
                "available": {"type": "boolean", "example": True},
            },
        }
        image_get = {
            "type": "object",
            "required": ["record_id"],
            "properties": {"record_id": {"type": "integer", "example": 1, "description": "Equipment record id, not device_model_id."}},
        }
        code_get = {
            "type": "object",
            "required": ["record_id", "type"],
            "properties": {
                "record_id": {"type": "integer", "example": 1, "description": "Equipment record id, not device_model_id."},
                "type": {"type": "string", "enum": ["qrcode", "barcode"], "description": "barcode uses Code 128."},
            },
        }
        error = {"type": "object", "properties": {"error": {"type": "string", "example": "Bearer token required"}}}
        response = lambda description, schema: {"description": description, "content": {"application/json": {"schema": schema}}}
        errors = {
            "401": response("Missing, expired or revoked Bearer key", error),
            "404": response("Equipment record was not found", error),
            "409": response("Source image is unavailable", error),
            "422": response("Payload validation failed", error),
            "429": response("The key rate limit was exceeded", error),
        }
        body = lambda schema: {"required": True, "content": {"application/json": {"schema": schema}}}
        identifier = [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}]
        record_id = [{"name": "record_id", "in": "path", "required": True, "description": "Equipment record id, not device_model_id.", "schema": {"type": "integer"}}]
        return {
            "openapi": "3.0.3",
            "info": {"title": "Advanced Serial Vision Local API", "version": "v1", "description": "Local BAS integration API. Use the Authorize button with a Bearer key."},
            "servers": [{"url": f"http://127.0.0.1:{self.service.api_port()}/api/v1"}],
            "tags": [{"name": "Application Routes", "description": "Equipment, models, and source-image operations for BAS integrations"}],
            "security": [{"bearerAuth": []}],
            "components": {
                "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "API key", "description": "Paste the sv_ key issued by Advanced Serial Vision."}},
                "schemas": {"Model": model, "Equipment": equipment, "EquipmentWrite": equipment_write, "ImageStatus": image_status, "ImageGet": image_get, "CodeGet": code_get, "Error": error},
            },
            "paths": {
                "/health": {"get": {"tags": ["Application Routes"], "summary": "API health", "security": [], "responses": {"200": response("API is running", {"type": "object", "properties": {"status": {"type": "string", "example": "ok"}}})}}},
                "/models": {
                    "get": {"tags": ["Application Routes"], "summary": "List models", "responses": {"200": response("Model list", {"type": "array", "items": {"$ref": "#/components/schemas/Model"}}), **errors}},
                    "post": {"tags": ["Application Routes"], "summary": "Create model", "requestBody": body(model), "responses": {"201": response("Model created", {"type": "object"}), **errors}},
                },
                "/models/{id}": {
                    "patch": {"tags": ["Application Routes"], "summary": "Update model", "parameters": identifier, "requestBody": body(model), "responses": {"200": response("Model updated", {"type": "object"}), **errors}},
                    "delete": {"tags": ["Application Routes"], "summary": "Delete model", "parameters": identifier, "responses": {"204": {"description": "Model deleted"}, **errors}},
                },
                "/equipment": {
                    "get": {"tags": ["Application Routes"], "summary": "List equipment", "responses": {"200": response("Equipment list", {"type": "array", "items": {"$ref": "#/components/schemas/Equipment"}}), **errors}},
                    "post": {"tags": ["Application Routes"], "summary": "Create equipment", "requestBody": body(equipment_write), "responses": {"201": response("Equipment created", {"type": "object"}), **errors}},
                },
                "/equipment/{id}": {
                    "patch": {"tags": ["Application Routes"], "summary": "Update equipment", "parameters": identifier, "requestBody": body(equipment_write), "responses": {"200": response("Equipment updated", {"type": "object"}), **errors}},
                    "delete": {"tags": ["Application Routes"], "summary": "Delete equipment", "parameters": identifier, "responses": {"204": {"description": "Equipment deleted"}, **errors}},
                },
                "/image/check/{record_id}": {
                    "get": {"tags": ["Application Routes"], "summary": "Check source image availability", "description": "record_id is the id of an equipment record, not a model. The response contains no local path.", "parameters": record_id, "responses": {"200": response("Source image is available", image_status), **errors}},
                },
                "/image/get": {
                    "post": {"tags": ["Application Routes"], "summary": "Download source image", "description": "Use an equipment record id. The response is a binary stream; read the original filename with extension from the Content-Disposition header.", "requestBody": body(image_get), "responses": {"200": {"description": "Image byte stream; filename is in the standard Content-Disposition header", "headers": {"Content-Disposition": {"schema": {"type": "string"}, "description": "Original file name with extension (RFC-compatible attachment filename)"}}, "content": {"image/*": {"schema": {"type": "string", "format": "binary"}}}}, **errors}},
                },
                "/code/get": {
                    "post": {"tags": ["Application Routes"], "summary": "Generate QR or Code 128 barcode", "description": "record_id is the equipment record id, not device_model_id. Generates a PNG from recognized_text without changing the record. The filename is returned in Content-Disposition.", "requestBody": body(code_get), "responses": {"200": {"description": "Generated PNG byte stream. barcode uses Code 128.", "headers": {"Content-Disposition": {"schema": {"type": "string"}, "description": "Generated filename: qrcode_<code>_<H_M_d_m_Y>.png or barcode_<code>_<H_M_d_m_Y>.png."}}, "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}, **errors}},
                },
            },
        }

    @staticmethod
    def docs_html() -> str:
        return (Path(__file__).with_name("assets") / "swagger.html").read_text(encoding="utf-8")



class ImageStream:
    def __init__(self, path: Path, content_type: str) -> None:
        self.path = path
        self.content_type = content_type


class GeneratedCodeStream:
    def __init__(self, data: bytes, filename: str) -> None:
        self.data = data
        self.filename = filename


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None: self.status = status; self.message = message
