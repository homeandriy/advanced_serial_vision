from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from string import Formatter

from serial_vision.i18n import SUPPORTED_LOCALES, TEXT
from serial_vision.warehouse.repository import Repository, now
from serial_vision.warehouse.security import Principal, Role, WarehouseError, email_address, text


class InventoryRepository(Repository):
    @staticmethod
    def allowed(
        db: sqlite3.Connection, actor: Principal, identifier: str, active: bool = False
    ) -> sqlite3.Row:
        row = db.execute("SELECT * FROM wh_warehouses WHERE id=?", (identifier,)).fetchone()
        if not row or (
            actor.role == Role.STOREKEEPER
            and not db.execute(
                "SELECT 1 FROM wh_access WHERE user_id=? AND warehouse_id=?",
                (actor.user_id, identifier),
            ).fetchone()
        ):
            raise WarehouseError("wh_forbidden", 403)
        if active and not row["active"]:
            raise WarehouseError("wh_inactive", 409)
        return row

    @staticmethod
    def warehouse_values(data: dict[str, object]) -> tuple[str, str, str, str, int]:
        active = data.get("active", True)
        if not isinstance(active, bool):
            raise WarehouseError("wh_input_invalid")
        return (
            text(data, "code", 50).upper(),
            text(data, "name", 200),
            text(data, "address", 500),
            text(data, "note", 1000, False),
            int(active),
        )

    def warehouses(self, actor: Principal) -> dict[str, object]:
        with self.connection() as db:
            return {
                "rows": [
                    dict(row)
                    for row in db.execute(
                        "SELECT w.*, r.person_id, COALESCE(r.name,'') AS responsible,COALESCE(r.position,'') AS position,COALESCE(r.phone,'') AS phone,COALESCE(r.email,'') AS email FROM wh_warehouses w LEFT JOIN wh_responsibles r ON r.warehouse_id=w.id AND r.ended_at IS NULL WHERE ? != 'storekeeper' OR EXISTS(SELECT 1 FROM wh_access a WHERE a.warehouse_id=w.id AND a.user_id=?) ORDER BY w.code",
                        (actor.role.value, actor.user_id),
                    )
                ]
            }

    def save_warehouse(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        identifier = text(data, "id", 100, False) or str(uuid.uuid4())
        values = self.warehouse_values(data)
        try:
            with self.connection(True) as db:
                if (
                    not values[-1]
                    and db.execute(
                        "SELECT 1 FROM wh_items WHERE warehouse_id=? LIMIT 1", (identifier,)
                    ).fetchone()
                ):
                    raise WarehouseError("wh_has_stock", 409)
                db.execute(
                    "INSERT INTO wh_warehouses VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET code=excluded.code,name=excluded.name,address=excluded.address,note=excluded.note,active=excluded.active",
                    (identifier, *values),
                )
                self.audit(db, actor.user_id, "warehouse_saved", identifier)
        except sqlite3.IntegrityError as error:
            raise WarehouseError("wh_code_conflict", 409) from error
        return {"id": identifier}

    @staticmethod
    def responsible_values(data: dict[str, object]) -> tuple[str, str, str, str]:
        email = text(data, "email", 254, False)
        return (
            text(data, "name", 200),
            text(data, "position", 200, False),
            text(data, "phone", 50, False),
            email_address(email) if email else "",
        )

    def assign_responsible(
        self,
        db: sqlite3.Connection,
        actor: Principal,
        identifier: str,
        values: tuple[str, str, str, str],
        person_id: str = "",
    ) -> None:
        if not person_id:
            person = db.execute(
                "SELECT id FROM wh_people WHERE name=? AND position=? AND phone=? AND email=? AND active=1",
                values,
            ).fetchone()
            person_id = person[0] if person else str(uuid.uuid4())
            if not person:
                db.execute("INSERT INTO wh_people VALUES (?,?,?,?,?,1)", (person_id, *values))
        current = db.execute(
            "SELECT * FROM wh_responsibles WHERE warehouse_id=? AND ended_at IS NULL", (identifier,)
        ).fetchone()
        if (
            current
            and tuple(current[key] for key in ("name", "position", "phone", "email")) == values
            and current["person_id"] == person_id
        ):
            return
        stamp = now()
        db.execute(
            "UPDATE wh_responsibles SET ended_at=? WHERE warehouse_id=? AND ended_at IS NULL",
            (stamp, identifier),
        )
        db.execute(
            "INSERT INTO wh_responsibles(warehouse_id,name,position,phone,email,started_at,actor_id,person_id) VALUES (?,?,?,?,?,?,?,?)",
            (identifier, *values, stamp, actor.user_id, person_id),
        )
        self.audit(db, actor.user_id, "responsible_assigned", identifier)

    def save_responsible(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        identifier = text(data, "warehouse_id")
        person_id = text(data, "person_id", 100, False)
        with self.connection(True) as db:
            self.allowed(db, actor, identifier)
            if person_id:
                person = db.execute(
                    "SELECT * FROM wh_people WHERE id=? AND active=1", (person_id,)
                ).fetchone()
                if not person:
                    raise WarehouseError("wh_not_found", 404)
                values = self.responsible_values(dict(person))
            else:
                values = self.responsible_values(data)
            self.assign_responsible(db, actor, identifier, values, person_id)
        return {}

    def people(self, actor: Principal) -> dict[str, object]:
        with self.connection() as db:
            return {
                "rows": [
                    dict(row)
                    for row in db.execute(
                        "SELECT p.* FROM wh_people p WHERE ?!='storekeeper' OR EXISTS(SELECT 1 FROM wh_responsibles r JOIN wh_access a ON a.warehouse_id=r.warehouse_id WHERE r.person_id=p.id AND r.ended_at IS NULL AND a.user_id=?) ORDER BY p.name",
                        (actor.role.value, actor.user_id),
                    )
                ]
            }

    def save_person(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        identifier = text(data, "id", 100, False) or str(uuid.uuid4())
        values = self.responsible_values(data)
        active = data.get("active", True)
        if not isinstance(active, bool):
            raise WarehouseError("wh_input_invalid")
        with self.connection(True) as db:
            assigned = db.execute(
                "SELECT warehouse_id FROM wh_responsibles WHERE person_id=? AND ended_at IS NULL",
                (identifier,),
            ).fetchall()
            if assigned and not active:
                raise WarehouseError("wh_person_assigned", 409)
            db.execute(
                "INSERT INTO wh_people VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,position=excluded.position,phone=excluded.phone,email=excluded.email,active=excluded.active",
                (identifier, *values, int(active)),
            )
            for row in assigned:
                self.assign_responsible(db, actor, row["warehouse_id"], values, identifier)
            self.audit(db, actor.user_id, "responsible_saved", identifier)
        return {"id": identifier}

    def responsible_history(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        identifier = text(data, "warehouse_id")
        with self.connection() as db:
            self.allowed(db, actor, identifier)
            return {
                "rows": [
                    dict(row)
                    for row in db.execute(
                        "SELECT r.*,u.email AS actor FROM wh_responsibles r JOIN wh_users u ON u.id=r.actor_id WHERE warehouse_id=? ORDER BY r.id DESC",
                        (identifier,),
                    )
                ]
            }

    def models(self) -> dict[str, object]:
        with self.connection() as db:
            return {
                "rows": [dict(row) for row in db.execute("SELECT * FROM wh_models ORDER BY name")]
            }

    def save_model(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        name = text(data, "name", 200)
        device_type, service = text(data, "device_type"), text(data, "service")
        if device_type not in ("modem", "tuner") or service not in ("internet", "television"):
            raise WarehouseError("wh_input_invalid")
        identifier = str(uuid.uuid4())
        with self.connection(True) as db:
            db.execute(
                "INSERT INTO wh_models VALUES (?,?,?,?)", (identifier, name, device_type, service)
            )
            self.audit(db, actor.user_id, "model_created", identifier)
        return {"id": identifier}

    @staticmethod
    def responsible_name(db: sqlite3.Connection, identifier: str | None) -> str:
        row = db.execute(
            "SELECT name FROM wh_responsibles WHERE warehouse_id=? AND ended_at IS NULL",
            (identifier,),
        ).fetchone()
        return row[0] if row else ""

    def move(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        kind, serial = text(data, "kind"), text(data, "serial", 200).upper()
        source = text(data, "source_id", 100, False) or None
        destination = text(data, "destination_id", 100, False) or None
        model_id, request_id, note = (
            text(data, "model_id"),
            text(data, "request_id", 100),
            text(data, "note", 1000, False),
        )
        if (
            kind not in ("receipt", "issue", "transfer")
            or (kind == "receipt" and (source is not None or destination is None))
            or (kind == "issue" and (source is None or destination is not None))
            or (
                kind == "transfer"
                and (source is None or destination is None or source == destination)
            )
        ):
            raise WarehouseError("wh_movement_invalid")
        fingerprint = hashlib.sha256(
            json.dumps(
                [kind, serial, source, destination, model_id, note], ensure_ascii=True
            ).encode()
        ).hexdigest()
        with self.connection(True) as db:
            for identifier in (source, destination):
                if identifier is not None:
                    self.allowed(db, actor, identifier, active=True)
            previous = db.execute(
                "SELECT id,request_hash FROM wh_movements WHERE actor_id=? AND request_id=?",
                (actor.user_id, request_id),
            ).fetchone()
            if previous:
                if previous["request_hash"] != fingerprint:
                    raise WarehouseError("wh_request_conflict", 409)
                return {"id": previous["id"]}
            item = db.execute("SELECT * FROM wh_items WHERE serial=?", (serial,)).fetchone()
            if not db.execute("SELECT 1 FROM wh_models WHERE id=?", (model_id,)).fetchone():
                raise WarehouseError("wh_not_found", 404)
            if item and item["model_id"] != model_id:
                raise WarehouseError("wh_serial_model", 409)
            if kind == "receipt":
                if item and item["warehouse_id"] is not None:
                    raise WarehouseError("wh_already_in_stock", 409)
                if not item:
                    db.execute("INSERT INTO wh_items VALUES (?,?,NULL)", (serial, model_id))
            elif not item or item["warehouse_id"] != source:
                raise WarehouseError("wh_no_stock", 409)
            identifier = str(uuid.uuid4())
            db.execute("UPDATE wh_items SET warehouse_id=? WHERE serial=?", (destination, serial))
            db.execute(
                "INSERT INTO wh_movements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    request_id,
                    fingerprint,
                    serial,
                    model_id,
                    kind,
                    source,
                    destination,
                    self.responsible_name(db, source),
                    self.responsible_name(db, destination),
                    actor.user_id,
                    now(),
                    note,
                ),
            )
            self.audit(db, actor.user_id, kind, identifier)
            return {"id": identifier}

    def balances(
        self, actor: Principal, data: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = data or {}
        warehouse = text(data, "warehouse_id", 100, False)
        model, serial, responsible = (
            text(data, "model_id", 100, False),
            text(data, "serial", 200, False),
            text(data, "responsible", 200, False),
        )
        with self.connection() as db:
            if warehouse:
                self.allowed(db, actor, warehouse)
            return {
                "rows": [
                    dict(row)
                    for row in db.execute(
                        "SELECT w.id AS warehouse_id,w.code,w.name AS warehouse,m.name AS model,COALESCE(r.name,'') AS responsible,COUNT(*) AS quantity FROM wh_items i JOIN wh_warehouses w ON w.id=i.warehouse_id JOIN wh_models m ON m.id=i.model_id LEFT JOIN wh_responsibles r ON r.warehouse_id=w.id AND r.ended_at IS NULL WHERE (?!='storekeeper' OR EXISTS(SELECT 1 FROM wh_access a WHERE a.user_id=? AND a.warehouse_id=w.id)) AND (?='' OR w.id=?) AND (?='' OR m.id=?) AND (?='' OR i.serial=?) AND (?='' OR casefold(r.name) LIKE ?) GROUP BY w.id,m.id,r.id ORDER BY w.code,m.name",
                        (
                            actor.role.value,
                            actor.user_id,
                            warehouse,
                            warehouse,
                            model,
                            model,
                            serial,
                            serial.upper(),
                            responsible,
                            "%" + responsible.casefold() + "%",
                        ),
                    )
                ]
            }

    def movements(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        page = data.get("page", 1)
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise WarehouseError("wh_input_invalid")
        warehouse_id = text(data, "warehouse_id", 100, False)
        serial = text(data, "serial", 200, False)
        model, responsible = (
            text(data, "model_id", 100, False),
            text(data, "responsible", 200, False),
        )
        with self.connection() as db:
            if warehouse_id:
                self.allowed(db, actor, warehouse_id)
            where = "WHERE (?!='storekeeper' OR EXISTS(SELECT 1 FROM wh_access a WHERE a.user_id=? AND a.warehouse_id IN (e.source_id,e.destination_id))) AND (?='' OR ? IN (e.source_id,e.destination_id)) AND (?='' OR e.serial=?)"
            params = (
                actor.role.value,
                actor.user_id,
                warehouse_id,
                warehouse_id,
                serial,
                serial.upper(),
                model,
                model,
                responsible,
                "%" + responsible.casefold() + "%",
                "%" + responsible.casefold() + "%",
            )
            where += " AND (?='' OR e.model_id=?) AND (?='' OR casefold(e.source_responsible) LIKE ? OR casefold(e.destination_responsible) LIKE ?)"
            total = db.execute("SELECT COUNT(*) FROM wh_movements e " + where, params).fetchone()[0]
            rows = db.execute(
                "SELECT e.*,m.name AS model,COALESCE(s.code,'') AS source,COALESCE(d.code,'') AS destination,u.email AS actor FROM wh_movements e JOIN wh_models m ON m.id=e.model_id LEFT JOIN wh_warehouses s ON s.id=e.source_id LEFT JOIN wh_warehouses d ON d.id=e.destination_id JOIN wh_users u ON u.id=e.actor_id "
                + where
                + " ORDER BY e.registered_at DESC,e.id DESC LIMIT 100 OFFSET ?",
                (*params, (page - 1) * 100),
            ).fetchall()
            return {
                "rows": [dict(row) for row in rows],
                "total": total,
                "page": page,
                "pages": max(1, (total + 99) // 100),
            }

    def import_warehouses(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        raw = data.get("rows")
        if not isinstance(raw, list) or not 1 <= len(raw) <= 10000:
            raise WarehouseError("wh_import_invalid")
        prepared = []
        codes = set()
        for entry in raw:
            if not isinstance(entry, dict) or any(not isinstance(key, str) for key in entry):
                raise WarehouseError("wh_import_invalid")
            row: dict[str, object] = dict(entry)
            values = self.warehouse_values(row)
            if values[0] in codes:
                raise WarehouseError("wh_import_invalid")
            codes.add(values[0])
            person = None
            if row.get("responsible_name"):
                person = self.responsible_values({**row, "name": row["responsible_name"]})
            prepared.append((values, person))
        added, skipped = 0, 0
        with self.connection(True) as db:
            for values, person in prepared:
                existing = db.execute(
                    "SELECT id FROM wh_warehouses WHERE code=?", (values[0],)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue
                identifier = str(uuid.uuid4())
                db.execute("INSERT INTO wh_warehouses VALUES (?,?,?,?,?,?)", (identifier, *values))
                if person:
                    self.assign_responsible(db, actor, identifier, person)
                self.audit(db, actor.user_id, "warehouse_imported", identifier)
                added += 1
        return {"added": added, "skipped": skipped}

    def translations(self) -> dict[str, object]:
        with self.connection() as db:
            return {
                "rows": [
                    dict(row)
                    for row in db.execute("SELECT * FROM wh_translations ORDER BY locale,key")
                ]
            }

    def save_translation(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        locale, key = text(data, "locale"), text(data, "key")
        value = text(data, "value", 4096)
        if locale not in SUPPORTED_LOCALES or key not in TEXT[locale]:
            raise WarehouseError("wh_translation_invalid")
        try:
            expected = sorted(
                field
                for _, field, _, _ in Formatter().parse(TEXT[locale][key])
                if field is not None
            )
            actual = sorted(
                field for _, field, _, _ in Formatter().parse(value) if field is not None
            )
            if actual != expected or any(
                spec or conversion for _, _, spec, conversion in Formatter().parse(value)
            ):
                raise ValueError()
        except ValueError as error:
            raise WarehouseError("wh_translation_invalid") from error
        with self.connection(True) as db:
            db.execute(
                "INSERT INTO wh_translations VALUES (?,?,?) ON CONFLICT(locale,key) DO UPDATE SET value=excluded.value",
                (locale, key, value),
            )
            self.audit(db, actor.user_id, "translation_saved", locale + ":" + key)
        return {}

    def audits(self) -> dict[str, object]:
        with self.connection() as db:
            return {
                "rows": [
                    dict(row)
                    for row in db.execute(
                        "SELECT a.*,u.email AS actor FROM wh_audit a LEFT JOIN wh_users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 500"
                    )
                ]
            }
