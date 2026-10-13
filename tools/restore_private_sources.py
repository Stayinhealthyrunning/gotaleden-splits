#!/usr/bin/env python3
"""Restore verified Gotaleden sources from an authenticated private checkout.

The command logs only aggregate counts. It never prints source contents,
participant identifiers, names, or registry values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> tuple[int, str]:
    checksum = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            checksum.update(chunk)
    return size, checksum.hexdigest()


def destination(relative: str) -> Path:
    if relative == "source/gotaleden.sqlite":
        return ROOT / "data" / "gotaleden.sqlite"
    if relative.startswith("source/eqtiming/"):
        return ROOT / "data" / "source" / relative.removeprefix("source/")
    if relative.startswith("source/gpx/"):
        return ROOT / "data" / "source" / relative.removeprefix("source/")
    raise SystemExit("Private manifest contains an unapproved Gotaleden path")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", required=True, type=Path)
    args = parser.parse_args()
    private_root = args.private_root.resolve()
    project = private_root / "gotaleden"
    manifest_path = project / "SOURCE_MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit("Private Gotaleden source manifest is unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 16:
        raise SystemExit("Private Gotaleden source manifest is invalid")

    restored = 0
    for entry in files:
        source = project / entry["path"]
        if not source.is_file():
            raise SystemExit("A required private Gotaleden source is missing")
        size, checksum = digest(source)
        if size != entry["bytes"] or checksum != entry["sha256"]:
            raise SystemExit("A private Gotaleden source failed integrity verification")
        target = destination(entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != (size, checksum):
            raise SystemExit("A restored Gotaleden source failed verification")
        restored += 1
    print(f"Private Gotaleden sources restored and verified: {restored}")


if __name__ == "__main__":
    main()
