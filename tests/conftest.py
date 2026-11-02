import json
from datetime import datetime, timezone

import pytest

from academia.db import ROOT
from academia.models import ImportBundle
from academia.service import Academy


@pytest.fixture
def instant():
    return datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def payload():
    return {"schema_version": 1, "sessions": [{
        "external_id": "test-session", "title": "Lógica y evidencia",
        "occurred_at": "2026-10-20T10:00:00+01:00", "summary": "Aprendimos una regla de inferencia.",
        "original_text": "P y P implica Q permiten inferir Q.",
        "sources": [{"id": "s1", "title": "Conversación aportada", "kind": "chatgpt"}],
        "knowledge": [{"id": "k1", "title": "Modus ponens", "content": "P; P implica Q; por tanto Q.",
                       "kind": "concepto", "epistemic": "verificable", "topics": ["Lógica", "Filosofía"],
                       "evidence": [{"source_id": "s1", "locator": "Turno 2", "excerpt": "P y P implica Q permiten inferir Q."}],
                       "tasks": [{"mode": "explicacion", "prompt": "Explica la regla.",
                                  "expected_answer": "De P y P implica Q inferimos Q.",
                                  "rubric": ["Incluye las dos premisas", "Concluye Q"]}]}]
    }]}


@pytest.fixture
def bundle(payload):
    return ImportBundle.model_validate(payload)


@pytest.fixture
def academy(tmp_path):
    return Academy(tmp_path / "test.sqlite3")


@pytest.fixture
def populated(academy, bundle, instant):
    academy.import_bundle(bundle, at=instant)
    return academy


@pytest.fixture
def example():
    return json.loads((ROOT / "examples" / "sesion.json").read_text(encoding="utf-8"))
