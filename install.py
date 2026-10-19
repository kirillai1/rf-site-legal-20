#!/usr/bin/env python3
"""Install the adjacent portable skill into one explicitly selected NEW directory.

Python standard library only. Default is a read-only plan; --install copies files.
Does not edit agent settings, overwrite files, download dependencies, or delete data.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


NAME = "rf-site-legal-20"


def file_hash(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def linked(path):
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def collect(source):
    files = []
    for directory, dirs, names in os.walk(source, followlinks=False):
        parent = Path(directory)
        for name in dirs + names:
            if linked(parent / name):
                raise ValueError("Symlinks are not allowed in the skill package")
        for name in names:
            file = parent / name
            if not file.is_file():
                raise ValueError("Non-regular entry: " + str(file))
            files.append(file)
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True,
                        help="Full path of the new skill directory, ending in " + NAME)
    parser.add_argument("--install", action="store_true",
                        help="Perform the planned copy; without this flag nothing is changed")
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    source = package / NAME
    requested = Path(args.destination).expanduser()
    if not requested.is_absolute():
        raise ValueError("Destination must be an absolute path")
    if requested.name != NAME:
        raise ValueError("Destination directory must be named " + NAME)
    if requested.exists() or linked(requested):
        raise ValueError("Destination already exists; no files were overwritten")
    target = requested.resolve()
    if target == source or source in target.parents:
        raise ValueError("Destination must be outside the package source")
    if linked(source) or not (source / "SKILL.md").is_file():
        raise ValueError("Adjacent skill folder or SKILL.md is missing")
    files = collect(source)
    manifest = json.loads((package / "SHA256SUMS.json").read_text(encoding="utf-8"))
    expected = manifest["files"]
    actual = {file.relative_to(package).as_posix(): file_hash(file) for file in files}
    if actual != {name: value for name, value in expected.items()
                  if name.startswith(NAME + "/")}:
        raise ValueError("Skill files differ from the package manifest; installation stopped")
    for entry in ("install.py", "INSTALL.md"):
        if expected.get(entry) != file_hash(package / entry):
            raise ValueError("Package entry differs from manifest: " + entry)
    print(json.dumps({"source": str(source), "destination": str(target),
                      "files": len(files), "mode": "install" if args.install else "plan"},
                     ensure_ascii=True, indent=2))
    if not args.install:
        print("Read-only plan. Add --install to copy into the selected new directory.")
        return 0
    # No exist_ok on the skill directory: an existing destination must never merge.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    for file in files:
        destination = target / file.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(file.read_bytes())
        if file_hash(destination) != actual[file.relative_to(package).as_posix()]:
            raise OSError("Copy verification failed: " + str(destination))
    print("Installed and hash-verified. No settings were modified.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)
