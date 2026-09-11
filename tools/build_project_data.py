#!/usr/bin/env python3
from __future__ import annotations

import errno
import json
import os
import re
import sqlite3
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "races.json"
DB = ROOT / "data" / "gotaleden.sqlite"
WEB_RESULTS = ROOT / "docs" / "data" / "results.json"
WEB_RESULTS_COMPAT = (ROOT / "docs" / "data" / "results-2026.json",)
WEB_ROUTE = ROOT / "docs" / "data" / "route.json"
REPORT = ROOT / "reports" / "import-summary.json"
REPORT_COMPAT = (ROOT / "reports" / "import-summary-2026.json",)
IS_WINDOWS = os.name == "nt"


def write_payload(path: Path, payload: dict, aliases: tuple[Path, ...] = (), *, compact: bool = True) -> None:
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(payload, ensure_ascii=False, indent=2)
    for output in (path, *aliases):
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_text(encoding="utf-8") == content:
            continue
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", delete=False,
                dir=output.parent, prefix=f".{output.name}.", suffix=".tmp",
            ) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            for attempt in range(5):
                try:
                    os.replace(temporary, output)
                    temporary = None
                    break
                except OSError as error:
                    retryable = IS_WINDOWS and (
                        error.errno in {errno.EACCES, errno.EBUSY, errno.EINVAL, errno.EPERM}
                        or getattr(error, "winerror", None) in {5, 32, 33}
                    )
                    if not retryable or attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

def normalize(value: str | None) -> str:
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def to_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None

def to_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None

def clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None

def status_code(value: str | None) -> str:
    v = (value or "").strip().upper()
    return {
        "TIME": "FINISHED",
        "FINISHED": "FINISHED",
        "DNF": "DNF",
        "DNS": "DNS",
        "DSQ": "DSQ",
    }.get(v, v or "UNKNOWN")

def prepare_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript((ROOT / "tools" / "schema.sql").read_text(encoding="utf-8"))
    return conn

if __name__ == "__main__":
    from build_official_data import import_all_official

    import_all_official()
