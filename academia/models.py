"""Contrato de intercambio con ChatGPT. No admite dominio importado."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[\w.:-]{1,150}$")]
Kind = Literal["concepto", "hecho", "procedimiento", "relacion", "competencia"]
Epistemic = Literal["verificable", "interpretacion", "opinion", "cambiante"]
Mode = Literal["recuperacion", "explicacion", "razonamiento", "comparacion", "analisis", "demostracion", "practica"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrictModel):
    id: Key
    title: Short
    kind: Literal["chatgpt", "libro", "articulo", "web", "video", "personal", "otro"]
    url: str | None = Field(default=None, max_length=2000)
    citation: str = Field(default="", max_length=10_000)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        if value is not None:
            parsed = urlparse(value)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username:
                raise ValueError("La URL debe ser http(s), sin credenciales.")
        return value


class Evidence(StrictModel):
    source_id: Key
    locator: str = Field(default="", max_length=2000)
    excerpt: str = Field(default="", max_length=20_000)

    @model_validator(mode="after")
    def located(self):
        if not self.locator.strip() and not self.excerpt.strip():
            raise ValueError("Cada evidencia necesita localizador o fragmento original.")
        return self


class Task(StrictModel):
    mode: Mode
    prompt: Text
    expected_answer: Text
    rubric: list[Short] = Field(min_length=1, max_length=20)


class Knowledge(StrictModel):
    id: Key
    title: Short
    content: Text
    kind: Kind
    epistemic: Epistemic
    as_of: date | None = None
    recheck_on: date | None = None
    topics: list[Short] = Field(default_factory=list, max_length=50)
    evidence: list[Evidence] = Field(min_length=1, max_length=50)
    tasks: list[Task] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def dated(self):
        if self.epistemic == "cambiante" and self.as_of is None:
            raise ValueError("El conocimiento cambiante necesita as_of (fecha de referencia).")
        if self.recheck_on and self.as_of and self.recheck_on < self.as_of:
            raise ValueError("recheck_on debe ser posterior o igual a as_of.")
        return self


class Relation(StrictModel):
    from_id: Key
    to_id: Key
    label: Short
    explanation: str = Field(default="", max_length=10_000)

    @model_validator(mode="after")
    def not_self(self):
        if self.from_id == self.to_id:
            raise ValueError("Una relación necesita dos conocimientos distintos.")
        return self


class Session(StrictModel):
    external_id: Key
    title: Short
    occurred_at: AwareDatetime
    summary: Text
    original_text: str = Field(default="", max_length=500_000)
    sources: list[Source] = Field(min_length=1, max_length=100)
    knowledge: list[Knowledge] = Field(min_length=1, max_length=500)
    relations: list[Relation] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def references(self):
        source_ids = {s.id for s in self.sources}
        knowledge_ids = {k.id for k in self.knowledge}
        if len(source_ids) != len(self.sources) or len(knowledge_ids) != len(self.knowledge):
            raise ValueError("Los identificadores de fuentes y conocimientos deben ser únicos en la sesión.")
        for item in self.knowledge:
            if any(e.source_id not in source_ids for e in item.evidence):
                raise ValueError(f"Fuente desconocida en {item.id}.")
        for relation in self.relations:
            if relation.from_id not in knowledge_ids or relation.to_id not in knowledge_ids:
                raise ValueError("La relación referencia un conocimiento ausente de la sesión.")
        return self


class ImportBundle(StrictModel):
    schema_version: Literal[1]
    sessions: list[Session] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_sessions(self):
        if len({s.external_id for s in self.sessions}) != len(self.sessions):
            raise ValueError("external_id debe ser único en el archivo.")
        return self


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def knowledge_fingerprint(item: Knowledge) -> str:
    # No mezclar épocas, interpretaciones u opiniones diferentes.
    return digest([normalized(item.title), normalized(item.content), item.kind, item.epistemic,
                   str(item.as_of or ""), str(item.recheck_on or "")])


def task_fingerprint(task: Task) -> str:
    return digest([task.mode, normalized(task.prompt), normalized(task.expected_answer),
                   [normalized(c) for c in task.rubric]])


def parse_bundle(raw: bytes | str) -> ImportBundle:
    if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > 10 * 1024 * 1024:
        raise ValueError("El archivo supera 10 MB. Divide la importación en sesiones.")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Clave JSON duplicada: {key}")
            result[key] = value
        return result
    return ImportBundle.model_validate(json.loads(raw, object_pairs_hook=unique_keys))
