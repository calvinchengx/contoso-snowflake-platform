"""Landing to bronze, by COPY INTO from the internal stage.

BRONZE IS SQL HERE, not Spark. That is the whole point of this cell: the other
runtimes hand their bronze to an engine that speaks DataFrames, and Snowflake
does not have one — it has a warehouse and a stage. `COPY INTO` reading a prefix
of staged parts is what a Snowflake team writes, and it is a different shape of
the same step rather than a port of somebody else's.

THE COLUMNS ARE THE VENDOR'S, in the order the vendor serves them. A CSV copy is
positional, so a column list that drifts from the export does not fail — it
loads the right bytes into the wrong columns, which is worse. The header row the
vendor sends is the authority, and `_assert_header` checks it before any copy.
"""

from __future__ import annotations

import pathlib

from provision import sql
from target import T

STAGE = pathlib.Path(__file__).resolve().parent.parent / "stages"

# The POS customer export: 101 columns, and the six the product actually reads.
# Declared as the vendor's header rather than the product's needs, because
# bronze is what arrived -- narrowing belongs in silver, where it is visible.
POS_CUSTOMERS = "contoso_pos_customers"


def _header(subdir: str) -> list[str]:
    parts = sorted((STAGE / subdir).glob("*.csv"))
    if not parts:
        raise SystemExit(
            f"nothing staged under {STAGE / subdir} — run ingest first."
        )
    with parts[0].open(encoding="utf-8") as fh:
        return fh.readline().strip().split(",")


def main() -> int:
    t = T()
    cols = _header(POS_CUSTOMERS)
    assert len(cols) > 1, f"the vendor's header did not parse: {cols[:3]}"

    ddl = ", ".join(f'"{c}" VARCHAR' for c in cols)
    out = sql(t, f"CREATE OR REPLACE TABLE bronze_pos_customers ({ddl})")
    if not out.get("success"):
        raise SystemExit(out)

    # ONE COPY PER PART, because this engine does not read a prefix. Snowflake
    # itself does -- `COPY INTO t FROM @~/dir/` is the ordinary form, and the
    # vendor pages precisely so that a directory of parts is what arrives. The
    # emulator answers a prefix with `ok` and loads nothing, and a glob with an
    # error (measured; noted on snowflake-emulator#20). Naming each part is the
    # form that works, and the loop is what a real prefix would have done.
    parts = sorted((STAGE / POS_CUSTOMERS).glob("*.csv"))
    for part in parts:
        out = sql(
            t,
            f"COPY INTO bronze_pos_customers FROM '@~/{POS_CUSTOMERS}/{part.name}' "
            f"FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1)",
        )
        if not out.get("success"):
            raise SystemExit(out)

    out = sql(t, "SELECT count(*) AS n FROM bronze_pos_customers")
    rows = int((out.get("data") or {}).get("rowset", [["0"]])[0][0])

    # COPY INTO REPORTS `ok` WHETHER OR NOT IT LOADED ANYTHING -- measured, and
    # filed as snowflake-emulator#20 for the JSON and PARQUET formats, which
    # load nothing and say ok. So the row count is the only evidence that this
    # step did what it claims, and an empty bronze fails here rather than
    # surfacing as a gold star full of truthful-looking zeros.
    if rows == 0:
        raise SystemExit(
            "COPY INTO reported success and bronze_pos_customers is empty — "
            "the stage has parts but nothing loaded."
        )
    print(
        f"bronze: {rows:,} POS customer rows x {len(cols)} columns, "
        f"by COPY INTO over {len(parts)} staged part(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
