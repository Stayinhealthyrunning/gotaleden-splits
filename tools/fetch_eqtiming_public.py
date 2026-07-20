#!/usr/bin/env python3
"""Cache contestant details from EQ Timing's public event 77906 endpoint.

The adapter is deliberately narrow: it only requests bibs already present in the
official combined result list, validates race and bib, and writes one reproducible
source snapshot. Existing valid entries are reused on subsequent runs.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT_ID = 77906
RESULTS = ROOT / "data/source/eqtiming/Resultlist-77906-20260719155435.csv"
OUTPUT = ROOT / "data/source/eqtiming/api/event-77906-contestants.json"
ENDPOINT = f"https://live.eqtiming.com/api/Result/Contestant/{EVENT_ID}"


def result_rows() -> list[dict[str, str]]:
    with RESULTS.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def load_cache() -> dict[str, object]:
    if not OUTPUT.exists():
        return {"event_id": EVENT_ID, "endpoint": ENDPOINT, "contestants": {}}
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    if payload.get("event_id") != EVENT_ID:
        raise ValueError(f"Unexpected event in {OUTPUT}")
    return payload


def fetch_bib(bib: str, timeout: float) -> dict[str, object]:
    request = urllib.request.Request(
        f"{ENDPOINT}?bib={bib}",
        headers={"EQLiveLocale": "sv-SE", "User-Agent": "Gotaleden-Splits/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_all(timeout: float) -> dict[str, object]:
    request = urllib.request.Request(
        f"https://live.eqtiming.com/api/Contestants/{EVENT_ID}",
        headers={"EQLiveLocale": "sv-SE", "User-Agent": "Gotaleden-Splits/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Bulk endpoint did not return an object")
    ids = [int(key) for key in payload]
    detailed: dict[str, object] = {}
    for offset in range(0, len(ids), 100):
        body = json.dumps(ids[offset : offset + 100]).encode("utf-8")
        detail_request = urllib.request.Request(
            f"https://live.eqtiming.com/api/Contestants/{EVENT_ID}?passes=true",
            data=body,
            headers={
                "Content-Type": "application/json",
                "EQLiveLocale": "sv-SE",
                "User-Agent": "Gotaleden-Splits/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(detail_request, timeout=timeout) as response:
            chunk = json.load(response)
        if not isinstance(chunk, dict):
            raise ValueError("Detailed bulk endpoint did not return an object")
        detailed.update(chunk)
    return detailed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0.12, help="Seconds between public requests")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--individual", action="store_true", help="Use one request per bib instead of the bulk endpoint")
    args = parser.parse_args()

    rows = result_rows()
    cache = load_cache()
    contestants = cache.setdefault("contestants", {})
    assert isinstance(contestants, dict)
    failures: list[str] = []
    fetched = 0
    bulk_by_bib: dict[str, object] = {}
    cache_complete = cache.get("passes_included") and len(contestants) == len(rows)
    if not args.individual and (args.refresh or not cache_complete):
        for item in fetch_all(args.timeout).values():
            if isinstance(item, dict) and item.get("Startnummer") is not None:
                bulk_by_bib[str(item["Startnummer"])] = item
    for index, row in enumerate(rows, 1):
        bib = str(row["Startnumber"])
        existing = contestants.get(bib)
        if not args.refresh and cache.get("passes_included") and isinstance(existing, dict) and existing.get("UID", 0):
            continue
        try:
            item = bulk_by_bib.get(bib) if bulk_by_bib else fetch_bib(bib, args.timeout)
            if not isinstance(item, dict):
                raise ValueError("bib missing from public response")
            stage = ((item.get("Etappe") or {}).get("Navn")) or ((item.get("Pulje") or {}).get("Navn"))
            if str(item.get("Startnummer")) != bib or stage != row["Stage"]:
                raise ValueError(f"validation mismatch: bib={item.get('Startnummer')} stage={stage}")
            contestants[bib] = item
            fetched += 1
        except Exception as exc:  # report all failures after preserving successful responses
            failures.append(f"{bib}: {exc}")
        if args.individual and index < len(rows):
            time.sleep(max(args.delay, 0))

    cache["fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
    cache["expected_count"] = len(rows)
    cache["response_count"] = len(contestants)
    cache["passes_included"] = not args.individual or not failures
    cache["failures"] = failures
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(json.dumps({"fetched": fetched, "cached": len(contestants), "failures": failures}, ensure_ascii=False))
    if failures or len(contestants) != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
