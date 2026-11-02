from datetime import datetime, timedelta, timezone
import json

import pytest
from fsrs import Card, Rating, Scheduler

from academia.models import Task
from academia.service import STAGES


def test_read_and_understood_never_imply_mastery(populated, instant):
    assert populated.list_knowledge(at=instant)[0]["stage"] == STAGES[0]
    populated.expose(1, "leido", at=instant)
    assert populated.list_knowledge(at=instant)[0]["stage"] == STAGES[1]
    populated.expose(1, "comprendido", "Creo que sí", at=instant)
    assert populated.list_knowledge(at=instant)[0]["stage"] == STAGES[2]
    assert populated.statistics(at=instant)["demonstrated"] == 0


def test_fsrs_state_and_audit_match_library(populated, instant):
    task = populated.tasks(due_only=False)[0]
    before = Card.from_json(task["card_json"])
    expected, expected_log = Scheduler.from_json(populated.settings()["scheduler"]).review_card(before, Rating.Good, review_datetime=instant)
    review = populated.review(task["id"], "P y P implica Q, por tanto Q.", 3, at=instant, token="first", expected_version=0)
    assert json.loads(review["card_after"]) == expected.to_dict()
    assert json.loads(review["log_json"]) == expected_log.to_dict()
    assert review["card_before"] == task["card_json"]
    after = populated.tasks(due_only=False)[0]
    assert after["version"] == 1 and after["due"] == expected.due.isoformat()
    assert populated.tasks(at=instant) == []
    assert len(populated.tasks(at=expected.due)) == 1


def test_review_token_is_idempotent_and_rejects_changed_data(populated, instant):
    a = populated.review(1, "Respuesta", 3, token="same", at=instant, expected_version=0)
    b = populated.review(1, "Respuesta", 3, token="same", at=instant, expected_version=0)
    assert a == b
    assert populated.tasks(due_only=False)[0]["version"] == 1
    with pytest.raises(ValueError, match="otro intento"):
        populated.review(1, "Respuesta distinta", 3, token="same", at=instant)
    assert len(populated.detail(1)["reviews"]) == 1


def test_concurrent_stale_review_does_not_overwrite_card(populated, instant):
    populated.review(1, "respuesta", 3, expected_version=0, at=instant)
    with pytest.raises(ValueError, match="otra pestaña"):
        populated.review(1, "otra respuesta", 4, expected_version=0, at=instant + timedelta(minutes=1))
    assert len(populated.detail(1)["reviews"]) == 1


@pytest.mark.parametrize("score,rating", [(0, 1), (1, 1), (2, 2), (3, 3), (4, 4)])
def test_score_rating_mapping(populated, instant, score, rating):
    saved = populated.review(1, "respuesta", score, at=instant)
    assert saved["rating"] == rating


def test_assisted_answers_are_not_autonomous_success(populated, instant):
    with pytest.raises(ValueError, match="máximo 2"):
        populated.review(1, "respuesta con ayuda", 3, assisted=True, at=instant)
    review = populated.review(1, "respuesta con ayuda", 2, assisted=True, at=instant)
    assert review["rating"] == 1
    assert populated.statistics(at=instant)["success"] == 0
    assert populated.list_knowledge(at=instant)[0]["stage"] == STAGES[3]


@pytest.mark.parametrize("score,answer", [(-1, "ok"), (5, "ok"), (True, "ok"), (3, "  ")])
def test_invalid_review_is_atomic(populated, instant, score, answer):
    with pytest.raises(ValueError):
        populated.review(1, answer, score, at=instant)
    assert populated.tasks(due_only=False)[0]["version"] == 0
    assert populated.detail(1)["reviews"] == []


def test_mastery_requires_spaced_evidence_and_decreases(populated, instant):
    populated.review(1, "respuesta", 4, at=instant)
    assert populated.list_knowledge(at=instant)[0]["stage"] == STAGES[3]
    populated.review(1, "respuesta", 4, at=instant + timedelta(minutes=10))
    assert populated.list_knowledge(at=instant + timedelta(minutes=10))[0]["stage"] == STAGES[3]
    later = instant + timedelta(days=2)
    populated.review(1, "respuesta", 4, at=later)
    assert populated.list_knowledge(at=later)[0]["stage"] == STAGES[4]
    assert populated.list_knowledge(at=later + timedelta(days=3650))[0]["stage"] == STAGES[3]
    populated.review(1, "Me equivoqué", 1, errors="Confundí las premisas", at=later + timedelta(days=1))
    assert populated.list_knowledge(at=later + timedelta(days=1))[0]["stage"] == STAGES[3]
    assert populated.detail(1)["reviews"][0]["errors"] == "Confundí las premisas"


def test_every_task_needs_evidence(populated, instant):
    populated.review(1, "respuesta", 4, at=instant)
    populated.review(1, "respuesta", 4, at=instant + timedelta(days=2))
    assert populated.list_knowledge(at=instant + timedelta(days=2))[0]["stage"] == STAGES[4]
    tid = populated.add_task(1, Task(mode="practica", prompt="Aplica la regla", expected_answer="Una aplicación válida",
                                  rubric=["Usa ambas premisas"]), at=instant + timedelta(days=2))
    assert tid
    assert populated.list_knowledge(at=instant + timedelta(days=2))[0]["stage"] == STAGES[3]


def test_no_tasks_never_demonstrated(academy, payload, instant):
    from academia.models import ImportBundle
    payload["sessions"][0]["knowledge"][0]["tasks"] = []
    academy.import_bundle(ImportBundle.model_validate(payload), at=instant)
    academy.expose(1, "comprendido")
    stats = academy.statistics(at=instant)
    assert stats["without_tasks"] == 1 and stats["demonstrated"] == 0


def test_task_deduplication(populated, instant):
    task = populated.detail(1)["tasks"][0]
    duplicate = Task(mode=task["mode"], prompt=task["prompt"], expected_answer=task["expected_answer"], rubric=json.loads(task["rubric_json"]))
    assert populated.add_task(1, duplicate, at=instant) is None
    assert len(populated.tasks(due_only=False)) == 1


def test_local_calendar_across_dst_and_midnight(academy, bundle):
    # En Madrid el 25/10/2026 ya ha terminado el horario de verano.
    when = datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)
    academy.import_bundle(bundle, at=when)
    stats = academy.statistics(at=when)
    assert stats["calendar"][0] == {"fecha": "2026-10-26", "ejercicios": 1}
    academy.review(1, "respuesta", 3, at=when)
    assert academy.statistics(at=when)["daily"][0]["fecha"] == "2026-10-26"


def test_naive_and_backdated_reviews_rejected(populated, instant):
    with pytest.raises(ValueError, match="zona horaria"):
        populated.review(1, "respuesta", 3, at=instant.replace(tzinfo=None))
    populated.review(1, "respuesta", 3, at=instant)
    with pytest.raises(ValueError, match="posterior"):
        populated.review(1, "respuesta", 3, at=instant - timedelta(seconds=1))


def test_relations_across_sessions_and_self_validation(populated, payload):
    from academia.models import ImportBundle
    payload["sessions"][0]["external_id"] = "second"
    payload["sessions"][0]["knowledge"][0]["title"] = "Aplicación de lógica"
    populated.import_bundle(ImportBundle.model_validate(payload))
    populated.add_relation(1, 2, "se aplica a", "Conexión transversal")
    assert populated.relations()[0]["explanation"] == "Conexión transversal"
    with pytest.raises(ValueError):
        populated.add_relation(1, 1, "es igual a")
    with pytest.raises(ValueError):
        populated.add_relation(1, 999, "relación")
