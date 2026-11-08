"""One-way cloud -> Obsidian publishing. Never upload or overwrite personal edits."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path


def normalized(value: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)).split())


# Export-only filing hints. Free topics and the knowledge graph remain unchanged.
AREA_HINTS = {
    "Energía e ingeniería": ("energia", "electricidad", "electrica", "electrico", "electrotecnia", "carburantes", "combustibles", "omie", "ree", "scada", "simel", "lcoe", "ppa", "kirchhoff", "potencia", "autoconsumo", "mercado marginalista"),
    "Economía y finanzas": ("economia", "microeconomia", "macroeconomia", "fiscal", "fiscalidad", "contabilidad", "inflacion", "deuda", "productividad", "finanzas", "econometria", "bienestar", "demografia", "coste de oportunidad", "costes marginales"),
    "Tecnología e informática": ("informatica", "programacion", "software", "algoritmos", "inteligencia artificial", "ia", "ml", "machine learning", "litografia", "hbm", "cowos", "fotonica", "semiconductores", "data leakage", "backtesting", "forecasting"),
    "Ciencias y matemáticas": ("matematicas", "algebra", "calculo", "geometria", "estadistica", "fisica", "quimica", "biologia", "geologia", "astronomia", "logica"),
    "Historia y sociedad": ("historia", "politica", "sociologia", "derecho", "geografia", "antropologia"),
    "Lengua, arte y humanidades": ("lengua", "idiomas", "literatura", "filosofia", "arte", "musica", "gramatica"),
    "Salud y vida cotidiana": ("salud", "medicina", "nutricion", "psicologia", "deporte"),
}


def choose_area(topics: list[str], title: str = "", organization: dict | None = None, fallback: str = "Por organizar") -> str:
    organization = organization or {}
    overrides = {normalized(k): slug(v) for k, v in organization.get("topic_areas", {}).items()}
    for topic in topics:
        if normalized(topic) in overrides:
            return overrides[normalized(topic)]
    scores = dict.fromkeys(AREA_HINTS, 0)
    for text, weight in [(t, 1) for t in topics] + [(title, 2)]:
        text = normalized(text)
        for area, hints in AREA_HINTS.items():
            if any(re.search(r"(?<!\w)" + re.escape(hint) + r"(?!\w)", text) for hint in hints):
                scores[area] += weight
    best = max(scores, key=scores.get)
    return best if scores[best] else fallback


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def slug(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\[\]#^]', " ", value)
    value = " ".join(value.split()).strip(" .")[:70].strip(" .") or "Sin título"
    if value.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        value = "_" + value
    return value


def frontmatter(**values) -> str:
    return "---\n" + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in values.items()) + "\n---\n\n"


def safe_target(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Ruta de sincronización no permitida.")
    target = root / path
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("La ruta o un enlace sale de Mi Academia.")
    return target


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=".academia-", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def build_files(snapshot: dict, previous: dict, organization: dict | None = None) -> dict[str, tuple[str, str]]:
    if snapshot.get("format") != "mi-academia-vault" or snapshot.get("version") != 1:
        raise ValueError("La respuesta no es una copia de Mi Academia compatible.")
    books = snapshot["notebooks"]
    concepts = snapshot["knowledge"]
    chats = snapshot["conversations"]
    relations = snapshot["relations"]
    paths: dict[str, str] = {}
    files: dict[str, tuple[str, str]] = {}
    sources: dict[str, dict] = {}
    source_keys: dict[tuple[str, str], str] = {}
    organization = organization or {}
    book_areas: dict[str, str] = {}
    concept_areas: dict[str, str] = {}
    topic_areas: dict[str, str] = {}

    def area_folder(area: str, kind: str):
        return "01 Temas/" + slug(area) + "/" + kind

    def allocate(key: str, folder: str, title: str):
        old = previous.get(key, {}).get("path")
        if old and (Path(old).is_absolute() or ".." in Path(old).parts):
            raise ValueError("Manifiesto local inválido.")
        # Keep basenames stable even when a broad area changes.
        name = Path(old).name if old else f"{slug(title)}--{digest(key)[:12]}.md"
        candidate = f"{folder}/{name}"
        paths[key] = candidate

    def link(key: str, title: str = ""):
        alias = re.sub(r"[\[\]|\r\n]", " ", title)
        return "[[Mi Academia/" + paths[key][:-3].replace("\\", "/") + ("|" + alias if alias else "") + "]]"

    def put(key: str, body: str):
        files[key] = (paths[key], body.rstrip() + "\n")

    for book in books:
        topics = list(dict.fromkeys(topic for k in book["knowledge"] for topic in k.get("topics", [])))
        area = slug(organization.get("notebook_areas", {}).get(book["id"]) or choose_area(topics, book["title"], organization))
        book_areas[book["id"]] = area
        allocate("book:" + book["id"], area_folder(area, "Cuadernos"), book["title"])
        for source in book["sources"]:
            sid = "source:" + digest(source.get("url") or json.dumps([source.get("kind"), source["title"], source.get("citation")], ensure_ascii=False))
            sources[sid] = source
            source_keys[(book["id"], source["id"])] = sid
            allocate(sid, "02 Fuentes", source["title"])
    for k in concepts:
        associated = [book_areas[e["session_id"]] for e in k.get("evidence", []) if e["session_id"] in book_areas]
        fallback = max(associated, key=associated.count) if associated else "Por organizar"
        area = choose_area(k.get("topics", []), k["title"], organization, fallback)
        concept_areas[k["id"]] = area
        allocate("concept:" + k["id"], area_folder(area, "Conceptos"), k["title"])
    for chat in chats:
        associated = [book_areas[b["id"]] for b in books if chat["id"] in b.get("conversation_ids", []) or any(row["session_id"] == b["id"] and row["conversation_id"] == chat["id"] for row in snapshot.get("conversation_sessions", []))]
        area = max(associated, key=associated.count) if associated else choose_area([], chat["title"], organization)
        allocate("chat:" + chat["id"], area_folder(area, "Conversaciones"), chat["title"])

    topic_members: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for k in concepts:
        for topic in k.get("topics", []):
            topic_members[topic].append(("concept:" + k["id"], k["title"]))
    for topic in topic_members:
        associated = [concept_areas[key.removeprefix("concept:")] for key, _ in topic_members[topic]]
        area = choose_area([topic], organization=organization, fallback=max(associated, key=associated.count))
        topic_areas[topic] = area
        allocate("topic:" + topic, area_folder(area, "Mapas"), topic)
    areas = sorted(set(book_areas.values()) | set(concept_areas.values()) | set(topic_areas.values()) | {paths["chat:" + c["id"]].split("/")[1] for c in chats})
    for area in areas:
        allocate("area:" + area, "01 Temas/" + slug(area), area)
    allocate("index", "00 Inicio", "Mi Academia")

    for book in books:
        key = "book:" + book["id"]
        body = frontmatter(academia_id=key, tipo="cuaderno", area=book_areas[book["id"]], version=book["version"], tags=["mi-academia", "cuaderno"])
        body += f"# {book['title']}\n\n{book['summary']}\n\n"
        notes = book["notes"]
        if notes.get("objectives"):
            body += "## Objetivos\n\n" + "\n".join("- " + objective for objective in notes["objectives"]) + "\n\n"
        for section in notes["sections"]:
            body += f"## {section['title']}\n\n{section['body']}\n\n"
            body += "Referencias: " + ", ".join(link(source_keys[(book["id"], sid)], sources[source_keys[(book["id"], sid)]]["title"]) for sid in section["source_ids"]) + "\n\n"
        if notes.get("glossary"):
            body += "## Glosario\n\n" + "\n\n".join(f"**{g['term']}**: {g['definition']}" for g in notes["glossary"]) + "\n\n"
        if notes.get("open_questions"):
            body += "## Dudas abiertas\n\n" + "\n".join("- " + q for q in notes["open_questions"]) + "\n\n"
        body += "[Abrir cuaderno en la web](https://mi-academia-juancinho.juan-el-g.chatgpt.site/?notebook=" + book["id"] + ")\n\n"
        body += "## Conceptos relacionados\n\n" + "\n".join("- " + link("concept:" + k["id"], k["title"]) for k in book["concepts"]) + "\n\n"
        body += "## Conversación de origen\n\n" + "\n".join("- " + link("chat:" + cid) for cid in book.get("conversation_ids", []) if "chat:" + cid in paths) + "\n\n"
        body += "La lectura de estos apuntes no acredita dominio. Los ejercicios y el historial FSRS se conservan en la academia web.\n"
        put(key, body)

    for k in concepts:
        key = "concept:" + k["id"]
        body = frontmatter(academia_id=key, tipo="concepto", area=concept_areas[k["id"]], naturaleza=k["epistemic"], estado=k.get("stage", "Registrado"), temas=k.get("topics", []), tags=["mi-academia", "concepto"])
        body += f"# {k['title']}\n\n{k['content']}\n\n## Relaciones\n\n"
        for r in relations:
            if k["id"] in (r["from_id"], r["to_id"]):
                other = r["to_id"] if r["from_id"] == k["id"] else r["from_id"]
                body += f"- {r['label']}: {link('concept:' + other)} — {r['explanation']}\n"
        body += "\n## Cuadernos y evidencia\n\n"
        for e in k.get("evidence", []):
            body += "- " + link("book:" + e["session_id"], e.get("session_title", "Cuaderno")) + " · " + e.get("locator", "") + "\n"
            if e.get("excerpt"):
                body += "\n> " + e["excerpt"].replace("\n", "\n> ") + "\n\n"
        body += "\n## Mapas de temas\n\n" + "\n".join("- " + link("topic:" + t, t) for t in k.get("topics", []))
        put(key, body)

    coverage = {"active_branch": "Rama activa de la exportación", "provided": "Texto aportado", "extracts": "Solo fragmentos o resumen; no es el chat completo"}
    for chat in chats:
        key = "chat:" + chat["id"]
        body = frontmatter(academia_id=key, tipo="conversacion", cobertura=chat["coverage"], tags=["mi-academia", "conversacion"])
        body += f"# {chat['title']}\n\n{coverage[chat['coverage']]}\n\n"
        if chat.get("url"):
            body += "[Abrir conversación original](" + chat["url"] + ")\n\n"
        for m in chat["messages"]:
            body += f"## {'Tú' if m['role']=='user' else 'ChatGPT' if m['role']=='assistant' else 'Material conservado'}\n\n{m['text']}\n\n"
        body += "## Cuadernos vinculados\n\n" + "\n".join("- " + link("book:" + row["session_id"]) for row in snapshot.get("conversation_sessions", []) if row["conversation_id"] == chat["id"])
        put(key, body)
    for key, source in sources.items():
        body = frontmatter(academia_id=key, tipo="fuente", tags=["mi-academia", "fuente"]) + "# " + source["title"] + "\n\n" + source.get("citation", "") + "\n\n"
        if source.get("url"):
            body += "[Consultar fuente](" + source["url"] + ")\n\n"
        body += "## Utilizada en\n\n" + "\n".join("- " + link("book:" + b["id"], b["title"]) for b in books if any(source_keys[(b["id"], src["id"])] == key for src in b["sources"]))
        put(key, body)
    for topic, members in topic_members.items():
        put("topic:" + topic, frontmatter(tipo="mapa", tags=["mi-academia", "mapa"]) + "# " + topic + "\n\n" + "\n".join("- " + link(key, title) for key, title in members))
    for area in areas:
        body = frontmatter(tipo="area", tags=["mi-academia", "area"]) + "# " + area + "\n\n"
        for heading, prefix in [("Cuadernos", "book:"), ("Conceptos", "concept:"), ("Conversaciones", "chat:"), ("Mapas de temas", "topic:")]:
            members = [(key, path) for key, path in paths.items() if key.startswith(prefix) and path.startswith("01 Temas/" + slug(area) + "/")]
            if members:
                body += "## " + heading + "\n\n" + "\n".join("- " + link(key, Path(path).stem.rsplit("--", 1)[0]) for key, path in members) + "\n\n"
        put("area:" + area, body)
    put("index", frontmatter(tipo="indice", tags=["mi-academia"]) + "# Mi Academia\n\n## Áreas de estudio\n\n" + "\n".join("- " + link("area:" + area, area) for area in areas) + "\n\n## Cuadernos\n\n" + "\n".join("- " + link("book:" + b["id"], b["title"]) for b in books) + "\n\n## Mapas de temas\n\n" + "\n".join("- " + link("topic:" + topic, topic) for topic in sorted(topic_members)) + "\n\nSincronización desde la web. Tus ediciones locales se conservan; los cambios de nube que entren en conflicto se guardan como copias separadas. No se eliminan notas al desaparecer del origen.")
    return files


def sync_snapshot(snapshot: dict, vault: Path, organization: dict | None = None) -> dict:
    vault = vault.resolve()
    if not vault.is_dir():
        raise ValueError("El vault debe existir.")
    root = safe_target(vault, "Mi Academia")
    root.mkdir(exist_ok=True)
    state_path = safe_target(root, ".sync-state.json")
    previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    state = dict(previous)
    result = {"written": 0, "unchanged": 0, "conflicts": 0}
    files = build_files(snapshot, previous, organization)
    moves = []
    for key, (relative, _) in files.items():
        old = previous.get(key, {}).get("path")
        if old and old != relative:
            source, target = safe_target(root, old), safe_target(root, relative)
            if source.exists():
                if target.exists():
                    raise ValueError("La reorganización encontró un destino ocupado; no se sobrescribe.")
                moves.append((source, target))
    # Preflight all destinations before moving any managed file. User content is moved verbatim.
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
    for key, (relative, content) in files.items():
        target = safe_target(root, relative)
        remote_hash = digest(content)
        record = previous.get(key, {})
        current_hash = digest(target.read_text(encoding="utf-8")) if target.exists() else None
        if current_hash == remote_hash:
            result["unchanged"] += 1
            state[key] = {"path": relative, "hash": remote_hash, "remote_hash": remote_hash}
        elif target.exists() and current_hash != record.get("hash"):
            if record.get("remote_hash") != remote_hash:
                conflict = target.with_name(target.stem + ".nube-" + remote_hash[:12] + ".md")
                if not conflict.exists():
                    atomic_write(conflict, content)
                    result["conflicts"] += 1
            state[key] = {**record, "path": relative, "remote_hash": remote_hash}
            result["unchanged"] += 1
        else:
            atomic_write(target, content)
            state[key] = {"path": relative, "hash": remote_hash, "remote_hash": remote_hash}
            result["written"] += 1
    atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2))
    # Only prune empty directories inside our resolved export root, never personal files.
    for folder in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if folder.is_dir() and not folder.is_symlink() and folder.resolve().is_relative_to(root.resolve()):
            try:
                folder.rmdir()
            except OSError:
                pass
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("El acceso privado requiere renovar la conexión; no se siguen redirecciones.")


def download_snapshot(url: str, token: str) -> dict:
    if url != "https://mi-academia-juancinho.juan-el-g.chatgpt.site/api/vault-sync":
        raise ValueError("Destino de sincronización no autorizado.")
    request = urllib.request.Request(url, headers={"OAI-Sites-Authorization": "Bearer " + token, "Accept": "application/json"})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
        data = response.read(100 * 1024 * 1024 + 1)
        if len(data) > 100 * 1024 * 1024:
            raise ValueError("La copia supera el límite de 100 MB.")
        return json.loads(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--url", default="https://mi-academia-juancinho.juan-el-g.chatgpt.site/api/vault-sync")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config else {}
        vault = args.vault or (Path(config["vault"]) if config else None)
        if vault is None:
            raise ValueError("Falta el vault.")
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        else:
            token = os.environ.get("ACADEMIA_SYNC_TOKEN")
            if token is None and args.config:
                from academia.windows_secret import transform
                token = transform(args.config.with_name("credential.dpapi").read_bytes(), decrypt=True).decode("utf-8")
            if not token:
                raise ValueError("Falta acceso privado.")
            snapshot = download_snapshot(config.get("url", args.url), token)
        report = sync_snapshot(snapshot, vault, config.get("organization"))
        if args.config:
            atomic_write(args.config.with_name("last-result.json"), json.dumps(report))
        print(json.dumps(report))
    except Exception as error:
        # Do not print request headers, credentials or note bodies into scheduled-task logs.
        report = {"error": type(error).__name__, "message": "No se pudo sincronizar. Revisa acceso, conexión y configuración local."}
        if args.config:
            atomic_write(args.config.with_name("last-result.json"), json.dumps(report))
        print(json.dumps(report))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
