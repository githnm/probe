"""Build the example DuckDB database with orders and customer_addresses."""

import os

import duckdb

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.duckdb")


def seed(path: str = DB_PATH) -> None:
    if os.path.exists(path):
        os.remove(path)

    conn = duckdb.connect(path)
    conn.execute("""
        CREATE TABLE orders (
            order_id   INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount     DECIMAL(10, 2) NOT NULL
        )
    """)
    conn.execute("""
        INSERT INTO orders VALUES
            (1, 100, 50.00),
            (2, 100, 75.00),
            (3, 200, 120.00),
            (4, 300, 30.00),
            (5, 200, 200.00)
    """)

    conn.execute("""
        CREATE TABLE customer_addresses (
            customer_id INTEGER NOT NULL,
            address_type TEXT NOT NULL,
            city TEXT NOT NULL
        )
    """)
    conn.execute("""
        INSERT INTO customer_addresses VALUES
            (100, 'billing',  'New York'),
            (100, 'shipping', 'Boston'),
            (200, 'billing',  'Chicago'),
            (200, 'shipping', 'Chicago'),
            (200, 'warehouse','Denver'),
            (300, 'billing',  'Seattle')
    """)

    conn.close()
    print(f"Seeded {path}")


if __name__ == "__main__":
    seed()
