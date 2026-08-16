"""Point this repository at a specific snowflake-emulator release."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSIONS = ROOT / "versions.env"
TRACKS_THE_RELEASE = ("SNOWFLAKE_EMULATOR_VERSION",)
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")


def set_version(text: str, version: str) -> tuple[str, dict[str, str]]:
    moved = {}
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, old = stripped.partition("=")
        key, old = key.strip(), old.strip()
        if key in TRACKS_THE_RELEASE:
            moved[key] = old
            lines[i] = f"{key}={version}\n"
    return "".join(lines), moved


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: set_release.py <version>   e.g. set_release.py 0.1.0")
    version = sys.argv[1].lstrip("v")
    if not SEMVER.match(version):
        sys.exit(f"not a version: {version!r} — expected something like 0.1.0")
    text = VERSIONS.read_text(encoding="utf-8")
    new, moved = set_version(text, version)
    missing = [k for k in TRACKS_THE_RELEASE if k not in moved]
    if missing:
        sys.exit(f"{VERSIONS.name} has no {', '.join(missing)} to set")
    VERSIONS.write_text(new, encoding="utf-8")
    for key, old in moved.items():
        note = "  (unchanged)" if old == version else ""
        print(f"  {key}: {old} -> {version}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
