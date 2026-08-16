"""Seed silver tables in the warehouse. No Spark bronze/silver claim."""

from __future__ import annotations

from provision import sql
from target import T

STATEMENTS = [
    "CREATE TABLE IF NOT EXISTS silver_customers (customer_id INTEGER, name VARCHAR, email VARCHAR, country VARCHAR, marketing_segment VARCHAR, loyalty_tier VARCHAR)",
    "CREATE TABLE IF NOT EXISTS silver_orders (order_id INTEGER, customer_id INTEGER, product_id INTEGER, order_date DATE, channel VARCHAR, status VARCHAR, currency VARCHAR, quantity INTEGER, unit_price DECIMAL(19,4), amount DECIMAL(19,4))",
    "CREATE TABLE IF NOT EXISTS silver_product_hierarchy (product_id INTEGER, product_name VARCHAR, category VARCHAR, department VARCHAR, segment VARCHAR, list_price_usd DECIMAL(19,4))",
    "CREATE TABLE IF NOT EXISTS silver_fx_daily (currency VARCHAR, rate_date DATE, rate_to_usd DECIMAL(19,6), rate_is_carried INTEGER)",
    "CREATE TABLE IF NOT EXISTS silver_party (party_key VARCHAR, email VARCHAR, pos_customer_id INTEGER, in_pos INTEGER, in_web INTEGER, country VARCHAR, marketing_segment VARCHAR, loyalty_tier VARCHAR)",
    "CREATE TABLE IF NOT EXISTS silver_web_customers (email VARCHAR)",
    "CREATE TABLE IF NOT EXISTS silver_web_order_lines (web_order_id INTEGER, product_id INTEGER, order_date DATE, status VARCHAR, quantity INTEGER, amount DECIMAL(19,4), currency VARCHAR, email VARCHAR)",
]


def main() -> int:
    t = T()
    for s in STATEMENTS:
        out = sql(t, s)
        if not out.get("success"):
            raise SystemExit(out)
    print("seeded silver tables (empty; gold numbers may be a named dialect gap)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
