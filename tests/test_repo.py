"""Repo-boundary tests. No Docker, no emulator, no product.

Since the split this repository is a PLATFORM: it stands up the stack and runs
whatever product it is pointed at. The tests that read step code moved to
contoso-data-product-snowflake-tasks with the code they describe.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_pins() -> dict[str, str]:
    out = {}
    for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def test_pins_are_immutable():
    pins = read_pins()
    assert "SNOWFLAKE_EMULATOR_VERSION" in pins
    mutable = {"latest", "stable", "main", "edge"}
    for k, v in pins.items():
        assert v.lower() not in mutable, f"{k}={v}"


def test_compose_reads_every_pin():
    composed = "".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "compose").glob("*.yml")
    )
    for k in read_pins():
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


def test_set_release_moves_only_the_emulator_pin():
    mod = load("set_release")
    text = "SNOWFLAKE_EMULATOR_VERSION=0.1.0\nOPENMETADATA_VERSION=1.13.2\n"
    new, moved = mod.set_version(text, "0.2.0")
    assert moved == {"SNOWFLAKE_EMULATOR_VERSION": "0.1.0"}
    assert "SNOWFLAKE_EMULATOR_VERSION=0.2.0" in new
    assert "OPENMETADATA_VERSION=1.13.2" in new


def test_the_platform_holds_no_product():
    """This repository used to contain its own product.

    Thirteen step modules -- ingest through govern -- sat in `platform/`, with
    the dbt profiles beside them. That made this cell's name a half-truth and
    made "a second product can use this platform unchanged" untestable, because
    there was no second thing to point it at.

    The split line is 00-family.md's: a platform holds no Contoso name and no
    product file. The steps live in contoso-data-product-snowflake-tasks.
    """
    assert not (ROOT / "platform").exists(), (
        "a platform/ directory is back -- the product's steps belong in the leaf"
    )
    for gone in ("gold/dbt_project.yml", "gold/profiles.yml", "silver/profiles.yml"):
        assert not (ROOT / gone).exists(), (
            f"{gone} is a product file: dbt runs from the product's directory, "
            f"so a copy here is one nothing reads and everything can diverge from"
        )
    # A DEFAULT NAMING CONTOSO would be the same coupling in one line. The
    # Makefile may name the VENDORS repo -- it consumes one -- but never a
    # product, and not in a variable name either: the stage the product writes
    # to is PRODUCT_STAGE, which says what it is rather than whose it is.
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for line in makefile.splitlines():
        code = line.split("#", 1)[0]
        if "contoso" in code.lower() and "contoso-sources" not in code:
            raise AssertionError(f"the Makefile names a product: {line.strip()!r}")

    # THE MAKEFILE WAS NOT ENOUGH in the Databricks split: a whole dbt PROJECT
    # survived it sitting in gold/, byte-identical to the product's copy and
    # naming `contoso_gold`. A dbt project is a product artefact -- it declares
    # models, materializations and a profile, which are the product's decisions.
    #
    # ./product is exempt: a dbt project appearing THERE is the product being
    # run, not the platform holding one.
    strays = [
        d.relative_to(ROOT).as_posix()
        for d in ROOT.rglob("dbt_project.yml")
        if "product" not in d.relative_to(ROOT).parts[:1] and ".venv" not in d.parts
    ]
    assert not strays, f"a dbt project is still in the platform: {strays}"


def test_the_product_is_supplied_as_a_path():
    """PRODUCT is how the platform learns what to run, and it is a PATH.

    A name would mean this platform could only ever run one product, which is
    the property the split exists to remove.
    """
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^PRODUCT \?= \./product$", makefile, re.M), (
        "PRODUCT must default to the ./product mount point"
    )
    assert "--directory $(PRODUCT)" in makefile, (
        "steps must run in the product's own directory, so dbt uses the "
        "product's lock and outputs land there"
    )


def test_the_platform_declares_no_runtime_dependency():
    """What is left here reaches for nothing outside the standard library.

    The declarations went to the product with the code that imports them, and
    the thirteen advisories fixed in #9 went with them -- they all arrived
    through dbt-snowflake, and dbt now runs from the product's lock. Keeping
    them here would keep a vulnerable tree alive in a lockfile that installs
    nothing.
    """
    proj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "dependencies = []" in proj
    for gone in ("snowflake-target", "contoso-data-product", "dbt-snowflake"):
        for line in proj.splitlines():
            if line.lstrip().startswith("#"):
                continue
            assert gone not in line, f"{gone} is the product's dependency, not this one"


def test_the_stage_the_warehouse_mounts_is_the_one_the_product_writes():
    """The coupling the split exposed, and the reason it is one variable.

    Ingest writes the vendors' bytes into the internal stage; the warehouse --
    a container this platform runs -- reads them back through COPY INTO. While
    both halves lived here they spelled it `<repo>/stages` and agreed by
    accident. If the mount and PRODUCT_STAGE ever name different directories,
    ingest writes where COPY INTO cannot look, and the symptom is an EMPTY
    BRONZE rather than an error.
    """
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    values = {}
    for var in ("PRODUCT_STAGE", "SNOWFLAKE_STAGES"):
        m = re.search(rf"^export {var} := (.+)$", makefile, re.M)
        assert m, f"{var} is not exported -- the product would fall back to its own guess"
        values[var] = m.group(1).strip()
    assert values["PRODUCT_STAGE"] == values["SNOWFLAKE_STAGES"], (
        f"the warehouse mounts {values['SNOWFLAKE_STAGES']} and the product "
        f"writes {values['PRODUCT_STAGE']}"
    )


def test_verify_checks_the_product_pin_before_running_a_step():
    """The two pins live in two repositories now, so the check runs where both exist.

    versions.env pins the emulator IMAGE; the product pins the client WHEEL.
    Nothing in either repository alone can see the pair -- `make verify` is the
    moment it exists, because the platform has been pointed at a product.
    """
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    body = makefile[makefile.index("verify:") :]
    recipe = [ln for ln in body.splitlines()[1:] if ln.startswith("\t")]
    assert recipe, "verify has no recipe"
    assert "check_product_pin.py" in recipe[0], (
        "the pin check must run BEFORE the first step, or the run reports a "
        "client/image mismatch as a failure four steps deep"
    )


def test_check_product_pin_refuses_a_client_from_another_release(tmp_path):
    """Checked against a disagreement, not just against the happy path."""
    script = ROOT / "scripts" / "check_product_pin.py"
    version = read_pins()["SNOWFLAKE_EMULATOR_VERSION"]
    good = (
        "snowflake-target = { url = "
        f'"https://github.com/calvinchengx/snowflake-emulator/releases/download/'
        f'v{version}/snowflake_target-0.1.0-py3-none-any.whl" }}\n'
    )
    stale = good.replace(f"/v{version}/", "/v0.0.1/")

    for name, content, expected in (
        ("agreeing", good, 0),
        ("stale", stale, 1),
        ("silent", "dependencies = []\n", 1),
    ):
        product = tmp_path / name
        product.mkdir()
        (product / "pyproject.toml").write_text(content, encoding="utf-8")
        (product / "uv.lock").write_text(content, encoding="utf-8")
        rc = subprocess.call(
            [sys.executable, str(script), str(product)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert rc == expected, f"{name} product: expected exit {expected}, got {rc}"


def test_the_acceptance_run_checks_out_the_product_it_runs():
    """`make verify` with no PRODUCT would run the empty ./product mount point.

    It would fail at the first step rather than quietly verifying nothing, but
    it would fail for a confusing reason.
    """
    wf = (ROOT / ".github" / "workflows" / "acceptance.yml").read_text(encoding="utf-8")
    for repo in (
        "calvinchengx/contoso-data-product-snowflake-tasks",
        # compose.py hard-requires this checkout to materialise the vendors.
        "calvinchengx/contoso-sources",
    ):
        assert repo in wf, f"the acceptance run does not check out {repo}"
    assert "make verify PRODUCT=../contoso-data-product-snowflake-tasks" in wf


def test_the_acceptance_run_adopts_every_file_the_bump_touches():
    """A half-adopted pin publishes a main that contradicts itself.

    The bump now changes ONE file. pyproject.toml and uv.lock carried the
    client wheel until the split and no longer do -- the wheel is the product's
    pin, which is why check_product_pin.py exists.
    """
    wf = (ROOT / ".github" / "workflows" / "acceptance.yml").read_text(encoding="utf-8")
    adopt = wf[wf.index("Adopt the version this run just verified") :]
    assert adopt.count("versions.env") >= 2, (
        "the adopt step must both TEST and COMMIT versions.env"
    )
    for gone in ("pyproject.toml", "uv.lock"):
        assert gone not in adopt, (
            f"the adopt step commits {gone}, which the bump no longer touches"
        )
