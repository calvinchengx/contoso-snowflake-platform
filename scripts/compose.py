#!/usr/bin/env python3
"""Assemble compose files. Logic lives here so the Makefile survives cmd.exe."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "compose" / ".generated"
FILES = ["compose/docker-compose.yml"]
if os.environ.get("GOVERNANCE", "1") == "1":
    FILES.append("compose/governance.yml")


def sources_dir() -> Path:
    """The contoso-sources checkout this stack pulls its vendors from.

    A SIBLING PATH, and the one place in this repository where that is right:
    the vendors are not a dependency, they are the world outside, mounted into
    containers as bytes rather than imported as code.
    """
    return Path(os.environ.get("SOURCES", ROOT.parent / "contoso-sources")).resolve()


def vendor_fragment() -> Path:
    """Generate the vendor compose fragment from the sources declaration.

    THIS CELL HAD NO SOURCE SYSTEMS AT ALL until now -- it seeded empty silver
    tables and built gold over them. The family's numbers are only comparable
    because every cell pulls the SAME bytes from the SAME pinned simulator, so a
    Snowflake cell without vendors could never produce evidence, only shapes.
    """
    src = sources_dir()
    decl = src / "sources.yaml"
    if not decl.exists():
        sys.exit(
            f"no vendor declaration at {decl}.\n\n"
            f"Clone calvinchengx/contoso-sources beside this repository, or set "
            f"SOURCES=/path/to/contoso-sources."
        )
    data = src / "_data"
    if not data.is_dir() or not any(data.iterdir()):
        sys.exit(
            f"{data} is empty -- the vendors have no bytes to serve.\n\n"
            f"Run `make sources` in {src} first. Without it mokapi does not\n"
            f"fail: it generates bodies from the OpenAPI schema and answers\n"
            f"every request 200, so this pipeline would land invented data."
        )
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / "sources.json"
    out.write_text(
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "sources.py"), str(decl), str(src)],
            check=True, capture_output=True, text=True,
        ).stdout,
        encoding="utf-8",
    )
    return out


def main() -> int:
    args = sys.argv[1:]
    cmd = [
        "docker",
        "compose",
        "--env-file",
        "versions.env",
        "--profile",
        "governance",
    ]
    for f in FILES:
        cmd.extend(["-f", f])
    # The vendors come last, generated from contoso-sources at every
    # invocation, so a vendor added over there is stood up here without an edit.
    cmd.extend(["-f", str(vendor_fragment().relative_to(ROOT))])
    cmd.extend(args)
    env = os.environ.copy()
    env.setdefault("SNOWFLAKE_DATA", str(ROOT / "data"))
    Path(env["SNOWFLAKE_DATA"]).mkdir(parents=True, exist_ok=True)
    os.chmod(env["SNOWFLAKE_DATA"], 0o777)
    # The internal stage, host-side. 0777 for the same reason as data/: the
    # emulator runs as nonroot and has to write the files ingest puts here.
    env.setdefault("SNOWFLAKE_STAGES", str(ROOT / "stages"))
    Path(env["SNOWFLAKE_STAGES"]).mkdir(parents=True, exist_ok=True)
    os.chmod(env["SNOWFLAKE_STAGES"], 0o777)
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
