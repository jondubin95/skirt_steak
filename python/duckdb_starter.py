"""
DuckDB Starter Script
=====================
Learn the basics of DuckDB for local SQL analysis.

Installation:
    pip install duckdb pandas

Usage:
    python duckdb_starter.py
"""

import duckdb
import pandas as pd
from pathlib import Path

# ============================================================================
# 1. Connect to DuckDB (creates file if it doesn't exist)
# ============================================================================
db_path = Path(__file__).parent.parent / "data" / "skirt_steak.duckdb"
db_path.parent.mkdir(exist_ok=True)

# Connect to database (persistent file)
conn = duckdb.connect(str(db_path))
print(f"✓ Connected to DuckDB: {db_path}\n")


# ============================================================================
# 2. Create Sample Tables
# ============================================================================
print("Creating sample tables...")

# Create a simple products table
conn.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name VARCHAR,
        price DECIMAL(10, 2),
        category VARCHAR
    )
""")

# Insert sample data
conn.execute("""
    INSERT INTO products VALUES
    (1, 'Ribeye Steak', 24.99, 'Beef'),
    (2, 'Skirt Steak', 16.99, 'Beef'),
    (3, 'NY Strip', 22.99, 'Beef'),
    (4, 'Salmon Fillet', 18.99, 'Fish'),
    (5, 'Chicken Breast', 12.99, 'Poultry')
""")

print("✓ Created products table\n")


# ============================================================================
# 3. Query and View Results
# ============================================================================
print("Running queries...\n")

# Simple SELECT
print("--- All Products ---")
result = conn.execute("SELECT * FROM products").fetchall()
for row in result:
    print(row)

print("\n--- Products by Category ---")
result = conn.execute("""
    SELECT category, COUNT(*) as count, AVG(price) as avg_price
    FROM products
    GROUP BY category
    ORDER BY avg_price DESC
""").fetchall()
for row in result:
    print(f"{row[0]}: {row[1]} items, avg ${row[2]:.2f}")


# ============================================================================
# 4. Convert to Pandas (great for exploration)
# ============================================================================
print("\n--- As Pandas DataFrame ---")
df = conn.execute("SELECT * FROM products WHERE price > 15").df()
print(df)
print(f"\nDataFrame shape: {df.shape}")
print(f"Average price: ${df['price'].mean():.2f}")


# ============================================================================
# 5. Read/Write CSV
# ============================================================================
csv_path = Path(__file__).parent.parent / "data" / "products.csv"
csv_path.parent.mkdir(exist_ok=True)

# Export to CSV
conn.execute(f"COPY products TO '{csv_path}' WITH (FORMAT CSV, HEADER)")
print(f"\n✓ Exported to CSV: {csv_path}")

# Read CSV back (creates new table)
conn.execute(f"""
    CREATE TABLE products_from_csv AS
    SELECT * FROM read_csv_auto('{csv_path}')
""")
print("✓ Read CSV back into DuckDB")


# ============================================================================
# 6. Performance: Query on Large Data
# ============================================================================
print("\n--- Performance Test ---")
# Create a larger table for testing
conn.execute("""
    CREATE TABLE IF NOT EXISTS orders AS
    SELECT 
        range(1, 10001) as order_id,
        (range(1, 10001) % 5) + 1 as product_id,
        RANDOM() * 100 as quantity
    FROM range(10000)
""")

# Query it
result = conn.execute("""
    SELECT p.name, COUNT(*) as order_count, SUM(o.quantity) as total_qty
    FROM orders o
    JOIN products p ON o.product_id = p.id
    GROUP BY p.name
    ORDER BY order_count DESC
""").df()

print(result)
print(f"\n✓ Queried 10,000 orders instantly!")


# ============================================================================
# 7. Cleanup (optional)
# ============================================================================
# conn.close()  # Uncomment to close connection
print("\n✓ DuckDB starter complete! Database saved to:", db_path)
