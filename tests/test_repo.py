"""Repo-boundary tests. No Docker, no emulator."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_pins_are_immutable():
    pins = {}
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pins[k.strip()] = v.strip()
    assert "SNOWFLAKE_EMULATOR_VERSION" in pins
    mutable = {"latest", "stable", "main", "edge"}
    for k, v in pins.items():
        assert v.lower() not in mutable, f"{k}={v}"


def test_compose_reads_every_pin():
    composed = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "compose").glob("*.yml"))
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k = line.split("=", 1)[0].strip()
            assert "${" + k in composed, k


def test_makefile_survives_cmd_exe():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for bad in (" | ", " && ", " `", " rm "):
        for line in text.splitlines():
            if line.startswith("#") or line.startswith("ifeq") or line.startswith("  SHELL"):
                continue
            if ":" in line and not line.startswith("\t") and not line.startswith(" "):
                continue
            if line.startswith("\t"):
                assert bad not in line, f"cmd.exe-unsafe recipe: {line!r}"


def test_emulator_only_in_target_resolver():
    allowed = {
        ROOT / "platform" / "target.py",
        ROOT / "platform" / "gold.py",
        ROOT / "platform" / "govern.py",
        ROOT / "gold" / "profiles.yml",
    }
    hits = []
    for p in (ROOT / "platform").glob("*.py"):
        if p in allowed:
            continue
        text = p.read_text(encoding="utf-8")
        if "127.0.0.1:8448" in text or "admin.pat" in text:
            hits.append(p.name)
    assert hits == []


def test_product_is_imported_not_restated():
    gold = (ROOT / "platform" / "gold.py").read_text(encoding="utf-8")
    assert "from contoso_product import gold_dir" in gold
    assert "decimal(19,4)" not in gold


def test_set_release_moves_only_the_emulator_pin(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "set_release", ROOT / "scripts" / "set_release.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = "SNOWFLAKE_EMULATOR_VERSION=0.1.0\nOPENMETADATA_VERSION=1.13.2\n"
    new, moved = mod.set_version(text, "0.2.0")
    assert moved == {"SNOWFLAKE_EMULATOR_VERSION": "0.1.0"}
    assert "SNOWFLAKE_EMULATOR_VERSION=0.2.0" in new
    assert "OPENMETADATA_VERSION=1.13.2" in new


def test_bronze_is_sql_not_spark():
    """This cell builds bronze with SQL, because Snowflake has no DataFrames.

    The test used to assert there was no bronze.py at all, which was an honest
    statement of a cell that seeded empty silver tables and built gold over
    them. There is a bronze now, and the invariant that actually matters
    survived the change: it is `COPY INTO` from a stage — what a Snowflake team
    writes — and not a Spark session smuggled in to make this cell look like the
    others.
    """
    bronze = ROOT / "platform" / "bronze.py"
    assert bronze.exists(), "bronze.py is gone — this cell landed one deliberately"
    src = bronze.read_text(encoding="utf-8")
    assert "COPY INTO" in src, "bronze must load through the stage"
    for banned in ("pyspark", "SparkSession", "databricks.connect"):
        assert banned not in src, f"bronze reaches for Spark ({banned})"


def test_no_dependency_comes_from_a_sibling_checkout():
    """This repository must clone and build on its own.

    Both `snowflake-target` and `contoso-data-product` used to resolve through
    `path = "../…"`. That is invisible to everyone who already has the siblings
    on disk and fails for everyone who does not — which is the whole population
    this repository claims to serve, and DoD item 1 in the family plan.

    It had a second cost that took a while to surface: with no version pin,
    this was the one consumer a core release could not reach. v0.1.1 and v0.2.0
    both went past it without anything to bump and without anything failing.
    """
    proj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in proj.splitlines()
        if "path = " in line and "../" in line and not line.lstrip().startswith("#")
    ]
    assert not offenders, (
        "a dependency resolves from a sibling checkout, so a lone clone cannot "
        "build: " + str(offenders)
    )


def test_the_target_wheel_matches_the_pinned_release():
    """The client wheel and the emulator image come from the SAME release.

    A workspace binary and a client that disagree about the contract is the one
    mismatch a consumer repository exists to notice, and putting the version in
    two files is how that disagreement arrives unannounced.
    """
    pins = {}
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pins[k.strip()] = v.strip()
    version = pins["SNOWFLAKE_EMULATOR_VERSION"]
    proj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    expected = f"snowflake-emulator/releases/download/v{version}/"
    assert expected in proj, (
        f"the snowflake-target wheel does not come from the pinned release "
        f"v{version}"
    )


def test_the_locked_wheel_matches_the_pinned_release():
    """The LOCKFILE is what decides which client actually runs.

    test_the_target_wheel_matches_the_pinned_release checks pyproject.toml,
    and that is the declaration. It is not what gets installed: every make
    target runs `uv run --frozen`, and --frozen resolves from uv.lock without
    reading pyproject.toml at all. So a bump that moves versions.env and
    pyproject.toml but not the lock leaves the pin pointing one way and the
    installed client pointing the other, with nothing between them.
    """
    pins = {}
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pins[k.strip()] = v.strip()
    version = pins["SNOWFLAKE_EMULATOR_VERSION"]

    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    stale = [
        line.strip()
        for line in lock.splitlines()
        if "snowflake-emulator/releases/download/" in line
        and f"/download/v{version}/" not in line
    ]
    assert not stale, (
        f"uv.lock still installs snowflake-target from a release other than "
        f"the pinned v{version}. Run `python scripts/set_release.py {version}` "
        f"AND `uv lock` -- the lockfile is what --frozen installs.\n  "
        + "\n  ".join(stale)
    )


def test_set_release_moves_the_wheel_as_well_as_the_pin():
    """Moving versions.env alone publishes a main that fails its own test.

    set_release.py used to touch versions.env only, while pyproject.toml
    carried the wheel URL and test_the_target_wheel_matches_the_pinned_release
    asserted the two agree. So the script's own output broke the suite.
    """
    src = (ROOT / "scripts" / "set_release.py").read_text(encoding="utf-8")
    assert "WHEEL_TAG" in src and "PYPROJECT" in src, (
        "set_release.py must move the snowflake-target wheel URL as well as "
        "SNOWFLAKE_EMULATOR_VERSION, or it leaves the repository failing "
        "test_the_target_wheel_matches_the_pinned_release"
    )


def test_the_acceptance_run_adopts_every_file_the_bump_touches():
    """A half-adopted pin publishes a main that contradicts itself.

    The adopt step commits what the bump changed. The bump changes
    versions.env and pyproject.toml, and `uv lock` then changes uv.lock.
    Commit only the first and main carries a pin the other two deny.
    """
    wf = (ROOT / ".github" / "workflows" / "acceptance.yml").read_text(encoding="utf-8")
    adopt = wf[wf.index("Adopt the version this run just verified") :]
    for name in ("versions.env", "pyproject.toml", "uv.lock"):
        assert adopt.count(name) >= 2, (
            f"the adopt step must both TEST and COMMIT {name}; a file left out "
            f"of either half is a pin that main contradicts"
        )
    assert "uv lock" in wf, (
        "the dispatch must refresh the lockfile after set_release.py, or the "
        "run verifies the new image against the client the lock still names"
    )
