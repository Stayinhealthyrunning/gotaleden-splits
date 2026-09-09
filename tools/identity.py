"""Conservative deterministic canonical-person identity resolution."""
from __future__ import annotations

import hashlib
from typing import Any


VALID_SCOPES = frozenset({"race_edition", "source_event", "provider"})


class IdentityConfigError(ValueError):
    pass


class IdentityConflictError(ValueError):
    pass


def _person_key(namespace: str) -> str:
    return "person-" + hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:24]


def identity_namespace(evidence: dict[str, Any], *, race_key: str, source_event_key: str) -> str:
    scope = evidence.get("scope")
    provider = evidence.get("provider")
    id_type = evidence.get("id_type")
    external_id = evidence.get("external_id")
    if scope not in VALID_SCOPES:
        raise IdentityConfigError(f"Invalid identity scope {scope!r}")
    if not provider or not id_type or external_id in (None, ""):
        raise IdentityConfigError("Identity evidence requires provider, id_type and external_id")
    if scope == "provider":
        scope_key = provider
    elif scope == "source_event":
        if not source_event_key:
            raise IdentityConfigError("source_event identity requires source_event_key")
        scope_key = source_event_key
    else:
        if not race_key:
            raise IdentityConfigError("race_edition identity requires race_key")
        scope_key = race_key
    return f"{scope}:{provider}:{scope_key}:{id_type}:{external_id}"


def resolve_person_identity(
    evidence: list[dict[str, Any]], *, race_key: str, source_event_key: str, local_result_id: str,
) -> dict[str, Any]:
    verified = [item for item in evidence if item.get("confidence") == "verified" and item.get("external_id") not in (None, "")]
    namespaces = {identity_namespace(item, race_key=race_key, source_event_key=source_event_key) for item in verified}
    if len(namespaces) > 1:
        raise IdentityConflictError(f"Conflicting verified identities for {race_key}/{local_result_id}")
    if namespaces:
        namespace = next(iter(namespaces))
        scope = next(iter(verified))["scope"]
        return {"person_key": _person_key(namespace), "status": "verified", "scope": scope, "namespaces": sorted(namespaces)}
    namespace = f"local:race_edition:{race_key}:{local_result_id}"
    return {"person_key": _person_key(namespace), "status": "local", "scope": "race_edition", "namespaces": []}


def external_identity_row(
    evidence: dict[str, Any], *, athlete_id: int, race_key: str, source_event_key: str,
) -> tuple[Any, ...]:
    namespace = identity_namespace(evidence, race_key=race_key, source_event_key=source_event_key)
    scope = evidence["scope"]
    scope_key = evidence["provider"] if scope == "provider" else source_event_key if scope == "source_event" else race_key
    return (
        athlete_id, evidence["provider"], evidence["id_type"], scope, scope_key,
        str(evidence["external_id"]), evidence.get("confidence", "verified"),
        evidence.get("evidence"), namespace,
    )
