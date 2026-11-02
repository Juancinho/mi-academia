"""Interfaz local. Ejecutar: python -m streamlit run app.py"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from academia.db import ROOT, backup_bytes, default_path, full_export
from academia.models import ImportBundle, Task, parse_bundle
from academia.service import Academy, EPI_LABELS, MODE_LABELS, STAGES, now_utc

st.set_page_config(page_title="Mi Academia", page_icon="🌱", layout="wide")
st.markdown("""<style>
.block-container {max-width:1200px;padding-top:2.4rem;padding-bottom:4rem}
h1 {letter-spacing:-.045em !important;font-weight:750 !important}
h2,h3 {letter-spacing:-.025em !important}
[data-testid="stMetric"] {background:white;border:1px solid #dce5df;border-radius:14px;padding:18px}
[data-testid="stSidebar"] {border-right:1px solid #dce5df}
div.stButton>button {border-radius:9px}
.eyebrow {font-size:.76rem;letter-spacing:.16em;color:#227969;font-weight:700;margin-bottom:12px}
</style>""", unsafe_allow_html=True)

try:
    academy = Academy()
except (sqlite3.Error, ValueError, OSError) as exc:
    st.error(f"No se pudo abrir la base de datos: {exc}")
    st.stop()

zone = ZoneInfo(academy.settings()["timezone"])


def local_date(value):
    return datetime.fromisoformat(value).astimezone(zone).strftime("%d/%m/%Y · %H:%M")


def go(page):
    st.session_state["navigation"] = page


def flash(message):
    st.session_state["flash"] = message


def display_table(rows):
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


with st.sidebar:
    st.title("🌱 Mi Academia")
    st.caption("Tu aprendizaje, conectado.")
    page = st.radio("Espacio de aprendizaje", ["Inicio", "Biblioteca", "Repasar", "Conexiones", "Sesiones", "Datos"],
                    key="navigation", label_visibility="collapsed")
    st.divider()
    due = len(academy.tasks())
    st.caption(f"{due} ejercicios pendientes ahora")
    st.caption("Local · SQLite · Sin suscripción")
    st.caption(f"Horario: {zone.key}")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))


def home():
    st.markdown('<div class="eyebrow">UN ESPACIO PARA SEGUIR APRENDIENDO</div>', unsafe_allow_html=True)
    st.title("Haz que lo aprendido permanezca.")
    st.write("Recoge ideas, conecta conocimientos y comprueba qué puedes recordar y aplicar.")
    stats = academy.statistics()
    cols = st.columns(4)
    for col, label, value in zip(cols, ["Conocimientos", "Para repasar ahora", "Dominio demostrado", "Sesiones"],
                                 [stats["knowledge"], stats["due"], stats["demonstrated"], stats["sessions"]]):
        col.metric(label, value)
    st.write("")
    a, b = st.columns([3, 2], gap="large")
    with a:
        with st.container(border=True):
            st.subheader("Tu siguiente paso")
            if stats["due"]:
                st.write(f"Tienes **{stats['due']} ejercicios** listos para recuperar, explicar o poner en práctica.")
                st.button("Comenzar repaso →", type="primary", on_click=go, args=("Repasar",))
            elif stats["knowledge"]:
                st.write("Estás al día. Puedes explorar conexiones o registrar una nueva sesión.")
                st.button("Explorar mi biblioteca →", on_click=go, args=("Biblioteca",))
            else:
                st.write("Empieza importando una sesión de ChatGPT o registra una idea desde el formulario.")
                st.button("Registrar mi primera sesión →", type="primary", on_click=go, args=("Datos",))
                if st.button("Probar con una sesión de ejemplo", key="demo_home"):
                    result = academy.import_bundle(parse_bundle((ROOT / "examples" / "sesion.json").read_bytes()))
                    flash(f"Ejemplo cargado: {result['knowledge']} conocimientos nuevos. Puedes reimportarlo sin duplicados.")
                    st.rerun()
        st.subheader("Evidencia de aprendizaje")
        st.bar_chart(pd.DataFrame(stats["stages"]).set_index("estado"), color="#227969")
        st.caption("Importar registra el conocimiento. Lectura y comprensión se declaran expresamente. El dominio requiere práctica autónoma repetida.")
    with b:
        with st.container(border=True):
            st.subheader("Una academia sin asignaturas fijas")
            st.write("Un mismo conocimiento puede pertenecer a varios temas y conectar con cualquier otro.")
            st.write("**1. Registra** una conversación o una fuente.\n\n**2. Responde** antes de ver la solución.\n\n**3. Evalúa** con una rúbrica y vuelve cuando toque.")
            if stats["without_tasks"]:
                st.info(f"{stats['without_tasks']} conocimientos aún no tienen ejercicios. Añádelos desde la biblioteca.")
            if stats["recheck"]:
                st.warning(f"{stats['recheck']} conocimientos necesitan revisar sus fuentes por fecha.")
    st.subheader("Actividad y evolución")
    if stats["daily"]:
        st.line_chart(pd.DataFrame(stats["daily"]).set_index("fecha"), color=["#227969", "#c28c3c"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Intentos registrados", stats["reviews"])
        c2.metric("Aciertos autónomos", f"{stats['success']:.0%}")
        c3.metric("Ejercicios creados", stats["tasks"])
        st.caption("Acierto autónomo = puntuación 3 o 4 sin ayuda. La valoración es manual en este MVP.")
    else:
        st.info("Aquí aparecerá tu evolución cuando completes tu primera evaluación.")
    st.subheader("Calendario de repasos · próximos 30 días")
    if stats["overdue"]:
        st.warning(f"Además hay {stats['overdue']} ejercicios de días anteriores pendientes.")
    st.bar_chart(pd.DataFrame(stats["calendar"]).set_index("fecha"), color="#227969")
    with st.expander("Ver agenda con horas"):
        display_table([{"Conocimiento": t["title"], "Evaluación": MODE_LABELS[t["mode"]],
                        "Fecha prevista": local_date(t["due"])} for t in academy.tasks(due_only=False)])
        st.caption("La agenda cuenta los ejercicios programados ahora. Cada respuesta modifica la siguiente fecha mediante FSRS.")


def library():
    st.title("Biblioteca")
    st.write("Busca ideas y vuelve a sus fuentes. Los temas son etiquetas libres y combinables.")
    all_items = academy.list_knowledge()
    c1, c2, c3 = st.columns([2, 1, 1])
    query = c1.text_input("Buscar", placeholder="Concepto, contenido, tema o fuente…")
    topic = c2.selectbox("Tema", ["Todos", *sorted({t for k in all_items for t in k["topics"]})])
    epi = c3.selectbox("Naturaleza", ["Todas", *EPI_LABELS], format_func=lambda v: EPI_LABELS.get(v, v))
    c1, c2 = st.columns(2)
    stage = c1.selectbox("Evidencia", ["Todas", *STAGES])
    no_tasks = c2.checkbox("Solo conocimientos sin ejercicios")
    items = academy.list_knowledge(query, None if topic == "Todos" else topic, None if epi == "Todas" else epi)
    items = [k for k in items if (stage == "Todas" or k["stage"] == stage) and (not no_tasks or not k["task_count"])]
    if not items:
        st.info("No hay conocimientos con estos filtros. Puedes registrar una sesión en Datos.")
        return
    display_table([{"Conocimiento": k["title"], "Temas": ", ".join(k["topics"]), "Evidencia": k["stage"],
                    "Ejercicios": k["task_count"], "Intentos": k["review_count"]} for k in items])
    by_id = {k["id"]: k for k in items}
    kid = st.selectbox("Abrir conocimiento", list(by_id), format_func=lambda v: by_id[v]["title"])
    item = by_id[kid]
    detail = academy.detail(kid)
    st.divider()
    st.subheader(item["title"])
    st.caption(f"{item['kind'].capitalize()} · {EPI_LABELS[item['epistemic']]} · {item['stage']}")
    st.write(item["content"])
    if item["as_of"]:
        st.caption(f"Fecha de referencia: {item['as_of']}")
    if item["recheck_on"]:
        st.caption(f"Revisar fuentes: {item['recheck_on']}")
    if item["epistemic"] == "verificable":
        st.caption("Verificable describe su naturaleza; no significa que el sistema haya comprobado su veracidad.")
    if item["recall"] is not None:
        st.caption(f"Recuerdo estimado por FSRS en los ejercicios practicados: {item['recall']:.0%}. No mide comprensión.")
    with st.expander("Registrar lectura o comprensión"):
        with st.form(f"exposure_{kid}"):
            level = st.selectbox("Mi valoración", ["comprendido", "leido"],
                                 format_func=lambda v: "Creo que lo he comprendido" if v == "comprendido" else "Lo he leído")
            note = st.text_input("Nota opcional")
            if st.form_submit_button("Registrar valoración"):
                academy.expose(kid, level, note)
                flash("Valoración registrada. El dominio se determina con evaluaciones.")
                st.rerun()
    tab_sources, tab_tasks, tab_history = st.tabs(["Fuentes y sesiones", "Evaluaciones", "Historial"])
    with tab_sources:
        for ev in detail["evidence"]:
            with st.expander(f"{ev['title']} · {ev['locator'] or 'Fragmento'}"):
                st.write(ev["excerpt"] or "Sin fragmento: usa el localizador de la fuente.")
                st.caption(ev["citation"])
                if ev["url"]:
                    st.link_button("Abrir fuente original", ev["url"])
                st.write(f"Sesión: **{ev['session_title']}** · {local_date(ev['occurred_at'])}")
                st.write(ev["summary"])
                if ev["original_text"]:
                    st.text(ev["original_text"])
    with tab_tasks:
        for task in detail["tasks"]:
            with st.container(border=True):
                st.caption(MODE_LABELS[task["mode"]])
                st.write(task["prompt"])
                st.caption(f"Próximo repaso: {local_date(task['due'])}")
                with st.expander("Consultar referencia y rúbrica (cuenta como ayuda si vas a responder)"):
                    st.write(task["expected_answer"])
                    for criterion in json.loads(task["rubric_json"]):
                        st.write(f"• {criterion}")
        with st.expander("Añadir una evaluación"):
            with st.form(f"new_task_{kid}", clear_on_submit=True):
                mode = st.selectbox("Forma de evaluación", list(MODE_LABELS), format_func=MODE_LABELS.get)
                prompt = st.text_area("Pregunta o ejercicio")
                expected = st.text_area("Respuesta de referencia")
                rubric = st.text_area("Criterios de la rúbrica (uno por línea)")
                if st.form_submit_button("Crear evaluación"):
                    try:
                        task = Task(mode=mode, prompt=prompt, expected_answer=expected,
                                    rubric=[x.strip() for x in rubric.splitlines() if x.strip()])
                        tid = academy.add_task(kid, task)
                        flash("Evaluación creada y lista para practicar." if tid else "Esta evaluación ya existía.")
                        st.rerun()
                    except (ValueError, ValidationError) as exc:
                        st.error(str(exc))
    with tab_history:
        if not detail["reviews"]:
            st.info("Aún no hay evaluaciones para este conocimiento.")
        display_table([{"Fecha": local_date(r["created_at"]), "Registro": r["level"], "Nota": r["note"]}
                       for r in detail["exposures"]])
        for review in detail["reviews"]:
            with st.expander(f"{local_date(review['reviewed_at'])} · {review['score']}/4 · {'Con ayuda' if review['assisted'] else 'Sin ayuda'}"):
                st.write(review["prompt"])
                st.text(review["answer"])
                st.write("**Errores o lagunas:**", review["errors"] or "Sin nota")
                st.write("**Comentario:**", review["feedback"] or "Sin nota")
                st.caption(f"Autocorrección · FSRS {review['rating']}/4 · Registro #{review['id']}")


def review_page():
    st.title("Repasar y demostrar")
    st.write("Responde primero. Después contrasta tu respuesta con la referencia y la rúbrica.")
    early = st.checkbox("Practicar también ejercicios futuros (actualiza su programación)")
    tasks = academy.tasks(due_only=not early)
    if not tasks:
        st.success("No tienes ejercicios pendientes ahora." if not early else "Aún no tienes ejercicios creados.")
        st.button("Ir a la biblioteca", on_click=go, args=("Biblioteca",))
        return
    by_id = {t["id"]: t for t in tasks}
    tid = st.selectbox("Ejercicio", list(by_id), format_func=lambda v: f"{by_id[v]['title']} · {MODE_LABELS[by_id[v]['mode']]} · #{v}")
    task = by_id[tid]
    start_key = f"started_{tid}_{task['version']}"
    st.session_state.setdefault(start_key, time.monotonic())
    st.caption(f"{MODE_LABELS[task['mode']]} · Programado: {local_date(task['due'])}")
    if task["epistemic"] in ("opinion", "interpretacion"):
        st.info("Evalúa la coherencia y la justificación según la rúbrica. La referencia no representa una verdad única.")
    if task["epistemic"] == "cambiante":
        st.warning(f"Conocimiento sujeto a cambios. Responde en el contexto de {task['as_of']} y comprueba la fuente si buscas la situación actual.")
    st.subheader(task["prompt"])
    pending = st.session_state.get("pending_review")
    if not pending or pending["task_id"] != tid or pending["version"] != task["version"]:
        with st.form(f"answer_{tid}_{task['version']}"):
            answer = st.text_area("Tu respuesta o evidencia del ejercicio", height=180, max_chars=50_000,
                                  help="Para un ejercicio práctico, pega el resultado, código o explicación de lo que has hecho.")
            assisted = st.checkbox("He usado pistas, fuentes o he visto la respuesta")
            if st.form_submit_button("Guardar borrador y ver referencia", type="primary"):
                if not answer.strip():
                    st.error("Escribe una respuesta antes de ver la referencia.")
                else:
                    st.session_state["pending_review"] = {"task_id": tid, "answer": answer.strip(),
                        "assisted": assisted, "version": task["version"], "token": str(uuid.uuid4()),
                        "duration_ms": int((time.monotonic() - st.session_state[start_key]) * 1000)}
                    st.rerun()
        return
    st.caption("Respuesta fijada para este intento; solo se guarda en la base al registrar la evaluación.")
    st.text(pending["answer"])
    st.subheader("Referencia y criterios")
    st.write(task["expected_answer"])
    for criterion in json.loads(task["rubric_json"]):
        st.write(f"• {criterion}")
    st.caption("Autocorrección manual. No hay un corrector de IA activo ni comprobación automática de la respuesta.")
    labels = {0: "0 · No pude responder", 1: "1 · Incorrecta o con lagunas esenciales",
              2: "2 · Parcial / difícil", 3: "3 · Correcta y autónoma", 4: "4 · Completa y fluida"}
    with st.form(f"grade_{pending['token']}"):
        assisted = st.checkbox("Usé ayuda antes de fijar la respuesta", value=pending["assisted"])
        score = st.selectbox("Resultado según la rúbrica", list(labels), index=2, format_func=labels.get)
        errors = st.text_area("Errores y lagunas detectados", max_chars=50_000)
        feedback = st.text_area("Comentario o evidencia adicional", max_chars=50_000)
        st.caption("FSRS: 0–1 → Otra vez; 2 → Difícil; 3 → Bien; 4 → Fácil. Con ayuda: máximo 2 y se reprograma como Otra vez.")
        if st.form_submit_button("Registrar evaluación y programar repaso", type="primary"):
            try:
                saved = academy.review(tid, pending["answer"], score, assisted=assisted,
                    feedback=feedback, errors=errors, token=pending["token"], expected_version=pending["version"],
                    duration_ms=pending["duration_ms"])
                due = json.loads(saved["card_after"])["due"]
                del st.session_state["pending_review"]
                flash(f"Evaluación registrada. Siguiente repaso: {local_date(due)}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if st.button("Descartar borrador"):
        del st.session_state["pending_review"]
        st.rerun()


def connections_page():
    st.title("Conexiones")
    st.write("Relaciona ideas de cualquier área: causas, ejemplos, analogías, requisitos o contradicciones.")
    items = academy.list_knowledge()
    if len(items) < 2:
        st.info("Registra al menos dos conocimientos para crear conexiones.")
        return
    by_id = {k["id"]: k for k in items}
    focus = st.selectbox("Explorar alrededor de", [0, *by_id],
                         format_func=lambda v: "Toda la biblioteca" if v == 0 else by_id[v]["title"])
    relations = academy.relations()
    visible = [r for r in relations if focus == 0 or focus in (r["from_id"], r["to_id"])]
    if visible:
        # json.dumps escapa los títulos importados para el lenguaje DOT.
        nodes = {r[k] for r in visible for k in ("from_id", "to_id")}
        dot = ['digraph { graph [bgcolor="transparent", rankdir="LR"]; node [shape="box", style="rounded,filled", fillcolor="#e0eee7", color="#227969", fontname="Arial"];']
        dot += [f'{kid} [label={json.dumps(by_id[kid]["title"], ensure_ascii=False)}];' for kid in nodes]
        dot += [f'{r["from_id"]} -> {r["to_id"]} [label={json.dumps(r["label"], ensure_ascii=False)}];' for r in visible]
        dot.append("}")
        st.graphviz_chart("\n".join(dot))
        for rel in visible:
            with st.container(border=True):
                st.write(f"**{rel['from_title']}** → {rel['label']} → **{rel['to_title']}**")
                if rel["explanation"]:
                    st.write(rel["explanation"])
                st.caption(f"Origen: sesión #{rel['session_id']}" if rel["session_id"] else "Conexión añadida manualmente")
    else:
        st.info("Todavía no hay conexiones en esta selección.")
    with st.expander("Conectar dos conocimientos"):
        with st.form("relation", clear_on_submit=True):
            left = st.selectbox("Desde", list(by_id), format_func=lambda v: by_id[v]["title"])
            right = st.selectbox("Hacia", list(by_id), index=1, format_func=lambda v: by_id[v]["title"])
            label = st.text_input("Relación", placeholder="es un requisito para / contrasta con / se aplica a…", max_chars=300)
            explanation = st.text_area("Por qué están relacionados", max_chars=10000)
            if st.form_submit_button("Crear conexión"):
                try:
                    academy.add_relation(left, right, label, explanation)
                    flash("Conexión guardada.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def sessions_page():
    st.title("Sesiones")
    st.write("El registro original que da contexto a tus conocimientos.")
    sessions = academy.sessions()
    if not sessions:
        st.info("Todavía no has registrado sesiones. Empieza en Datos.")
    for session in sessions:
        with st.expander(f"{session['title']} · {local_date(session['occurred_at'])} · {session['knowledge_count']} conocimientos"):
            st.caption(f"Identificador: {session['external_id']} · Importada: {local_date(session['imported_at'])}")
            st.write(session["summary"])
            if session["original_text"]:
                st.text(session["original_text"])
            st.download_button("Descargar sesión original JSON", json.dumps({"schema_version": 1,
                "sessions": [json.loads(session["payload_json"])]}, ensure_ascii=False, indent=2),
                file_name=f"sesion-{session['id']}.json", mime="application/json", key=f"session_dl_{session['id']}")


def import_tab():
    st.write("Pega un JSON o carga un archivo. Primero se valida y se muestra qué se añadirá.")
    upload = st.file_uploader("Archivo de sesiones", type=["json"])
    pasted = st.text_area("O pega el JSON", height=180)
    raw = upload.getvalue() if upload else pasted
    if upload and pasted.strip():
        st.caption("Se usa el archivo cargado. Retíralo para importar el texto pegado.")
    if raw:
        try:
            bundle = parse_bundle(raw)
            preview = academy.preview_import(bundle)
            display_table([{"Sesiones nuevas": preview["sessions"], "Sesiones ya importadas": preview["skipped"],
                            "Conocimientos nuevos": preview["knowledge"], "Reutilizados": preview["reused"], "Evaluaciones nuevas": preview["tasks"]}])
            with st.expander("Revisar contenido validado"):
                st.json(bundle.model_dump(mode="json"), expanded=False)
            if st.button("Importar sesiones validadas", type="primary"):
                result = academy.import_bundle(bundle)
                st.success(f"Importación completada: {result['sessions']} sesiones, {result['knowledge']} conocimientos nuevos, {result['tasks']} evaluaciones nuevas.")
        except (ValidationError, ValueError, UnicodeError, RecursionError) as exc:
            st.error(f"No se ha importado nada. Revisa el archivo:\n{exc}")
    st.divider()
    st.download_button("Descargar ejemplo válido", (ROOT / "examples" / "sesion.json").read_bytes(),
                       file_name="sesion-ejemplo.json", mime="application/json")
    st.download_button("Descargar contrato JSON Schema", json.dumps(ImportBundle.model_json_schema(), ensure_ascii=False, indent=2),
                       file_name="academia-schema-v1.json", mime="application/schema+json")
    with st.expander("Instrucciones para ChatGPT"):
        st.code((ROOT / "docs" / "prompt-chatgpt.md").read_text(encoding="utf-8"), language=None)
    st.caption("Mi Academia no accede a tu historial privado de ChatGPT. Tú eliges qué conversaciones o fragmentos traer.")


def manual_tab():
    st.write("Guarda una idea con su fuente. Puedes añadir más conocimientos mediante importación JSON.")
    with st.form("quick_session", clear_on_submit=True):
        session_title = st.text_input("Título de la sesión", max_chars=300)
        summary = st.text_area("Qué has aprendido")
        source_title = st.text_input("Fuente original", placeholder="Conversación, libro, artículo…", max_chars=300)
        source_kind = st.selectbox("Tipo de fuente", ["chatgpt", "libro", "articulo", "web", "video", "personal", "otro"])
        url = st.text_input("URL de la fuente (opcional)")
        excerpt = st.text_area("Fragmento original", help="Conserva la evidencia que da origen al conocimiento.")
        title = st.text_input("Título del conocimiento", max_chars=300)
        content = st.text_area("Conocimiento en tus palabras")
        c1, c2 = st.columns(2)
        kind = c1.selectbox("Tipo de conocimiento", ["concepto", "hecho", "procedimiento", "relacion", "competencia"])
        epistemic = c2.selectbox("Naturaleza del conocimiento", list(EPI_LABELS), format_func=EPI_LABELS.get)
        topics = st.text_input("Temas separados por comas", placeholder="Sin categorías fijas: lógica, historia, escritura…")
        as_of = st.date_input("Fecha de referencia", value=now_utc().astimezone(zone).date())
        recheck = st.date_input("Volver a comprobar la fuente (opcional)", value=None)
        st.caption("Evaluación inicial opcional; también puedes añadirla después desde Biblioteca.")
        mode = st.selectbox("Modalidad", list(MODE_LABELS), format_func=MODE_LABELS.get)
        prompt = st.text_area("Pregunta o ejercicio (opcional)")
        expected = st.text_area("Respuesta de referencia (si añades ejercicio)")
        rubric = st.text_area("Criterios (uno por línea, si añades ejercicio)")
        if st.form_submit_button("Registrar sesión", type="primary"):
            try:
                task_data = []
                if prompt.strip() or expected.strip() or rubric.strip():
                    task_data = [{"mode": mode, "prompt": prompt, "expected_answer": expected,
                                  "rubric": [x.strip() for x in rubric.splitlines() if x.strip()]}]
                bundle = ImportBundle.model_validate({"schema_version": 1, "sessions": [{
                    "external_id": f"manual-{uuid.uuid4()}", "title": session_title, "occurred_at": now_utc(),
                    "summary": summary, "original_text": excerpt,
                    "sources": [{"id": "fuente", "title": source_title, "kind": source_kind, "url": url or None}],
                    "knowledge": [{"id": "idea", "title": title, "content": content, "kind": kind,
                        "epistemic": epistemic, "as_of": as_of, "recheck_on": recheck,
                        "topics": [x.strip() for x in topics.split(",") if x.strip()],
                        "evidence": [{"source_id": "fuente", "excerpt": excerpt}], "tasks": task_data}]}]})
                academy.import_bundle(bundle)
                flash("Sesión registrada con su fuente. El conocimiento está listo en Biblioteca.")
                st.rerun()
            except (ValidationError, ValueError) as exc:
                st.error(str(exc))


def data_page():
    st.title("Tus datos, bajo tu control")
    tabs = st.tabs(["Importar sesiones", "Registro rápido", "Exportar y respaldar", "Preferencias"])
    with tabs[0]:
        import_tab()
    with tabs[1]:
        manual_tab()
    with tabs[2]:
        st.write("La copia SQLite incluye sesiones, fuentes, evaluaciones, respuestas e historial FSRS.")
        st.caption(f"Base de datos activa: {default_path().resolve()}")
        if st.button("Preparar exportaciones actualizadas"):
            st.session_state["exports"] = {"backup": backup_bytes(), "full": full_export(),
                                            "sessions": academy.export_sessions(), "at": now_utc().isoformat()}
        if "exports" in st.session_state:
            exports = st.session_state["exports"]
            st.caption(f"Instantánea preparada: {local_date(exports['at'])}. Vuelve a prepararla después de nuevos cambios.")
            st.download_button("Copia de seguridad SQLite", exports["backup"], "mi-academia-backup.sqlite3", "application/octet-stream")
            st.download_button("Exportación completa JSON", exports["full"], "mi-academia-completa.json", "application/json")
            st.download_button("Sesiones reimportables JSON", exports["sessions"], "mi-academia-sesiones.json", "application/json")
        st.info("Para restaurar una copia SQLite, usa el comando de restauración del README. Restaura siempre a un archivo nuevo.")
        st.caption("La exportación completa JSON es para portabilidad y análisis; el importador de sesiones usa el otro formato. La restauración íntegra usa SQLite.")
    with tabs[3]:
        st.write("Las fechas de FSRS se guardan en UTC y se muestran en tu zona horaria.")
        with st.form("timezone"):
            name = st.text_input("Zona horaria IANA", value=zone.key, help="Ejemplo: Europe/Madrid, America/Mexico_City")
            if st.form_submit_button("Guardar zona horaria"):
                try:
                    academy.set_timezone(name.strip())
                    st.rerun()
                except (ValueError, ZoneInfoNotFoundError):
                    st.error("Zona horaria desconocida.")
        with st.expander("Cómo se calcula el dominio"):
            st.write("Cada evaluación de un conocimiento debe tener al menos dos aciertos sin ayuda, separados por 24 horas o más. El último intento debe ser correcto y el recuerdo estimado por FSRS debe ser al menos del 80 %. Un ejercicio nuevo vuelve a exigir evidencia.")
            st.write("El dominio mostrado es provisional y depende de las evaluaciones disponibles y de tu autocorrección. No se propaga a un tema entero.")
            st.caption("FSRS tiene retención objetivo del 90 % y parámetros predeterminados, sin aleatoriedad. No se optimizan parámetros personales en este MVP.")


try:
    {"Inicio": home, "Biblioteca": library, "Repasar": review_page, "Conexiones": connections_page,
     "Sesiones": sessions_page, "Datos": data_page}[page]()
except (sqlite3.Error, OSError) as exc:
    st.error(f"No se pudo completar la operación: {exc}")
