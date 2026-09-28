from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublicationProfileField:
    name: str
    label: str
    kind: str = "text"
    max_length: int = 500
    help_text: str = ""


@dataclass(frozen=True)
class PublicationProfileSchema:
    key: str
    version: int
    label: str
    fields: tuple[PublicationProfileField, ...]


_SCHEMAS: dict[tuple[str, str], PublicationProfileSchema] = {
    ("logos", "article"): PublicationProfileSchema(
        key="logos.article",
        version=1,
        label="Данные статьи Logos",
        fields=(
            PublicationProfileField(
                name="abstract",
                label="Аннотация",
                kind="textarea",
                max_length=4000,
                help_text="Краткое содержательное описание материала.",
            ),
            PublicationProfileField(
                name="keywords",
                label="Ключевые слова",
                kind="tags",
                max_length=80,
                help_text="Через запятую.",
            ),
            PublicationProfileField(
                name="bibliography",
                label="Литература и источники",
                kind="lines",
                max_length=500,
                help_text="Одна запись на строку.",
            ),
        ),
    ),
    ("logos", "lecture"): PublicationProfileSchema(
        key="logos.lecture",
        version=1,
        label="Данные лекции Logos",
        fields=(
            PublicationProfileField(
                name="abstract",
                label="Аннотация",
                kind="textarea",
                max_length=4000,
            ),
            PublicationProfileField(
                name="speaker",
                label="Автор или докладчик",
                max_length=240,
            ),
            PublicationProfileField(
                name="keywords",
                label="Ключевые слова",
                kind="tags",
                max_length=80,
                help_text="Через запятую.",
            ),
        ),
    ),
}


def schema_for(site_key: str, source_type: str) -> PublicationProfileSchema | None:
    return _SCHEMAS.get((site_key.strip().lower(), source_type.strip().lower()))


def schemas_for_site(site_key: str) -> dict[str, PublicationProfileSchema]:
    normalized = site_key.strip().lower()
    return {
        source_type: schema
        for (schema_site, source_type), schema in _SCHEMAS.items()
        if schema_site == normalized
    }


def profile_for_editor(extra_data: dict | None) -> dict[str, Any]:
    profile = (extra_data or {}).get("profile")
    if not isinstance(profile, dict):
        return {}
    data = profile.get("data")
    return data if isinstance(data, dict) else {}


def _clean_tags(value: str, *, max_length: int) -> list[str]:
    result: list[str] = []
    for item in value.split(","):
        cleaned = item.strip()[:max_length]
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result[:40]


def _clean_lines(value: str, *, max_length: int) -> list[str]:
    return [
        line.strip()[:max_length]
        for line in value.splitlines()
        if line.strip()
    ][:100]


def build_profile(
    site_key: str,
    source_type: str,
    values: dict[str, str],
) -> dict[str, Any] | None:
    schema = schema_for(site_key, source_type)
    if schema is None:
        return None

    data: dict[str, Any] = {}
    for field in schema.fields:
        raw = values.get(field.name, "").strip()
        if field.kind == "tags":
            data[field.name] = _clean_tags(raw, max_length=field.max_length)
            continue
        if field.kind == "lines":
            data[field.name] = _clean_lines(raw, max_length=field.max_length)
            continue
        data[field.name] = raw[:field.max_length]

    return {
        "schema": schema.key,
        "version": schema.version,
        "data": data,
    }


def public_profile(extra_data: dict | None) -> dict[str, Any] | None:
    profile = (extra_data or {}).get("profile")
    if not isinstance(profile, dict):
        return None

    schema = profile.get("schema")
    version = profile.get("version")
    data = profile.get("data")
    if not isinstance(schema, str) or not isinstance(version, int) or not isinstance(data, dict):
        return None

    return {
        "schema": schema,
        "version": version,
        "data": data,
    }
