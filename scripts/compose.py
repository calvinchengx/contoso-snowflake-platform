#!/usr/bin/env python3
"""Assemble compose files. Logic lives here so the Makefile survives cmd.exe."""

from __future__ import annotations

import json
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
    rc = subprocess.call(cmd, cwd=ROOT, env=env)
    if rc != 0 and args and args[0] == "up":
        rc = tolerate_finished_jobs(cmd[:-len(args)], env, rc)
    return rc


def tolerate_finished_jobs(base: list[str], env: dict, rc: int) -> int:
    """`--wait` calls a finished job a failure. Two of ours finish by design.

    `docker compose up --wait` waits for every service to be running or
    healthy, and a container that has EXITED does not qualify -- even when it
    exited 0, which is exactly what a one-shot job should do. This stack has
    two: `contoso-erp-seed` loads the vendor's database, and `om-migrate`
    migrates OpenMetadata's schema. Both run once and stop.

    So `make up` returned 1 on a stack that had come up correctly. In CI that
    stops the job before `make verify` runs, and the failure is reported
    against a step that never executed rather than the one that misread its
    own success. Measured here: every service healthy, exit 1, and
    `compose-contoso-erp-seed-1 exited (0)` the only complaint.

    The same shape as the Kafka race this repository fixed earlier -- a wait
    condition that does not describe the thing being waited for. So the exit
    code is re-derived from what the containers actually did. A non-zero exit,
    or a service that never ran, is still a failure.
    """
    ps = subprocess.run(base + ["ps", "-a", "--format", "json"],
                        cwd=ROOT, env=env, capture_output=True, text=True)
    if ps.returncode != 0 or not ps.stdout.strip():
        return rc
    bad = []
    for line in ps.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            svc = json.loads(line)
        except json.JSONDecodeError:
            return rc
        state, code = svc.get("State", ""), svc.get("ExitCode", 0)
        if state in ("running", "restarting") or (state == "exited" and code == 0):
            continue
        bad.append(f"{svc.get('Service', '?')}: {state} ({code})")
    if bad:
        print("compose: " + "; ".join(bad))
        return rc
    print("compose: up -- every service is running, or is a job that finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
