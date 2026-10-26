from __future__ import annotations

import secrets
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from serial_vision.database import DEFAULT_MODELS
from serial_vision.warehouse.schema import SCHEMA
from serial_vision.warehouse.security import (
    PASSWORDS,
    Principal,
    Role,
    WarehouseError,
    email_address,
    password_matches,
    temporary_password,
    text,
    token_digest,
    validate_password,
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def public_user(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "active": bool(row["active"]),
        "must_change": bool(row["must_change"]),
    }


class Repository:
    """Dedicated warehouse database. Never migrates the existing equipment database."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise WarehouseError("wh_schema_newer", 503)
            if version == 0:
                db.executescript(SCHEMA)
            db.execute("PRAGMA journal_mode = WAL")
            db.executemany(
                "INSERT OR IGNORE INTO wh_models VALUES (?,?, 'modem','internet')",
                [(str(uuid.uuid5(uuid.NAMESPACE_URL, name)), name) for name in DEFAULT_MODELS],
            )
        self._dummy_hash = PASSWORDS.hash(secrets.token_urlsafe(32))

    @contextmanager
    def connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 15000")
        db.create_function(
            "casefold", 1, lambda value: str(value or "").casefold(), deterministic=True
        )
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def audit(db: sqlite3.Connection, actor: str, action: str, entity: str) -> None:
        db.execute(
            "INSERT INTO wh_audit(actor_id,action,entity_id,registered_at) VALUES (?,?,?,?)",
            (actor, action, entity, now()),
        )

    def initialized(self) -> bool:
        with self.connection() as db:
            return db.execute("SELECT EXISTS(SELECT 1 FROM wh_users)").fetchone()[0] == 1

    def bootstrap(self, data: dict[str, object]) -> dict[str, object]:
        email = email_address(data.get("email"))
        name = text(data, "name", 200, False) or email
        encoded = PASSWORDS.hash(validate_password(data.get("password")))
        with self.connection(True) as db:
            if db.execute("SELECT 1 FROM wh_users LIMIT 1").fetchone():
                raise WarehouseError("wh_already_initialized", 409)
            identifier = str(uuid.uuid4())
            db.execute(
                "INSERT INTO wh_users(id,email,name,password_hash,role,created_at) VALUES (?,?,?,?, 'admin',?)",
                (identifier, email, name, encoded, now()),
            )
            self.audit(db, identifier, "bootstrap", identifier)
            return self.session(db, identifier)

    @staticmethod
    def session(db: sqlite3.Connection, user_id: str) -> dict[str, object]:
        row = db.execute("SELECT * FROM wh_users WHERE id=?", (user_id,)).fetchone()
        token = "svs_" + secrets.token_urlsafe(32)
        db.execute("DELETE FROM wh_tokens WHERE expires < ?", (time.time(),))
        db.execute(
            "INSERT INTO wh_tokens VALUES (?,?, 'session','admin','',?,?)",
            (
                token_digest(token),
                user_id,
                time.time() + (900 if row["must_change"] else 8 * 3600),
                now(),
            ),
        )
        return {"token": token, "user": public_user(row)}

    def login(self, data: dict[str, object]) -> dict[str, object]:
        email = email_address(data.get("email"))
        with self.connection() as db:
            attempt = db.execute(
                "SELECT * FROM wh_login_attempts WHERE email=?", (email,)
            ).fetchone()
            row = db.execute("SELECT * FROM wh_users WHERE email=?", (email,)).fetchone()
        if attempt and attempt["blocked_until"] > time.time():
            raise WarehouseError("wh_login_limited", 429)
        valid = password_matches(
            row["password_hash"] if row else self._dummy_hash, data.get("password")
        )
        if (
            not valid
            or not row
            or not row["active"]
            or (row["must_change"] and row["temporary_expires"] < time.time())
        ):
            with self.connection(True) as db:
                db.execute(
                    "INSERT INTO wh_login_attempts VALUES (?,1,0) ON CONFLICT(email) DO UPDATE SET failures = CASE WHEN blocked_until < ? AND blocked_until > 0 THEN 1 ELSE failures+1 END, blocked_until=0",
                    (email, time.time()),
                )
                db.execute(
                    "UPDATE wh_login_attempts SET blocked_until=? WHERE email=? AND failures>=5",
                    (time.time() + 900, email),
                )
            raise WarehouseError("wh_login_invalid", 401)
        with self.connection(True) as db:
            current = db.execute("SELECT * FROM wh_users WHERE id=?", (row["id"],)).fetchone()
            if not current["active"] or current["password_hash"] != row["password_hash"]:
                raise WarehouseError("wh_login_invalid", 401)
            if PASSWORDS.check_needs_rehash(current["password_hash"]):
                db.execute(
                    "UPDATE wh_users SET password_hash=? WHERE id=?",
                    (PASSWORDS.hash(str(data["password"])), row["id"]),
                )
            db.execute("DELETE FROM wh_login_attempts WHERE email=?", (email,))
            self.audit(db, row["id"], "login", row["id"])
            return self.session(db, row["id"])

    def authorize(self, token: str) -> Principal:
        with self.connection() as db:
            row = db.execute(
                "SELECT u.*, t.hash,t.kind,t.scope FROM wh_tokens t JOIN wh_users u ON u.id=t.user_id WHERE t.hash=? AND t.expires>? AND u.active=1",
                (token_digest(token), time.time()),
            ).fetchone()
        if not row:
            raise WarehouseError("wh_login_required", 401)
        return Principal(
            row["id"],
            row["email"],
            Role(row["role"]),
            bool(row["must_change"]),
            row["hash"],
            row["kind"],
            row["scope"],
        )

    def me(self, actor: Principal) -> dict[str, object]:
        with self.connection() as db:
            row = db.execute("SELECT * FROM wh_users WHERE id=?", (actor.user_id,)).fetchone()
            return {"user": public_user(row)}

    def logout(self, actor: Principal) -> dict[str, object]:
        with self.connection(True) as db:
            db.execute("DELETE FROM wh_tokens WHERE hash=?", (actor.token_hash,))
        return {}

    def change_password(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        password = validate_password(data.get("password"))
        with self.connection() as db:
            previous = db.execute(
                "SELECT password_hash FROM wh_users WHERE id=?", (actor.user_id,)
            ).fetchone()[0]
        if not password_matches(previous, data.get("old_password")):
            raise WarehouseError("wh_login_invalid", 401)
        if password_matches(previous, password):
            raise WarehouseError("wh_password_reused")
        encoded = PASSWORDS.hash(password)
        with self.connection(True) as db:
            changed = db.execute(
                "UPDATE wh_users SET password_hash=?, must_change=0,temporary_expires=NULL WHERE id=? AND password_hash=? AND active=1",
                (encoded, actor.user_id, previous),
            ).rowcount
            if changed != 1:
                raise WarehouseError("wh_login_required", 401)
            db.execute("DELETE FROM wh_tokens WHERE user_id=?", (actor.user_id,))
            self.audit(db, actor.user_id, "password_changed", actor.user_id)
            return self.session(db, actor.user_id)

    def users(self) -> dict[str, object]:
        with self.connection() as db:
            rows = []
            for row in db.execute("SELECT * FROM wh_users ORDER BY email"):
                user = public_user(row)
                user["warehouse_ids"] = [
                    value[0]
                    for value in db.execute(
                        "SELECT warehouse_id FROM wh_access WHERE user_id=?", (row["id"],)
                    )
                ]
                rows.append(user)
            return {"rows": rows}

    @staticmethod
    def access_ids(data: dict[str, object]) -> list[str]:
        ids = data.get("warehouse_ids", [])
        if (
            not isinstance(ids, list)
            or len(ids) > 1000
            or any(not isinstance(value, str) for value in ids)
        ):
            raise WarehouseError("wh_input_invalid")
        return list(dict.fromkeys(str(value) for value in ids))

    def create_user(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        email = email_address(data.get("email"))
        name = text(data, "name", 200, False) or email
        try:
            role = Role(text(data, "role"))
        except ValueError as error:
            raise WarehouseError("wh_input_invalid") from error
        password = validate_password(data.get("temporary_password") or temporary_password())
        encoded, identifier = PASSWORDS.hash(password), str(uuid.uuid4())
        ids = self.access_ids(data)
        try:
            with self.connection(True) as db:
                db.execute(
                    "INSERT INTO wh_users(id,email,name,password_hash,role,must_change,temporary_expires,created_at) VALUES (?,?,?,?,?,1,?,?)",
                    (identifier, email, name, encoded, role.value, time.time() + 86400, now()),
                )
                db.executemany(
                    "INSERT INTO wh_access VALUES (?,?)", [(identifier, value) for value in ids]
                )
                self.audit(db, actor.user_id, "user_created", identifier)
        except sqlite3.IntegrityError as error:
            raise WarehouseError("wh_user_conflict", 409) from error
        return {"id": identifier, "temporary_password": password}

    def update_user(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        identifier = text(data, "id")
        try:
            role = Role(text(data, "role"))
        except ValueError as error:
            raise WarehouseError("wh_input_invalid") from error
        active = data.get("active", True)
        if not isinstance(active, bool):
            raise WarehouseError("wh_input_invalid")
        ids = self.access_ids(data)
        with self.connection(True) as db:
            previous = db.execute("SELECT * FROM wh_users WHERE id=?", (identifier,)).fetchone()
            if not previous:
                raise WarehouseError("wh_not_found", 404)
            if (
                previous["role"] == "admin"
                and previous["active"]
                and not previous["must_change"]
                and (role != Role.ADMIN or not active)
            ):
                if (
                    db.execute(
                        "SELECT COUNT(*) FROM wh_users WHERE role='admin' AND active=1 AND must_change=0"
                    ).fetchone()[0]
                    <= 1
                ):
                    raise WarehouseError("wh_last_admin", 409)
            db.execute(
                "UPDATE wh_users SET role=?,active=? WHERE id=?",
                (role.value, int(active), identifier),
            )
            db.execute("DELETE FROM wh_access WHERE user_id=?", (identifier,))
            db.executemany(
                "INSERT INTO wh_access VALUES (?,?)", [(identifier, value) for value in ids]
            )
            if not active:
                db.execute("DELETE FROM wh_tokens WHERE user_id=?", (identifier,))
            self.audit(db, actor.user_id, "user_updated", identifier)
        return {}

    def reset_password(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        identifier = text(data, "id")
        if identifier == actor.user_id:
            raise WarehouseError("wh_use_password_change")
        password = temporary_password()
        encoded = PASSWORDS.hash(password)
        with self.connection(True) as db:
            changed = db.execute(
                "UPDATE wh_users SET password_hash=?,must_change=1,temporary_expires=? WHERE id=?",
                (encoded, time.time() + 86400, identifier),
            ).rowcount
            if not changed:
                raise WarehouseError("wh_not_found", 404)
            db.execute("DELETE FROM wh_tokens WHERE user_id=?", (identifier,))
            self.audit(db, actor.user_id, "password_reset", identifier)
        return {"temporary_password": password}

    def issue_token(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        scope = text(data, "scope")
        if scope not in ("warehouse", "admin"):
            raise WarehouseError("wh_input_invalid")
        token = "svw_" + secrets.token_urlsafe(32)
        with self.connection(True) as db:
            db.execute(
                "INSERT INTO wh_tokens VALUES (?,?, 'api',?,?,?,?)",
                (
                    token_digest(token),
                    actor.user_id,
                    scope,
                    text(data, "name", 100),
                    time.time() + 90 * 86400,
                    now(),
                ),
            )
            self.audit(db, actor.user_id, "token_issued", token_digest(token)[:12])
        return {"token": token}

    def tokens(self) -> dict[str, object]:
        with self.connection() as db:
            return {
                "rows": [
                    dict(row)
                    for row in db.execute(
                        "SELECT hash,name,scope,expires,created_at FROM wh_tokens WHERE kind='api' ORDER BY created_at DESC"
                    )
                ]
            }

    def revoke_token(self, actor: Principal, data: dict[str, object]) -> dict[str, object]:
        with self.connection(True) as db:
            identifier = text(data, "hash")
            db.execute("DELETE FROM wh_tokens WHERE hash=? AND kind='api'", (identifier,))
            self.audit(db, actor.user_id, "token_revoked", identifier[:12])
        return {}
