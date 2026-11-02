"""Casos de uso: importación atómica, evidencias y evaluación FSRS."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from importlib.metadata import version as package_version
from zoneinfo import ZoneInfo

from fsrs import Card, Rating, Scheduler

from .db import connection, initialize
from .models import ImportBundle, Task, canonical, digest, knowledge_fingerprint, normalized, task_fingerprint

UTC = timezone.utc
STAGES = ["Registrado", "Leído", "Comprendido (declarado)", "En práctica", "Dominio demostrado"]
MODE_LABELS = {"recuperacion": "Recuperación factual", "explicacion": "Explicación abierta",
               "razonamiento": "Razonamiento", "comparacion": "Comparación", "analisis": "Análisis crítico",
               "demostracion": "Demostración", "practica": "Ejercicio práctico"}
EPI_LABELS = {"verificable": "Hecho o conocimiento verificable", "interpretacion": "Interpretación",
              "opinion": "Opinión", "cambiante": "Sujeto a cambios"}


def now_utc():
    return datetime.now(UTC)


def utc(value: datetime | None = None) -> datetime:
    value = value or now_utc()
    if value.tzinfo is None:
        raise ValueError("La fecha necesita zona horaria.")
    return value.astimezone(UTC)


def stamp(value=None):
    return utc(value).isoformat()


class Academy:
    def __init__(self, path=None):
        self.path = path
        initialize(path)
        with connection(path, write=True) as conn:
            conn.execute("INSERT OR IGNORE INTO settings VALUES('scheduler', ?)",
                         (Scheduler(desired_retention=0.9, enable_fuzzing=False).to_json(),))
            conn.execute("INSERT OR IGNORE INTO settings VALUES('timezone','Europe/Madrid')")
            conn.execute("INSERT OR IGNORE INTO settings VALUES('fsrs_version',?)", (package_version("fsrs"),))

    def settings(self):
        with connection(self.path) as conn:
            return dict(conn.execute("SELECT key,value FROM settings").fetchall())

    def set_timezone(self, name):
        ZoneInfo(name)  # Validar antes de guardar.
        with connection(self.path, write=True) as conn:
            conn.execute("UPDATE settings SET value=? WHERE key='timezone'", (name,))

    def preview_import(self, bundle: ImportBundle):
        result = {"sessions": 0, "skipped": 0, "knowledge": 0, "reused": 0, "tasks": 0}
        with connection(self.path) as conn:
            known = {r[0] for r in conn.execute("SELECT fingerprint FROM knowledge")}
            tasks = {(r[0], r[1]) for r in conn.execute(
                "SELECT k.fingerprint,t.fingerprint FROM tasks t JOIN knowledge k ON k.id=t.knowledge_id")}
            for session in bundle.sessions:
                payload = session.model_dump(mode="json")
                existing = conn.execute("SELECT payload_hash FROM sessions WHERE external_id=?", (session.external_id,)).fetchone()
                if existing:
                    if existing[0] != digest(payload):
                        raise ValueError(f"La sesión '{session.external_id}' ya existe con otro contenido. Usa un nuevo external_id para una ampliación.")
                    result["skipped"] += 1
                    continue
                result["sessions"] += 1
                for item in session.knowledge:
                    fp = knowledge_fingerprint(item)
                    key = "reused" if fp in known else "knowledge"
                    result[key] += 1
                    known.add(fp)
                    for task in item.tasks:
                        pair = (fp, task_fingerprint(task))
                        if pair not in tasks:
                            result["tasks"] += 1
                            tasks.add(pair)
        return result

    def import_bundle(self, bundle: ImportBundle, at=None):
        timestamp = stamp(at)
        # Revalidar dentro de la transacción: no depender de una previsualización antigua.
        result = {"sessions": 0, "skipped": 0, "knowledge": 0, "reused": 0, "tasks": 0}
        with connection(self.path, write=True) as conn:
            for session in bundle.sessions:
                payload = session.model_dump(mode="json")
                existing = conn.execute("SELECT payload_hash FROM sessions WHERE external_id=?", (session.external_id,)).fetchone()
                if existing:
                    if existing[0] != digest(payload):
                        raise ValueError(f"Conflicto en '{session.external_id}'. Importación cancelada; usa un nuevo external_id.")
                    result["skipped"] += 1
                    continue
                sid = conn.execute("""INSERT INTO sessions(external_id,title,occurred_at,summary,original_text,payload_hash,payload_json,imported_at)
                    VALUES(?,?,?,?,?,?,?,?)""", (session.external_id, session.title, stamp(session.occurred_at), session.summary,
                    session.original_text, digest(payload), canonical(payload), timestamp)).lastrowid
                result["sessions"] += 1
                sources = {}
                for source in session.sources:
                    sources[source.id] = conn.execute("""INSERT INTO sources(session_id,external_id,title,kind,url,citation)
                        VALUES(?,?,?,?,?,?)""", (sid, source.id, source.title, source.kind, source.url, source.citation)).lastrowid
                ids = {}
                for item in session.knowledge:
                    fp = knowledge_fingerprint(item)
                    found = conn.execute("SELECT id FROM knowledge WHERE fingerprint=?", (fp,)).fetchone()
                    if found:
                        kid = found[0]
                        result["reused"] += 1
                    else:
                        kid = conn.execute("""INSERT INTO knowledge(fingerprint,title,content,kind,epistemic,as_of,recheck_on,created_at)
                            VALUES(?,?,?,?,?,?,?,?)""", (fp, item.title, item.content, item.kind, item.epistemic,
                            str(item.as_of) if item.as_of else None, str(item.recheck_on) if item.recheck_on else None, timestamp)).lastrowid
                        conn.execute("INSERT INTO exposures(knowledge_id,level,note,created_at) VALUES(?,'registrado',?,?)",
                                     (kid, "Registrado por importación; sin afirmar lectura ni comprensión.", timestamp))
                        result["knowledge"] += 1
                    ids[item.id] = kid
                    conn.execute("INSERT INTO session_knowledge VALUES(?,?,?)", (sid, item.id, kid))
                    for ev in item.evidence:
                        conn.execute("INSERT OR IGNORE INTO evidence(knowledge_id,source_id,locator,excerpt) VALUES(?,?,?,?)",
                                     (kid, sources[ev.source_id], ev.locator, ev.excerpt))
                    for topic in item.topics:
                        conn.execute("INSERT OR IGNORE INTO topics(name,normalized) VALUES(?,?)", (topic, normalized(topic)))
                        tid = conn.execute("SELECT id FROM topics WHERE normalized=?", (normalized(topic),)).fetchone()[0]
                        conn.execute("INSERT OR IGNORE INTO knowledge_topics VALUES(?,?)", (kid, tid))
                    for task in item.tasks:
                        if self._insert_task(conn, kid, task, timestamp):
                            result["tasks"] += 1
                        tid = conn.execute("SELECT id FROM tasks WHERE knowledge_id=? AND fingerprint=?",
                                           (kid, task_fingerprint(task))).fetchone()[0]
                        conn.execute("INSERT OR IGNORE INTO task_sessions VALUES(?,?)", (tid, sid))
                for rel in session.relations:
                    if ids[rel.from_id] == ids[rel.to_id]:
                        raise ValueError("La deduplicación convierte una relación en autorreferencia. Revisa el archivo.")
                    conn.execute("INSERT OR IGNORE INTO relations(from_id,to_id,label,explanation,session_id) VALUES(?,?,?,?,?)",
                                 (ids[rel.from_id], ids[rel.to_id], rel.label, rel.explanation, sid))
        return result

    @staticmethod
    def _insert_task(conn, kid, task, timestamp):
        cursor = conn.execute("""INSERT OR IGNORE INTO tasks(knowledge_id,fingerprint,mode,prompt,expected_answer,rubric_json,created_at)
            VALUES(?,?,?,?,?,?,?)""", (kid, task_fingerprint(task), task.mode, task.prompt,
            task.expected_answer, canonical(task.rubric), timestamp))
        if cursor.rowcount:
            tid = cursor.lastrowid
            card = Card(card_id=tid, due=datetime.fromisoformat(timestamp))
            conn.execute("INSERT INTO cards(task_id,card_json,due) VALUES(?,?,?)", (tid, card.to_json(), timestamp))
            return tid
        return None

    def add_task(self, knowledge_id, task: Task, at=None):
        with connection(self.path, write=True) as conn:
            if not conn.execute("SELECT 1 FROM knowledge WHERE id=?", (knowledge_id,)).fetchone():
                raise ValueError("Conocimiento no encontrado.")
            return self._insert_task(conn, knowledge_id, task, stamp(at))

    def add_relation(self, from_id, to_id, label, explanation=""):
        label = label.strip()
        if from_id == to_id or not label or len(label) > 300 or len(explanation) > 10000:
            raise ValueError("Elige dos conocimientos distintos y una relación de hasta 300 caracteres.")
        with connection(self.path, write=True) as conn:
            try:
                conn.execute("INSERT OR IGNORE INTO relations(from_id,to_id,label,explanation) VALUES(?,?,?,?)",
                             (from_id, to_id, label, explanation.strip()))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Uno de los conocimientos ya no existe.") from exc

    def expose(self, knowledge_id, level, note="", at=None):
        if level not in ("leido", "comprendido"):
            raise ValueError("Estado de exposición inválido.")
        with connection(self.path, write=True) as conn:
            conn.execute("INSERT INTO exposures(knowledge_id,level,note,created_at) VALUES(?,?,?,?)",
                         (knowledge_id, level, note.strip(), stamp(at)))

    def list_knowledge(self, query="", topic=None, epistemic=None, at=None):
        with connection(self.path) as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM knowledge ORDER BY created_at DESC,id DESC")]
            topic_map = {}
            for r in conn.execute("SELECT kt.knowledge_id,t.name FROM knowledge_topics kt JOIN topics t ON t.id=kt.topic_id ORDER BY t.name"):
                topic_map.setdefault(r[0], []).append(r[1])
            understood = {r[0] for r in conn.execute("SELECT DISTINCT knowledge_id FROM exposures WHERE level='comprendido'")}
            read = {r[0] for r in conn.execute("SELECT DISTINCT knowledge_id FROM exposures WHERE level='leido'")}
            task_map = {}
            for r in conn.execute("SELECT t.*,c.card_json,c.due,c.version FROM tasks t JOIN cards c ON c.task_id=t.id"):
                task_map.setdefault(r["knowledge_id"], []).append(dict(r))
            reviews = {}
            for r in conn.execute("SELECT * FROM reviews ORDER BY reviewed_at,id"):
                reviews.setdefault(r["task_id"], []).append(dict(r))
            evidence_text = {}
            for r in conn.execute("""SELECT e.knowledge_id,e.excerpt,e.locator,s.title,s.citation,ss.summary,ss.title
                FROM evidence e JOIN sources s ON s.id=e.source_id JOIN sessions ss ON ss.id=s.session_id"""):
                evidence_text.setdefault(r[0], []).extend(str(x) for x in tuple(r)[1:])
        current = utc(at)
        scheduler = Scheduler.from_json(self.settings()["scheduler"])
        result = []
        for row in rows:
            row["topics"] = topic_map.get(row["id"], [])
            tasks = task_map.get(row["id"], [])
            rs = [r for t in tasks for r in reviews.get(t["id"], [])]
            stage = STAGES[2] if row["id"] in understood else STAGES[1] if row["id"] in read else STAGES[0]
            if rs:
                stage = STAGES[3]
            demonstrated = bool(tasks)
            recall = []
            for t in tasks:
                history = reviews.get(t["id"], [])
                passes = [datetime.fromisoformat(r["reviewed_at"]) for r in history if r["score"] >= 3 and not r["assisted"]]
                enough = len(passes) >= 2 and passes[-1] - passes[0] >= timedelta(days=1)
                last_pass = bool(history and history[-1]["score"] >= 3 and not history[-1]["assisted"])
                p = scheduler.get_card_retrievability(Card.from_json(t["card_json"]), current)
                if history:
                    recall.append(p)
                demonstrated = demonstrated and enough and last_pass and p >= 0.8
            if demonstrated:
                stage = STAGES[4]
            row.update(stage=stage, task_count=len(tasks), review_count=len(rs),
                       recall=round(sum(recall) / len(recall), 3) if recall else None)
            haystack = normalized(" ".join([row["title"], row["content"], *row["topics"], *evidence_text.get(row["id"], [])]))
            if query and normalized(query) not in haystack:
                continue
            if topic and topic not in row["topics"]:
                continue
            if epistemic and row["epistemic"] != epistemic:
                continue
            result.append(row)
        return result

    def detail(self, kid):
        with connection(self.path) as conn:
            item = conn.execute("SELECT * FROM knowledge WHERE id=?", (kid,)).fetchone()
            if item is None:
                raise ValueError("Conocimiento no encontrado.")
            result = dict(item)
            result["evidence"] = [dict(r) for r in conn.execute("""SELECT e.*,s.title,s.url,s.citation,s.kind,
                ss.id AS session_id,ss.title AS session_title,ss.original_text,ss.summary,ss.occurred_at
                FROM evidence e JOIN sources s ON s.id=e.source_id JOIN sessions ss ON ss.id=s.session_id
                WHERE e.knowledge_id=?""", (kid,))]
            result["tasks"] = [dict(r) for r in conn.execute("SELECT t.*,c.due,c.version FROM tasks t JOIN cards c ON c.task_id=t.id WHERE knowledge_id=?", (kid,))]
            result["reviews"] = [dict(r) for r in conn.execute("""SELECT r.*,t.prompt,t.mode FROM reviews r JOIN tasks t ON t.id=r.task_id
                WHERE t.knowledge_id=? ORDER BY reviewed_at DESC,r.id DESC""", (kid,))]
            result["exposures"] = [dict(r) for r in conn.execute("SELECT * FROM exposures WHERE knowledge_id=? ORDER BY created_at DESC", (kid,))]
        return result

    def tasks(self, *, due_only=True, at=None):
        sql = """SELECT t.*,c.due,c.version,c.card_json,k.title,k.epistemic,k.as_of,k.recheck_on
            FROM tasks t JOIN cards c ON c.task_id=t.id JOIN knowledge k ON k.id=t.knowledge_id"""
        params = ()
        if due_only:
            sql += " WHERE c.due <= ?"
            params = (stamp(at),)
        sql += " ORDER BY c.due,t.id"
        with connection(self.path) as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def review(self, task_id, answer, score, *, assisted=False, feedback="", errors="", token=None,
               expected_version=None, at=None, duration_ms=None):
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 4:
            raise ValueError("Puntuación entre 0 y 4.")
        if not answer.strip() or len(answer) > 50_000:
            raise ValueError("Escribe una respuesta de entre 1 y 50.000 caracteres.")
        if assisted and score > 2:
            raise ValueError("Una respuesta con ayuda no demuestra recuperación autónoma: máximo 2.")
        if duration_ms is not None and (not isinstance(duration_ms, int) or duration_ms < 0):
            raise ValueError("Duración inválida.")
        if len(feedback) > 50_000 or len(errors) > 50_000:
            raise ValueError("Comentario demasiado largo.")
        when = utc(at)
        token = token or str(uuid.uuid4())
        if not token or len(token) > 200:
            raise ValueError("Identificador de intento inválido.")
        with connection(self.path, write=True) as conn:
            previous = conn.execute("SELECT * FROM reviews WHERE token=?", (token,)).fetchone()
            if previous:
                if (previous["task_id"], previous["answer"], previous["score"], previous["assisted"], previous["feedback"], previous["errors"]) != (
                        task_id, answer.strip(), score, int(assisted), feedback.strip(), errors.strip()):
                    raise ValueError("El identificador ya corresponde a otro intento.")
                return dict(previous)
            row = conn.execute("SELECT * FROM cards WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise ValueError("Evaluación no encontrada.")
            if expected_version is not None and row["version"] != expected_version:
                raise ValueError("Este ejercicio cambió en otra pestaña. Recarga antes de evaluar.")
            card = Card.from_json(row["card_json"])
            if when < card.due and card.last_review is None:
                raise ValueError("El intento no puede ser anterior a la creación del ejercicio.")
            if card.last_review and when <= card.last_review:
                raise ValueError("La fecha del intento debe ser posterior al último repaso.")
            rating = Rating.Again if assisted or score <= 1 else {2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}[score]
            scheduler_json = conn.execute("SELECT value FROM settings WHERE key='scheduler'").fetchone()[0]
            updated, log = Scheduler.from_json(scheduler_json).review_card(card, rating, review_datetime=when, review_duration=duration_ms)
            rid = conn.execute("""INSERT INTO reviews(token,task_id,answer,score,assisted,rating,feedback,errors,reviewed_at,duration_ms,
                card_before,card_after,log_json,scheduler_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (token, task_id, answer.strip(), score, int(assisted), int(rating), feedback.strip(), errors.strip(), stamp(when),
                 duration_ms, row["card_json"], updated.to_json(), log.to_json(), scheduler_json)).lastrowid
            conn.execute("UPDATE cards SET card_json=?,due=?,version=version+1 WHERE task_id=?",
                         (updated.to_json(), stamp(updated.due), task_id))
            return dict(conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone())

    def relations(self):
        with connection(self.path) as conn:
            return [dict(r) for r in conn.execute("""SELECT r.*,a.title AS from_title,b.title AS to_title FROM relations r
                JOIN knowledge a ON a.id=r.from_id JOIN knowledge b ON b.id=r.to_id ORDER BY r.id DESC""")]

    def sessions(self):
        with connection(self.path) as conn:
            return [dict(r) for r in conn.execute("""SELECT s.*, (SELECT count(*) FROM session_knowledge sk WHERE sk.session_id=s.id) AS knowledge_count
                FROM sessions s ORDER BY s.occurred_at DESC""")]

    def export_sessions(self):
        return json.dumps({"schema_version": 1, "sessions": [json.loads(s["payload_json"]) for s in self.sessions()]},
                          ensure_ascii=False, indent=2)

    def statistics(self, at=None):
        current = utc(at)
        zone = ZoneInfo(self.settings()["timezone"])
        today = current.astimezone(zone).date()
        knowledge = self.list_knowledge(at=current)
        tasks = self.tasks(due_only=False)
        with connection(self.path) as conn:
            reviews = [dict(r) for r in conn.execute("SELECT * FROM reviews ORDER BY reviewed_at,id")]
        daily = {}
        for r in reviews:
            day = datetime.fromisoformat(r["reviewed_at"]).astimezone(zone).date().isoformat()
            entry = daily.setdefault(day, {"fecha": day, "intentos": 0, "autonomos_correctos": 0})
            entry["intentos"] += 1
            entry["autonomos_correctos"] += int(r["score"] >= 3 and not r["assisted"])
        calendar = []
        for offset in range(30):
            day = today + timedelta(days=offset)
            count = sum(datetime.fromisoformat(t["due"]).astimezone(zone).date() == day for t in tasks)
            calendar.append({"fecha": day.isoformat(), "ejercicios": count})
        return {"knowledge": len(knowledge), "sessions": len(self.sessions()), "tasks": len(tasks),
                "due": sum(datetime.fromisoformat(t["due"]) <= current for t in tasks),
                "overdue": sum(datetime.fromisoformat(t["due"]).astimezone(zone).date() < today for t in tasks),
                "reviews": len(reviews), "demonstrated": sum(k["stage"] == STAGES[4] for k in knowledge),
                "without_tasks": sum(k["task_count"] == 0 for k in knowledge),
                "recheck": sum(bool(k["recheck_on"] and k["recheck_on"] <= today.isoformat()) for k in knowledge),
                "success": sum(r["score"] >= 3 and not r["assisted"] for r in reviews) / len(reviews) if reviews else None,
                "daily": list(daily.values()), "calendar": calendar,
                "stages": [{"estado": s, "conocimientos": sum(k["stage"] == s for k in knowledge)} for s in STAGES]}
