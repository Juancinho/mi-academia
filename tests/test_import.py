from copy import deepcopy

import pytest
from pydantic import ValidationError

from academia.db import connection
from academia.models import ImportBundle, parse_bundle


def test_example_includes_all_evaluation_modes(example, academy, instant):
    result = academy.import_bundle(ImportBundle.model_validate(example), at=instant)
    assert (result["knowledge"], result["tasks"]) == (4, 7)
    assert len({t["mode"] for t in academy.tasks(due_only=False)}) == 7
    assert len(academy.relations()) == 2


def test_preview_does_not_write(academy, bundle):
    preview = academy.preview_import(bundle)
    assert preview["knowledge"] == 1 and preview["tasks"] == 1
    assert academy.sessions() == []


def test_reimport_is_idempotent(populated, bundle):
    result = populated.import_bundle(bundle)
    assert result["skipped"] == 1
    assert result["knowledge"] == result["tasks"] == 0
    assert len(populated.list_knowledge()) == 1
    assert len(populated.detail(1)["exposures"]) == 1


def test_optional_notes_preserve_existing_payload_and_hash(bundle):
    assert "study_notes" not in bundle.sessions[0].model_dump(mode="json")


def test_study_notebook_round_trip_and_references(academy):
    from pathlib import Path
    material = parse_bundle(Path("examples/cuaderno-estudio.json").read_text(encoding="utf-8"))
    notes = material.sessions[0].study_notes
    assert notes and len(notes.sections) == 4
    academy.import_bundle(material)
    exported = parse_bundle(academy.export_sessions())
    assert exported.sessions[0].study_notes == notes
    assert academy.import_bundle(exported)["skipped"] == 1
    assert all(k["stage"] == "Registrado" for k in academy.list_knowledge())
    broken = material.model_dump(mode="json")
    broken["sessions"][0]["study_notes"]["sections"][0]["source_ids"] = ["absent"]
    with pytest.raises(ValidationError):
        ImportBundle.model_validate(broken)


def test_same_knowledge_keeps_all_sources_and_task_origins(populated, payload):
    payload["sessions"][0]["external_id"] = "second-session"
    payload["sessions"][0]["sources"][0]["title"] = "Otra fuente"
    payload["sessions"][0]["knowledge"][0]["topics"] += ["Transversal"]
    result = populated.import_bundle(ImportBundle.model_validate(payload))
    assert result["reused"] == 1 and result["tasks"] == 0
    assert len(populated.detail(1)["evidence"]) == 2
    assert "Transversal" in populated.list_knowledge()[0]["topics"]
    with connection(populated.path) as conn:
        assert conn.execute("SELECT count(*) FROM task_sessions").fetchone()[0] == 2


def test_conflicting_session_is_atomic(populated, payload):
    new_session = deepcopy(payload["sessions"][0])
    new_session["external_id"] = "would-be-new"
    payload["sessions"][0]["summary"] = "Contenido modificado"
    payload["sessions"].insert(0, new_session)
    bundle = ImportBundle.model_validate(payload)
    with pytest.raises(ValueError, match="Conflicto"):
        populated.import_bundle(bundle)
    assert len(populated.sessions()) == 1
    with pytest.raises(ValueError, match="otro contenido"):
        populated.preview_import(bundle)


def test_different_epistemic_status_or_date_never_merges(populated, payload):
    payload["sessions"][0]["external_id"] = "new-date"
    item = payload["sessions"][0]["knowledge"][0]
    item.update(epistemic="cambiante", as_of="2026-10-20")
    populated.import_bundle(ImportBundle.model_validate(payload))
    payload["sessions"][0]["external_id"] = "another-date"
    item["as_of"] = "2026-10-21"
    populated.import_bundle(ImportBundle.model_validate(payload))
    assert len(populated.list_knowledge()) == 3


@pytest.mark.parametrize("mutation", [
    lambda p: p["sessions"][0]["knowledge"][0]["evidence"][0].update(source_id="missing"),
    lambda p: p["sessions"][0]["knowledge"][0]["evidence"][0].update(locator="", excerpt=""),
    lambda p: p["sessions"][0]["knowledge"][0].update(epistemic="cambiante"),
    lambda p: p["sessions"][0]["knowledge"][0].update(mastery=100),
    lambda p: p["sessions"][0].update(occurred_at="2026-10-20T09:00:00"),
    lambda p: p["sessions"][0]["sources"][0].update(url="javascript:alert(1)"),
    lambda p: p["sessions"][0]["sources"].append(deepcopy(p["sessions"][0]["sources"][0])),
    lambda p: p["sessions"][0]["knowledge"][0]["tasks"][0].update(rubric=[]),
    lambda p: p["sessions"][0].update(relations=[{"from_id": "k1", "to_id": "absent", "label": "causa"}]),
    lambda p: p.update(schema_version=999),
])
def test_bad_import_contract(payload, mutation):
    mutation(payload)
    with pytest.raises(ValidationError):
        ImportBundle.model_validate(payload)


def test_duplicate_json_keys_and_size_rejected():
    with pytest.raises(ValueError, match="duplicada"):
        parse_bundle('{"schema_version": 1, "schema_version": 2, "sessions": []}')
    with pytest.raises(ValueError, match="10 MB"):
        parse_bundle(" " * (10 * 1024 * 1024 + 1))


def test_dedup_self_relation_rolls_back(academy, payload):
    session = payload["sessions"][0]
    second = deepcopy(session["knowledge"][0])
    second["id"] = "k2"
    session["knowledge"].append(second)
    session["relations"] = [{"from_id": "k1", "to_id": "k2", "label": "igual"}]
    with pytest.raises(ValueError, match="autorreferencia"):
        academy.import_bundle(ImportBundle.model_validate(payload))
    assert academy.sessions() == []
    assert academy.list_knowledge() == []


def test_parameterized_search_and_accented_text(populated):
    assert len(populated.list_knowledge("LÓGICA")) == 1
    assert len(populated.list_knowledge("Conversación aportada")) == 1
    assert populated.list_knowledge("' OR 1=1; DROP TABLE knowledge;--") == []
    assert len(populated.list_knowledge()) == 1
