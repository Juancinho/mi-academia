from streamlit.testing.v1 import AppTest

from academia.db import ROOT
from academia.models import parse_bundle
from academia.service import Academy


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_empty_dashboard_and_sample_workflow(monkeypatch, tmp_path):
    monkeypatch.setenv("ACADEMIA_DB", str(tmp_path / "ui.sqlite3"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
    assert not app.exception
    assert app.metric[0].value == "0"
    button(app, "Probar con una sesión de ejemplo").click().run()
    assert not app.exception
    assert app.metric[0].value == "4"
    assert len(Academy().tasks()) == 7


def test_every_page_and_full_review(monkeypatch, tmp_path):
    monkeypatch.setenv("ACADEMIA_DB", str(tmp_path / "ui.sqlite3"))
    academy = Academy()
    academy.import_bundle(parse_bundle((ROOT / "examples" / "sesion.json").read_bytes()))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
    for page in ["Biblioteca", "Conexiones", "Sesiones", "Datos", "Repasar"]:
        app.radio(key="navigation").set_value(page).run()
        assert not app.exception, (page, [e.value for e in app.exception])
    app.text_area[0].set_value("P y P implica Q, por tanto Q.")
    button(app, "Guardar borrador y ver referencia").click().run()
    assert not app.exception
    assert len(academy.detail(1)["reviews"]) == 0
    score = next(s for s in app.selectbox if s.label == "Resultado según la rúbrica")
    score.set_value(3)
    button(app, "Registrar evaluación y programar repaso").click().run()
    assert not app.exception
    assert len(academy.detail(1)["reviews"]) == 1
    assert academy.detail(1)["reviews"][0]["answer"] == "P y P implica Q, por tanto Q."


def test_import_validation_error_is_visible_and_no_writes(monkeypatch, tmp_path):
    monkeypatch.setenv("ACADEMIA_DB", str(tmp_path / "ui.sqlite3"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
    app.radio(key="navigation").set_value("Datos").run()
    next(t for t in app.text_area if t.label == "O pega el JSON").set_value('{"schema_version": 999}').run()
    assert not app.exception
    assert any("No se ha importado nada" in e.value for e in app.error)
    assert Academy().sessions() == []
