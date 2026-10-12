#!/usr/bin/env python3
"""Mask people provably under 18 in Gotaleden's public race payload.

Known source age <18, or competition year minus birth year <=17, is sufficient.
Ambiguous age 18/birth year differences are NOT classified as definite minors.
This is a public-identity suppression, not irreversible anonymisation.
"""
from __future__ import annotations
import hashlib

IDENTITY_FIELDS=("canonical_name","first_name","last_name","listed_contact_name",
    "club","nation","nationality","age","birth_year","person_key",
    "public_contestant_uid","source_external_id","external_result_id","bib_number")

def minor(row, year):
    age=row.get("age")
    if type(age) is int and 0<=age<18:
        return True
    birth=row.get("birth_year")
    if type(birth) is int and type(year) is int and 1850<=birth<=year and 0<=year-birth<=17:
        return True
    return False

def opaque(race_key, key):
    return "anon-"+hashlib.sha256(f"gt-minor|{race_key}|{key}".encode()).hexdigest()[:24]

def mask_item(row,race_key):
    orig=str(row.get("bib") or row.get("source_result_id") or row.get("public_contestant_uid") or "")
    pid=opaque(race_key,orig)
    for key in IDENTITY_FIELDS:
        if key in row:row[key]=None
    for key in ("name","name_as_published","member_name_as_published","runner_name_as_published"):
        if key in row:row[key]="Anonym löpare"
    row["bib"]=pid
    if "source_result_id" in row:row["source_result_id"]=pid
    if "identity_status" in row:row["identity_status"]="source_local"
    if "identity_scope" in row:row["identity_scope"]="race_result"
    return orig,pid

def suppress_payload(payload):
    mappings={}
    count=0
    for race_key,race in (payload.get("races") or {}).items():
        year=race.get("year")
        for rec in race.get("records",[]):
            if not minor(rec,year):continue
            original,pid=mask_item(rec,race_key)
            if original:mappings[(str(race_key),original)]=pid
            count+=1
    for split in payload.get("splits",[]):
        key=(str(split.get("race_key") or ""),str(split.get("bib") or ""))
        if key in mappings:split["bib"]=mappings[key]
    for member in payload.get("team_members",[]):
        race_key=str(member.get("race_key") or "")
        orig=str(member.get("bib") or "")
        mapping=mappings.get((race_key,orig))
        if mapping:
            for key in IDENTITY_FIELDS:
                if key in member:member[key]=None
            for key in ("name","name_as_published","member_name_as_published"):
                if key in member:member[key]="Anonym löpare"
            member["bib"]=mapping
        elif minor(member,(payload.get("races") or {}).get(race_key,{}).get("year")):
            mask_item(member,race_key);count+=1
    return count
