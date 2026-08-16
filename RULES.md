# Rules for this codebase

This platform runs against **real Snowflake**. `snowflake-emulator` is one
target it can be pointed at. Gold only — no bronze/silver Spark rewrite.

## 1. Snowflake, not the emulator

| | |
|---|---|
| **Rule** | Every difference between the emulator and a real account lives in the published `snowflake-target` package, selected by `SNOWFLAKE_TARGET=emulator\|real`. |
| **Why** | A localhost URL or a seeded PAT anywhere else is a workaround that ships to production. |
| **Enforced by** | `test_emulator_only_in_target_resolver` |

| | |
|---|---|
| **Rule** | TLS verification is never hardcoded off on the real target. |
| **Why** | Real mode sets `tls_verify=True`. |
| **Enforced by** | snowflake-target unit tests |

| | |
|---|---|
| **Rule** | Warehouse, database, and schema are addressed **by name**. |
| **Why** | Ids never match across emulator and real. |

## 2. The product is installed, never restated

Gold SQL and ODCS contracts come from `contoso-data-product`. This repo wraps them.

## 3. What this platform will not claim

- Bronze / silver Spark
- Time Travel / Streams / Tasks
- Cortex
- “Snowflake SQL compatible”
