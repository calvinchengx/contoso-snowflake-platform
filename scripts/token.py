"""Put the workspace credential where the product reads it.

A PRODUCT DOES NOT REACH INTO A PLATFORM. Before the split the steps and the
emulator's data directory sat in one repository, so `target.py` read
`<repo>/data/admin.pat` and the coupling was invisible. It is a coupling all
the same: that directory also holds warehouse.duckdb -- the engine's storage --
and belongs to whoever runs the container.

So only the credential crosses, and it is handed over rather than reached for.
The product's own `data/` holds this file and nothing else, which is why
`target.py` needed no change: it still reads `<product>/data/admin.pat`.
"""

from __future__ import annotations

import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: token.py <product-path>", file=sys.stderr)
        return 2
    product = pathlib.Path(sys.argv[1]).resolve()
    src = ROOT / "data" / "admin.pat"
    if not src.is_file():
        print(
            f"no workspace credential at {src} -- run `make up` first, and give "
            f"the emulator long enough to write it",
            file=sys.stderr,
        )
        return 1
    if not product.is_dir():
        print(f"no product at {product}", file=sys.stderr)
        return 1
    dest = product / "data" / "admin.pat"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    # An empty PAT authenticates nothing and fails four steps later, as a
    # connection error rather than as a missing credential.
    if dest.stat().st_size == 0:
        print(f"the credential copied to {dest} is empty", file=sys.stderr)
        return 1
    print(f"platform: workspace token -> {product.name}/data/admin.pat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
