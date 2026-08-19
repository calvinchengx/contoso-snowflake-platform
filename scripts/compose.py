#!/usr/bin/env python3
"""Assemble compose files. Logic lives here so the Makefile survives cmd.exe."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["compose/docker-compose.yml"]
if os.environ.get("GOVERNANCE", "1") == "1":
    FILES.append("compose/governance.yml")


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
