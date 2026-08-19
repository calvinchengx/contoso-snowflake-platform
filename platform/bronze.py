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

import csv
import pathlib

from provision import sql
from target import T

STAGE = pathlib.Path(__file__).resolve().parent.parent / "stages"

# The POS customer export: 101 columns, and the six the product actually reads.
# Declared as the vendor's header rather than the product's needs, because
# bronze is what arrived -- narrowing belongs in silver, where it is visible.
# Every staged feed, and the shape it landed in. `text` means the vendor's
# documents ride in as one JSON string per row and silver parses them -- see
# ingest_web for why that is the ordinary Snowflake pattern rather than a dodge.
FEEDS = [
    ("bronze_pos_customers", "contoso_pos_customers", "header"),
    ("bronze_pos_orders", "contoso_pos_orders", "text"),
    ("bronze_web_customers", "contoso_web_customers", "text"),
    ("bronze_web_products", "contoso_web_products", "text"),
    ("bronze_web_orders", "contoso_web_orders", "text"),
    ("bronze_product_hierarchy", "contoso_reference_product_hierarchy", "header"),
    ("bronze_fx_rates", "contoso_reference_fx_rates", "header"),
    ("bronze_erp_changes", "contoso_erp_changes", "header"),
]


def _header(subdir: str) -> list[str]:
    parts = sorted((STAGE / subdir).glob("*.csv"))
    if not parts:
        raise SystemExit(
            f"nothing staged under {STAGE / subdir} — run ingest first."
        )
    # PARSED AS CSV, not split on commas. The JSON-text feeds are written
    # QUOTE_ALL, so their header arrives as `"doc"` and a naive split keeps the
    # quotes -- which then fails a comparison against the column name it IS.
    with parts[0].open(encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def _load(t, table: str, subdir: str, shape: str) -> int:
    cols = _header(subdir)
    assert len(cols) >= 1, f"{subdir}: the header did not parse: {cols[:3]}"
    if shape == "text" and cols != ["doc"]:
        raise SystemExit(f"{subdir}: expected a single `doc` column, got {cols[:3]}")

    ddl = ", ".join(f'"{c}" VARCHAR' for c in cols)
    out = sql(t, f"CREATE OR REPLACE TABLE {table} ({ddl})")
    if not out.get("success"):
        raise SystemExit(out)

    # ONE COPY PER PART, because this engine does not read a prefix. Snowflake
    # itself does -- `COPY INTO t FROM @~/dir/` is the ordinary form, and the
    # vendor pages precisely so that a directory of parts is what arrives. The
    # emulator answers a prefix with `ok` and loads nothing, and a glob with an
    # error (measured; noted on snowflake-emulator#20). Naming each part is the
    # form that works, and the loop is what a real prefix would have done.
    parts = sorted((STAGE / subdir).glob("*.csv"))
    for part in parts:
        out = sql(
            t,
            f"COPY INTO {table} FROM '@~/{subdir}/{part.name}' "
            f"FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1)",
        )
        if not out.get("success"):
            raise SystemExit(out)

    out = sql(t, f"SELECT count(*) AS n FROM {table}")
    rows = int((out.get("data") or {}).get("rowset", [["0"]])[0][0])

    # COPY INTO REPORTS `ok` WHETHER OR NOT IT LOADED ANYTHING -- measured, and
    # filed as snowflake-emulator#20 for the JSON and PARQUET formats, which
    # load nothing and say ok. So the row count is the only evidence that this
    # step did what it claims, and an empty bronze fails here rather than
    # surfacing as a gold star full of truthful-looking zeros.
    if rows == 0:
        raise SystemExit(
            f"COPY INTO reported success and {table} is empty — "
            f"{len(parts)} part(s) staged under {subdir} and nothing loaded."
        )
    print(f"  {table:26} {rows:>8,} rows x {len(cols):>3} col(s), {len(parts)} part(s)")
    return rows


def main() -> int:
    t = T()
    total = 0
    for table, subdir, shape in FEEDS:
        total += _load(t, table, subdir, shape)
    print(f"bronze: {total:,} rows across {len(FEEDS)} tables, by COPY INTO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
