# contoso-snowflake-platform

Gold-only Contoso consumer for `snowflake-emulator` / a real Snowflake account.
`SNOWFLAKE_TARGET=emulator|real`. SQL runs on DuckDB inside the emulator and
is named `duckdb`.

```sh
make doctor
make up
make verify
```

Apache-2.0.
