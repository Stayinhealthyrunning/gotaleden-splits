#!/usr/bin/env python3
"""Shared public-identity suppression helpers for Loppanalys race exports.

Suppression rules contain normalized-name SHA-256 fingerprints, never plaintext
names. This is a publication safeguard, not a claim of irreversible GDPR
anonymisation: exact race observations can remain indirectly identifiable from
the official result source.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

DISPLAY_NAME = "Anonym löpare"
FULL_NAME_KEYS = (
    "name", "name_as_published", "canonical_name", "member_name_as_published",
    "runner_name_as_published", "published_name", "NavnFormatert",
)
FIRST_NAME_KEYS = ("first_name", "firstname", "FirstName", "Firstname", "Fornavn", "Förnamn")
LAST_NAME_KEYS = ("last_name", "surname", "Surname", "Etternavn", "Efternamn")
DIRECT_ID_KEYS = (
    "bib", "club", "listed_contact_name", "source_member_result_id",
    "public_contestant_uid",
)


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"\s+", " ", text).strip()


def name_fingerprint(value: Any) -> str:
    return hashlib.sha256(normalize_name(value).encode("utf-8")).hexdigest()


def load_rules(path: str | Path) -> dict[str, Any]:
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    if int(rules.get("schema_version", 0)) != 1:
        raise ValueError("Unsupported privacy suppression schema")
    rules.setdefault("display_name", DISPLAY_NAME)
    rules["_fingerprints"] = set(rules.get("suppressed_name_sha256") or [])
    return rules


def _candidate_names(record: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in FULL_NAME_KEYS:
        value = record.get(key)
        if value not in (None, ""):
            candidates.append(str(value))
    for first_key in FIRST_NAME_KEYS:
        first = record.get(first_key)
        if first in (None, ""):
            continue
        for last_key in LAST_NAME_KEYS:
            last = record.get(last_key)
            if last in (None, ""):
                continue
            candidates.extend((f"{first} {last}", f"{last} {first}"))
    return candidates


def is_suppressed_name(value: Any, rules: dict[str, Any]) -> bool:
    normalized = normalize_name(value)
    if not normalized:
        return False
    if normalized == normalize_name(rules.get("display_name", DISPLAY_NAME)):
        return True
    return name_fingerprint(normalized) in rules["_fingerprints"]


def record_is_suppressed(record: dict[str, Any], rules: dict[str, Any]) -> bool:
    return any(is_suppressed_name(value, rules) for value in _candidate_names(record))


def sanitize_identity(record: dict[str, Any], rules: dict[str, Any]) -> bool:
    """Mask public identity fields in-place, preserving performance fields."""
    if not record_is_suppressed(record, rules):
        return False
    display = rules.get("display_name", DISPLAY_NAME)
    for key in FULL_NAME_KEYS:
        if key in record:
            record[key] = display
    for key in (*FIRST_NAME_KEYS, *LAST_NAME_KEYS, *DIRECT_ID_KEYS):
        if key in record:
            record[key] = None
    return True


def opaque_result_id(race_key: Any, source_result_id: Any) -> str:
    raw = f"loppanalys-public|{race_key}|{source_result_id}".encode("utf-8")
    return "anon-" + hashlib.sha256(raw).hexdigest()[:20]
