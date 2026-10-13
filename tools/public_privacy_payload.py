#!/usr/bin/env python3
"""Remove protected individual and relay identities from Gotaleden browser data.

This operates only on public export payloads. Source-backed aggregate and
provenance reports remain separate from the individual browser data.
"""
from __future__ import annotations

from privacy import DISPLAY_NAME, normalize_name, record_is_suppressed


def withhold_protected_rows(payload: dict, rules: dict) -> dict[str, int]:
    """Filter every published occurrence, including nested relay team members."""
    blocked_refs: set[tuple[str, str]] = set()
    removed_records = removed_teams = removed_members = removed_nested = 0

    def ref(row: dict, key: str = "bib") -> tuple[str, str] | None:
        value = row.get(key)
        if value in (None, ""):
            return None
        return (str(row.get("race_key") or ""), str(value))

    def protected(row: dict, race_key: str) -> bool:
        return (
            normalize_name(row.get("name")) == normalize_name(DISPLAY_NAME)
            or record_is_suppressed(row, rules, scope=race_key)
        )

    # A relay team name can itself be a personal name. Remove the entire
    # team, its results and its members when that is the case.
    kept_teams = []
    for team in payload.get("teams", []):
        scope = str(team.get("race_key") or "*")
        team_ref = ref(team)
        if protected({"name": team.get("team_name"), "bib": team.get("bib")}, scope):
            if team_ref:
                blocked_refs.add(team_ref)
            removed_teams += 1
            continue
        kept_teams.append(team)

    for race_key, race in payload.get("races", {}).items():
        kept = []
        for record in race.get("records", []):
            race_ref = (str(race_key), str(record.get("bib") or ""))
            if (record.get("bib") not in (None, "") and race_ref in blocked_refs) or protected(record, str(race_key)):
                if record.get("bib") not in (None, ""):
                    blocked_refs.add(race_ref)
                removed_records += 1
            else:
                kept.append(record)
        race["records"] = kept

    payload["splits"] = [
        split for split in payload.get("splits", [])
        if ref(split) not in blocked_refs
    ]

    teams = []
    for team in kept_teams:
        if ref(team) in blocked_refs:
            removed_teams += 1
            continue
        scope = str(team.get("race_key") or "*")
        members = []
        for member in team.get("team_members", []):
            if protected(member, scope):
                removed_nested += 1
            else:
                members.append(member)
        team["team_members"] = members
        teams.append(team)
    payload["teams"] = teams

    members = []
    for member in payload.get("team_members", []):
        scope = str(member.get("race_key") or "*")
        team_ref = ref(member, "team_bib") or ref(member)
        if team_ref in blocked_refs or protected(member, scope):
            removed_members += 1
        else:
            members.append(member)
    payload["team_members"] = members

    return {
        "removed_results": removed_records,
        "removed_teams": removed_teams,
        "removed_team_members": removed_members,
        "removed_nested_team_members": removed_nested,
    }
