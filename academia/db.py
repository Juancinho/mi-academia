"""SQLite, esquema versionado, transacciones y copias consistentes."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 id INTEGER PRIMARY KEY, external_id TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 occurred_at TEXT NOT NULL, summary TEXT NOT NULL, original_text TEXT NOT NULL,
 payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL, imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources(
 id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id),
 external_id TEXT NOT NULL, title TEXT NOT NULL, kind TEXT NOT NULL,
 url TEXT, citation TEXT NOT NULL, UNIQUE(session_id,external_id)
);
CREATE TABLE IF NOT EXISTS knowledge(
 id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 content TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('concepto','hecho','procedimiento','relacion','competencia')),
 epistemic TEXT NOT NULL CHECK(epistemic IN ('verificable','interpretacion','opinion','cambiante')),
 as_of TEXT, recheck_on TEXT, created_at TEXT NOT NULL,
 CHECK(epistemic != 'cambiante' OR as_of IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS session_knowledge(
 session_id INTEGER NOT NULL REFERENCES sessions(id), external_id TEXT NOT NULL,
 knowledge_id INTEGER NOT NULL REFERENCES knowledge(id), PRIMARY KEY(session_id,external_id)
);
CREATE TABLE IF NOT EXISTS evidence(
 id INTEGER PRIMARY KEY, knowledge_id INTEGER NOT NULL REFERENCES knowledge(id),
 source_id INTEGER NOT NULL REFERENCES sources(id), locator TEXT NOT NULL, excerpt TEXT NOT NULL,
 UNIQUE(knowledge_id,source_id,locator,excerpt)
);
CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY, name TEXT NOT NULL, normalized TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS knowledge_topics(
 knowledge_id INTEGER NOT NULL REFERENCES knowledge(id), topic_id INTEGER NOT NULL REFERENCES topics(id),
 PRIMARY KEY(knowledge_id,topic_id)
);
CREATE TABLE IF NOT EXISTS relations(
 id INTEGER PRIMARY KEY, from_id INTEGER NOT NULL REFERENCES knowledge(id),
 to_id INTEGER NOT NULL REFERENCES knowledge(id), label TEXT NOT NULL, explanation TEXT NOT NULL,
 session_id INTEGER REFERENCES sessions(id), CHECK(from_id != to_id),
 UNIQUE(from_id,to_id,label,explanation)
);
CREATE TABLE IF NOT EXISTS tasks(
 id INTEGER PRIMARY KEY, knowledge_id INTEGER NOT NULL REFERENCES knowledge(id),
 fingerprint TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode IN ('recuperacion','explicacion','razonamiento','comparacion','analisis','demostracion','practica')),
 prompt TEXT NOT NULL, expected_answer TEXT NOT NULL, rubric_json TEXT NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(knowledge_id,fingerprint)
);
CREATE TABLE IF NOT EXISTS cards(
 task_id INTEGER PRIMARY KEY REFERENCES tasks(id), card_json TEXT NOT NULL,
 due TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS task_sessions(
 task_id INTEGER NOT NULL REFERENCES tasks(id), session_id INTEGER NOT NULL REFERENCES sessions(id),
 PRIMARY KEY(task_id,session_id)
);
CREATE TABLE IF NOT EXISTS exposures(
 id INTEGER PRIMARY KEY, knowledge_id INTEGER NOT NULL REFERENCES knowledge(id),
 level TEXT NOT NULL CHECK(level IN ('registrado','leido','comprendido')), note TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews(
 id INTEGER PRIMARY KEY, token TEXT NOT NULL UNIQUE,
 task_id INTEGER NOT NULL REFERENCES tasks(id), answer TEXT NOT NULL CHECK(length(trim(answer)) > 0),
 score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 4), assisted INTEGER NOT NULL CHECK(assisted IN (0,1)),
 rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 4), feedback TEXT NOT NULL, errors TEXT NOT NULL,
 reviewed_at TEXT NOT NULL, duration_ms INTEGER CHECK(duration_ms >= 0),
 card_before TEXT NOT NULL, card_after TEXT NOT NULL, log_json TEXT NOT NULL, scheduler_json TEXT NOT NULL,
 evaluator TEXT NOT NULL DEFAULT 'self' CHECK(evaluator IN ('self','human','ai')),
 CHECK(assisted = 0 OR score <= 2)
);
CREATE INDEX IF NOT EXISTS idx_due ON cards(due);
CREATE INDEX IF NOT EXISTS idx_reviews_task_time ON reviews(task_id,reviewed_at);
CREATE INDEX IF NOT EXISTS idx_evidence_knowledge ON evidence(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_exposures_knowledge ON exposures(knowledge_id);
"""


