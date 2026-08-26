from __future__ import annotations

import csv
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Iterator


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS device_models (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    device_type TEXT NOT NULL CHECK(device_type IN ('tuner', 'modem')),
                    service TEXT NOT NULL CHECK(service IN ('internet', 'television')),
                    UNIQUE(name, device_type, service)
                );
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY,
                    recognized_text TEXT NOT NULL,
                    contract_number TEXT,
                    operation_type TEXT NOT NULL CHECK(operation_type IN ('receipt', 'issue')),
                    source_image_path TEXT,
                    device_model_id INTEGER NOT NULL REFERENCES device_models(id) ON DELETE RESTRICT,
                    registered_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS devices_registered_at_idx ON devices(registered_at);
                CREATE TABLE IF NOT EXISTS ai_agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL CHECK(provider IN ('openai', 'anthropic', 'gemini')),
                    model TEXT NOT NULL,
                    credential_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS application_state (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    launch_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )
            count = db.execute("SELECT COUNT(*) FROM device_models").fetchone()[0]
            if count == 0:
                db.executemany(
                    "INSERT INTO device_models(name, device_type, service) VALUES (?, ?, ?)",
                    [(name, "modem", "internet") for name in DEFAULT_MODELS],
                )

    def setting(self, key: str, default: str = "") -> str:
        with self.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return default if row is None else str(row["value"])

    def has_setting(self, key: str) -> bool:
        with self.connection() as db:
            return db.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone() is not None

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def register_launch(self) -> int:
        now = datetime.now(UTC).isoformat()
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO application_state(id, launch_count, updated_at) VALUES (1, 0, ?)", (now,))
            db.execute("UPDATE application_state SET launch_count = launch_count + 1, updated_at = ? WHERE id = 1", (now,))
            return int(db.execute("SELECT launch_count FROM application_state WHERE id = 1").fetchone()[0])

    def ai_agents(self) -> list[sqlite3.Row]:
        with self.connection() as db:
            return db.execute("SELECT id, name, provider, model, credential_id FROM ai_agents ORDER BY name").fetchall()

    def save_ai_agent(self, name: str, provider: str, model: str, credential_id: str, agent_id: str | None = None) -> str:
        identifier = agent_id or str(uuid.uuid4())
        with self.connection() as db:
            db.execute(
                """INSERT INTO ai_agents(id, name, provider, model, credential_id) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, provider=excluded.provider, model=excluded.model, credential_id=excluded.credential_id""",
                (identifier, name, provider, model, credential_id),
            )
        return identifier

    def delete_ai_agent(self, agent_id: str) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM ai_agents WHERE id = ?", (agent_id,))

    def models(self, device_type: str = "", service: str = "") -> list[sqlite3.Row]:
        conditions, params = [], []
        if device_type:
            conditions.append("device_type = ?")
            params.append(device_type)
        if service:
            conditions.append("service = ?")
            params.append(service)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.connection() as db:
            return db.execute(f"SELECT * FROM device_models {where} ORDER BY name", params).fetchall()

    def popular_models(self, limit: int = 10) -> list[sqlite3.Row]:
        with self.connection() as db:
            used = db.execute("SELECT m.id, m.name, COUNT(d.id) AS usage_count FROM device_models m JOIN devices d ON d.device_model_id = m.id GROUP BY m.id, m.name ORDER BY usage_count DESC, m.name LIMIT ?", (limit,)).fetchall()
            used_ids = {row["id"] for row in used}
            placeholders = ",".join("?" for _ in DEFAULT_MODELS)
            defaults = db.execute(f"SELECT id, name, 0 AS usage_count FROM device_models WHERE name IN ({placeholders})", DEFAULT_MODELS).fetchall()
        fallback = sorted((row for row in defaults if row["id"] not in used_ids), key=lambda row: DEFAULT_MODELS.index(row["name"]))
        return [*used, *fallback][:limit]

    def save_model(self, model_id: int | None, name: str, device_type: str, service: str) -> None:
        with self.connection() as db:
            if model_id is None:
                db.execute("INSERT INTO device_models(name, device_type, service) VALUES (?, ?, ?)", (name, device_type, service))
            else:
                db.execute("UPDATE device_models SET name=?, device_type=?, service=? WHERE id=?", (name, device_type, service, model_id))

    def delete_model(self, model_id: int) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM device_models WHERE id = ?", (model_id,))

    def devices(self, search: str = "", device_type: str = "", service: str = "", date_from: str = "", date_to: str = "", model_id: int | None = None, operation: str = "", page: int = 1, per_page: int = 100) -> tuple[list[sqlite3.Row], dict[str, int] | None]:
        conditions, params = [], []
        if search:
            conditions.append("(d.recognized_text LIKE ? OR d.contract_number LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if device_type:
            conditions.append("m.device_type = ?")
            params.append(device_type)
        if service:
            conditions.append("m.service = ?")
            params.append(service)
        if date_from:
            conditions.append("d.registered_at >= ?")
            params.append(self._utc_boundary(date_from, end=False))
        if date_to:
            conditions.append("d.registered_at <= ?")
            params.append(self._utc_boundary(date_to, end=True))
        if model_id is not None:
            conditions.append("d.device_model_id = ?")
            params.append(model_id)
        if operation:
            conditions.append("d.operation_type = ?")
            params.append(operation)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT d.*, m.name AS model_name, m.device_type, m.service
            FROM devices d JOIN device_models m ON m.id = d.device_model_id
            {where} ORDER BY d.registered_at DESC, d.id DESC
        """
        with self.connection() as db:
            total = int(db.execute(f"SELECT COUNT(*) FROM devices d JOIN device_models m ON m.id = d.device_model_id {where}", params).fetchone()[0])
            if total <= 5000:
                return db.execute(query, params).fetchall(), None
            pages = max(1, (total + per_page - 1) // per_page)
            page = min(max(1, page), pages)
            rows = db.execute(query + " LIMIT ? OFFSET ?", [*params, per_page, (page - 1) * per_page]).fetchall()
            return rows, {"page": page, "per_page": per_page, "total": total, "pages": pages}

    @staticmethod
    def _utc_boundary(value: str, end: bool) -> str:
        local = datetime.fromisoformat(f"{value}T23:59:59" if end else f"{value}T00:00:00")
        return local.replace(tzinfo=ZoneInfo("Europe/Kyiv")).astimezone(UTC).isoformat()

    def save_device(self, device_id: int | None, data: dict[str, object]) -> None:
        values = (
            str(data["recognized_text"]).strip(),
            str(data["contract_number"]).strip() or None,
            str(data["operation_type"]),
            str(data["source_image_path"]) or None,
            int(data["device_model_id"]),
            str(data["registered_at"]),
        )
        with self.connection() as db:
            if device_id is None:
                db.execute("""INSERT INTO devices(recognized_text, contract_number, operation_type, source_image_path, device_model_id, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?)""", values)
            else:
                db.execute("""UPDATE devices SET recognized_text=?, contract_number=?, operation_type=?, source_image_path=?, device_model_id=?, registered_at=?
                    WHERE id=?""", (*values, device_id))

    def delete_device(self, device_id: int) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM devices WHERE id = ?", (device_id,))

    def export_csv(self, destination: Path, rows: list[sqlite3.Row]) -> None:
        with destination.open("w", newline="", encoding="cp1251", errors="replace") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["Дата", "Номер договору", "Операція", "Текст", "Модель", "Тип", "Послуга", "Шлях до фото"])
            for row in rows:
                writer.writerow([row["registered_at"], row["contract_number"] or "", row["operation_type"], row["recognized_text"], row["model_name"], row["device_type"], row["service"], row["source_image_path"] or ""])

    def statistics_rows(self) -> list[sqlite3.Row]:
        with self.connection() as db:
            return db.execute("SELECT d.registered_at, d.operation_type, m.service, m.name AS model_name FROM devices d JOIN device_models m ON m.id = d.device_model_id").fetchall()

    def statistics(self) -> list[sqlite3.Row]:
        with self.connection() as db:
            return db.execute("""SELECT substr(d.registered_at, 1, 7) AS period, d.operation_type, COUNT(*) AS total
                FROM devices d GROUP BY period, d.operation_type ORDER BY period""").fetchall()


DEFAULT_MODELS = (
    "Оптичний термінал GPON G-010G-P Nokia",
    "Оптичний термінал GPON G-010G-Q(R) NOKIA",
    "Оптичний термінал GPON G-140W-G NOKIA",
    "Маршрутизатор TP-Link EC220-F5",
    "Arris CM820",
)
