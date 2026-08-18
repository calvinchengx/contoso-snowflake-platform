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


def test_gold_only_no_spark():
    for name in ("bronze.py", "silver.py"):
        assert not (ROOT / "platform" / name).exists()


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