def default_path() -> Path:
    return Path(os.environ.get("ACADEMIA_DB", str(ROOT / "data" / "academia.sqlite3")))


@contextmanager
def connection(path: str | Path | None = None, *, write=False):
    path = Path(path) if path is not None else default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        if write:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize(path=None):
    with connection(path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError("Esta base de datos requiere una versión más reciente de Mi Academia.")
        if version == 0:
            # El esquema y su versión se confirman de forma atómica.
            conn.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + f"\nPRAGMA user_version={SCHEMA_VERSION};\nCOMMIT;")
        conn.execute("PRAGMA journal_mode=WAL")


def backup_bytes(path=None) -> bytes:
    # backup() incluye el WAL y produce una instantánea coherente con la app abierta.
    handle, target = tempfile.mkstemp(suffix=".sqlite3")
    os.close(handle)
    try:
        with connection(path) as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
            destination.execute("PRAGMA journal_mode=DELETE")
        return Path(target).read_bytes()
    finally:
        Path(target).unlink(missing_ok=True)


def restore_backup(source_path: Path, target_path: Path):
    source_path, target_path = source_path.resolve(), target_path.resolve()
    if target_path.exists():
        raise ValueError("El destino ya existe. Restaura a un archivo nuevo para conservar tus datos.")
    uri = source_path.as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as source:
        if source.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise ValueError("Versión de copia no compatible.")
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("La copia está dañada.")
        if source.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("La copia tiene referencias inválidas.")
        with closing(sqlite3.connect(":memory:")) as expected:
            expected.executescript(SCHEMA)
            tables = [r[0] for r in expected.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                expected_columns = [tuple(r) for r in expected.execute(f"PRAGMA table_info({table})")]
                actual_columns = [tuple(r) for r in source.execute(f"PRAGMA table_info({table})")]
                if expected_columns != actual_columns:
                    raise ValueError("La copia no tiene el esquema completo de Mi Academia.")
        from fsrs import Card, Scheduler, ReviewLog
        for row in source.execute("SELECT card_json FROM cards"):
            Card.from_json(row[0])
        settings = dict(source.execute("SELECT key,value FROM settings").fetchall())
        if "scheduler" not in settings or "timezone" not in settings:
            raise ValueError("La copia no contiene la configuración del planificador.")
        Scheduler.from_json(settings["scheduler"])
        from zoneinfo import ZoneInfo
        ZoneInfo(settings["timezone"])
        for row in source.execute("SELECT card_before,card_after,log_json,scheduler_json FROM reviews"):
            Card.from_json(row[0])
            Card.from_json(row[1])
            ReviewLog.from_json(row[2])
            Scheduler.from_json(row[3])
        target_path.parent.mkdir(parents=True, exist_ok=True)
        # Reserva exclusiva: nunca sobrescribir una BD creada mientras se comprobaba la copia.
        with target_path.open("xb"):
            pass
        try:
            with closing(sqlite3.connect(target_path)) as destination:
                source.backup(destination)
        except BaseException:
            target_path.unlink(missing_ok=True)
            raise


def full_export(path=None) -> str:
    tables = ["settings", "sessions", "sources", "knowledge", "session_knowledge", "evidence",
              "topics", "knowledge_topics", "relations", "tasks", "cards", "task_sessions", "exposures", "reviews"]
    with connection(path) as conn:
        conn.execute("BEGIN")
        data = {table: [dict(row) for row in conn.execute(f"SELECT * FROM {table}")] for table in tables}
    return json.dumps({"format": "mi-academia-export", "schema_version": SCHEMA_VERSION, "tables": data},
                      ensure_ascii=False, indent=2)
