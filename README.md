# snowflake-platform-tasks

Gold-only Contoso consumer for `snowflake-emulator` / a real Snowflake account.
`SNOWFLAKE_TARGET=emulator|real`. SQL runs on DuckDB inside the emulator and
is named `duckdb`.

```sh
make doctor
make up
make verify
```

Apache-2.0.

## Related projects

This is the Snowflake consumer. Its siblings are
[`fabric-platform-notebook-pipelines`](https://github.com/calvinchengx/fabric-platform-notebook-pipelines)
and
[`databricks-platform-jobs`](https://github.com/calvinchengx/databricks-platform-jobs)
— the same Contoso data on different engines — sharing the transforms in
[`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product).

It runs against [`snowflake-emulator`](https://github.com/calvinchengx/snowflake-emulator),
a peer of the [**azure-emulators**](https://github.com/calvinchengx/azure-emulators) family rather than a member of it.
