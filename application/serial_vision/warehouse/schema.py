SCHEMA = """
CREATE TABLE IF NOT EXISTS wh_users (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','manager','storekeeper')),
 active INTEGER NOT NULL DEFAULT 1, must_change INTEGER NOT NULL DEFAULT 0,
 temporary_expires REAL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wh_tokens (
 hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES wh_users(id), kind TEXT NOT NULL,
 scope TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', expires REAL NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wh_login_attempts (email TEXT PRIMARY KEY, failures INTEGER NOT NULL, blocked_until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS wh_warehouses (
 id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
 address TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS wh_access (
 user_id TEXT NOT NULL REFERENCES wh_users(id), warehouse_id TEXT NOT NULL REFERENCES wh_warehouses(id),
 PRIMARY KEY(user_id,warehouse_id)
);
CREATE TABLE IF NOT EXISTS wh_people (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, position TEXT NOT NULL, phone TEXT NOT NULL,
 email TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS wh_responsibles (
 id INTEGER PRIMARY KEY, warehouse_id TEXT NOT NULL REFERENCES wh_warehouses(id),
 name TEXT NOT NULL, position TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL,
 started_at TEXT NOT NULL, ended_at TEXT, actor_id TEXT NOT NULL REFERENCES wh_users(id),
 person_id TEXT REFERENCES wh_people(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS wh_one_responsible ON wh_responsibles(warehouse_id) WHERE ended_at IS NULL;
CREATE TABLE IF NOT EXISTS wh_models (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, device_type TEXT NOT NULL, service TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wh_items (
 serial TEXT PRIMARY KEY COLLATE NOCASE, model_id TEXT NOT NULL REFERENCES wh_models(id),
 warehouse_id TEXT REFERENCES wh_warehouses(id)
);
CREATE TABLE IF NOT EXISTS wh_movements (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 serial TEXT NOT NULL REFERENCES wh_items(serial), model_id TEXT NOT NULL REFERENCES wh_models(id),
 kind TEXT NOT NULL CHECK(kind IN ('receipt','issue','transfer')),
 source_id TEXT REFERENCES wh_warehouses(id), destination_id TEXT REFERENCES wh_warehouses(id),
 source_responsible TEXT NOT NULL, destination_responsible TEXT NOT NULL,
 actor_id TEXT NOT NULL REFERENCES wh_users(id), registered_at TEXT NOT NULL, note TEXT NOT NULL,
 UNIQUE(actor_id,request_id), CHECK(source_id IS NOT destination_id)
);
CREATE INDEX IF NOT EXISTS wh_movements_time ON wh_movements(registered_at);
CREATE TABLE IF NOT EXISTS wh_translations (
 locale TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(locale,key)
);
CREATE TABLE IF NOT EXISTS wh_audit (
 id INTEGER PRIMARY KEY, actor_id TEXT REFERENCES wh_users(id), action TEXT NOT NULL,
 entity_id TEXT NOT NULL, registered_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""
