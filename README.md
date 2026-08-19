# snowflake-platform-tasks

The **platform** half of the Snowflake · Snowflake Tasks cell: it stands up
`snowflake-emulator` (or points at a real Snowflake account), the four Contoso
vendors and OpenMetadata, then runs whatever product it is pointed at.

It holds no product. The steps live in
[`contoso-data-product-snowflake-tasks`](https://github.com/calvinchengx/contoso-data-product-snowflake-tasks).

```sh
make doctor
make up    PRODUCT=../contoso-data-product-snowflake-tasks
make verify PRODUCT=../contoso-data-product-snowflake-tasks
make down  PRODUCT=../contoso-data-product-snowflake-tasks
```

`PRODUCT` is a **path**, not a name — this repository contains no product
identifier, which is what makes "a second product can use this platform
unchanged" a fact rather than an aspiration. `./product` is an empty, gitignored
mount point if you prefer to clone or symlink one there.

`SNOWFLAKE_TARGET=emulator|real`. Inside the emulator, SQL runs on DuckDB.

## What crosses the boundary

A product does not reach into a platform. Exactly two things are handed over:

| | |
|---|---|
| `make token` | copies `data/admin.pat` into the product. The emulator's data directory also holds `warehouse.duckdb`, and that stays here |
| `PRODUCT_STAGE` | the internal stage. Ingest writes the vendors' bytes there; the warehouse — a container this platform runs — reads them back through `COPY INTO`. The mount and the variable are the same value, so they cannot drift |

## The pin the platform cannot see

`versions.env` pins the emulator **image**; the product pins the client
**wheel**. Since the split those live in two repositories, and nothing in either
one alone can see the pair — so `make verify` runs
`scripts/check_product_pin.py` before any step and refuses when they disagree.

A release therefore needs **two** bumps. Forgetting the second one fails the
acceptance run loudly, which is preferable to verifying a client and an image
that no consumer will ever have together.

## Related projects

Its leaf is
[`contoso-data-product-snowflake-tasks`](https://github.com/calvinchengx/contoso-data-product-snowflake-tasks).
Its sibling platforms are
[`fabric-platform-notebook-pipelines`](https://github.com/calvinchengx/fabric-platform-notebook-pipelines)
and
[`databricks-platform-jobs`](https://github.com/calvinchengx/databricks-platform-jobs),
which made this same split first. The family layout is in
[`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product/blob/main/docs/00-family.md).

Apache-2.0.
