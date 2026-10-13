#!/usr/bin/env python3
"""Adapter for the access-controlled Loppanalys publication-block registry."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DISPLAY_NAME = "Anonym löpare"
REGISTRY_ENV = "LOPPANALYS_PRIVACY_REGISTRY_B64"
REGISTRY_PATH_ENV = "LOPPANALYS_PRIVACY_REGISTRY_PATH"
REQUIRE_ENV = "LOPPANALYS_REQUIRE_PRIVATE_REGISTRY"
ALLOWED_ACTIONS = {"restrict_identifiers", "remove_result", "temporary_restriction"}
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


def _required(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return os.environ.get(REQUIRE_ENV, "").strip().casefold() in {"1", "true", "yes"}


def _private_payload() -> dict[str, Any] | None:
    encoded = os.environ.get(REGISTRY_ENV, "").strip()
    local_path = os.environ.get(REGISTRY_PATH_ENV, "").strip()
    if encoded and local_path:
        raise RuntimeError("Configure one private registry source, not both")
    if encoded:
        try:
            return json.loads(base64.b64decode(encoded, validate=True).decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("Invalid private privacy registry secret") from exc
    if local_path:
        return json.loads(Path(local_path).read_text(encoding="utf-8"))
    return None


def load_rules(path: str | Path, *, require_private: bool | None = None) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if int(policy.get("schema_version", 0)) != 2:
        raise ValueError("Unsupported public privacy policy schema")
    private = _private_payload()
    if private is None:
        if _required(require_private):
            raise RuntimeError(
                f"Private registry missing: set {REGISTRY_ENV} or {REGISTRY_PATH_ENV}; publication stopped"
            )
        entries: list[dict[str, Any]] = []
    else:
        if int(private.get("schema_version", 0)) != 2:
            raise ValueError("Unsupported private privacy registry schema")
        entries = list(private.get("entries") or [])
    for entry in entries:
        action = entry.get("action")
        fingerprint = (entry.get("match") or {}).get("normalized_name_sha256", "")
        if action not in ALLOWED_ACTIONS:
            raise ValueError("Unsupported privacy action")
        if not re.fullmatch(r"[0-9a-f]{64}", str(fingerprint)):
            raise ValueError("Private registry entry has invalid match fingerprint")
        if any(key in entry for key in ("name", "email", "birthdate")):
            raise ValueError("Private registry must not contain plaintext identity fields")
    return {
        **policy,
        "display_name": policy.get("display_name", DISPLAY_NAME),
        "_entries": entries,
        "_registry_loaded": private is not None,
    }


def _candidate_names(record: dict[str, Any]) -> list[str]:
    candidates = [str(record[key]) for key in FULL_NAME_KEYS if record.get(key) not in (None, "")]
    for first_key in FIRST_NAME_KEYS:
        first = record.get(first_key)
        if first in (None, ""):
            continue
        for last_key in LAST_NAME_KEYS:
            last = record.get(last_key)
            if last not in (None, ""):
                candidates.extend((f"{first} {last}", f"{last} {first}"))
    return candidates


def _entry_active(entry: dict[str, Any], now: datetime | None = None) -> bool:
    if entry.get("action") != "temporary_restriction":
        return True
    expires = entry.get("expires_at")
    if not expires:
        return True
    parsed = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
    return parsed > (now or datetime.now(timezone.utc))


def confirmed_minor(record: dict[str, Any]) -> bool:
    """Return true only when source fields unambiguously establish age below 18."""
    age = record.get("age")
    if isinstance(age, int) and not isinstance(age, bool) and 0 <= age < 18:
        return True
    year = record.get("year", record.get("edition_year"))
    birth_year = record.get("birth_year")
    if isinstance(year, int) and isinstance(birth_year, int) and 1850 <= birth_year <= year:
        if year - birth_year < 18:
            return True
    for key in ("age_category", "class_name", "source_class"):
        value = str(record.get(key) or "").strip()
        match = re.fullmatch(
            r"(?:\([A-Za-z]\)\s*|[A-Za-z]\s*)?(\d{1,2})\s*[-–]\s*(\d{1,2})(?:\s+(?:män|kvinnor))?",
            value,
            re.I,
        )
        if match and int(match.group(1)) <= int(match.group(2)) < 18:
            return True
    return False


def suppression_action(record: dict[str, Any], rules: dict[str, Any], *, scope: str = "*") -> str | None:
    fingerprints = {name_fingerprint(value) for value in _candidate_names(record) if normalize_name(value)}
    actions = []
    for entry in rules.get("_entries", []):
        scopes = entry.get("scopes") or ["*"]
        if scope not in scopes and "*" not in scopes:
            continue
        if not _entry_active(entry):
            continue
        if (entry.get("match") or {}).get("normalized_name_sha256") in fingerprints:
            if entry.get("require_review_for_new_matches"):
                approved = any(
                    str(item.get("scope", "*")) in {"*", scope}
                    and bool(item.get("identifiers"))
                    and all(str(record.get(key, "")) == str(value) for key, value in item["identifiers"].items())
                    for item in entry.get("approved_matches", [])
                )
                if not approved:
                    raise RuntimeError(
                        "Potential protected-identity match requires private manual review; publication stopped"
                    )
            actions.append(entry["action"])
    for action in ("remove_result", "temporary_restriction", "restrict_identifiers"):
        if action in actions:
            return action
    return None


def record_is_suppressed(record: dict[str, Any], rules: dict[str, Any], *, scope: str = "*") -> bool:
    return confirmed_minor(record) or suppression_action(record, rules, scope=scope) is not None


def is_suppressed_name(value: Any, rules: dict[str, Any], *, scope: str = "*") -> bool:
    """Compatibility helper for source/archive scanners without record objects."""
    return record_is_suppressed({"name": value}, rules, scope=scope)


def sanitize_identity(record: dict[str, Any], rules: dict[str, Any], *, scope: str = "*") -> bool:
    if not record_is_suppressed(record, rules, scope=scope):
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
