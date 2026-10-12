#!/usr/bin/env python3
"""Rewrite current Gotaleden browser bundles in place; fail if any proven minor is still identifiable."""
import argparse,json,sys
from pathlib import Path
from public_minor_suppression import minor,suppress_payload
ROOT=Path(__file__).resolve().parents[1]
TARGETS=[ROOT/"docs/data/results.json",ROOT/"docs/data/results-2026.json"]

def audit(doc,path):
    unsafe=[]
    for rk,race in (doc.get("races") or {}).items():
        for r in race.get("records",[]):
            if minor(r,race.get("year")):unsafe.append(rk)
            if r.get("name")=="Anonym löpare" and (r.get("club") or r.get("first_name") or r.get("last_name")):
                unsafe.append(rk)
    if unsafe:raise ValueError(f"{path.name}: identifiable under-18 record or leaked anonymous name fields")

def run(check=False):
    total=0;count=0
    for path in TARGETS:
        if not path.exists():raise FileNotFoundError(path)
        doc=json.loads(path.read_text(encoding="utf-8"))
        if not check:
            total+=suppress_payload(doc)
            path.write_text(json.dumps(doc,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
        audit(doc,path);count+=1
    print(json.dumps({"files":count,"newly_masked_records":total,"audit":"PASS","mode":"check" if check else "redact"}))

if __name__=="__main__":
    args=argparse.ArgumentParser();args.add_argument("--check",action="store_true")
    run(check=args.parse_args().check)
