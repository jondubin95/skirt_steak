# Check query templates

Shapes for the checks in `../SKILL.md`. Confirm names in schema recon, then substitute them for `orders`, `customers`, and `events`. These statements are selects. Run them on a test, sample, or dry-run dataset, or in a read-only session.

DuckDB is the reference dialect. `FILTER` and `information_schema` are used as DuckDB implements them.

Cite a result by the heading name (`join_row_counts`). Report the counts, not key values or row samples.

## schema_tables

```sql
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
ORDER BY table_schema, table_name;
```

## schema_columns

```sql
SELECT
  table_schema,
  table_name,
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
ORDER BY table_name, ordinal_position;
```

## grain

`row_count` and `distinct_order_id` differ when `order_id` is not a key. Nulls are not counted by `COUNT(DISTINCT ...)`.

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(order_id) AS non_null_order_id,
  COUNT(DISTINCT order_id) AS distinct_order_id
FROM orders;
```

## join_key_uniqueness

Run once per side of each join. `keys_with_duplicates` above zero means that side can multiply rows.

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(customer_id) AS non_null_keys,
  COUNT(DISTINCT customer_id) AS distinct_keys
FROM orders;

SELECT COUNT(*) AS keys_with_duplicates
FROM (
  SELECT customer_id
  FROM orders
  WHERE customer_id IS NOT NULL
  GROUP BY customer_id
  HAVING COUNT(*) > 1
) AS duplicate_keys;
```

Repeat both statements for `customers`.

## join_row_counts

Compare `joined_rows` with `left_rows`. A larger joined count is fan-out. A smaller inner-join count is loss. Read `join_key_uniqueness` before attributing the delta.

```sql
SELECT
  (SELECT COUNT(*) FROM orders) AS left_rows,
  (SELECT COUNT(*) FROM customers) AS right_rows,
  (
    SELECT COUNT(*)
    FROM orders AS o
    INNER JOIN customers AS c ON o.customer_id = c.customer_id
  ) AS inner_joined_rows,
  (
    SELECT COUNT(*)
    FROM orders AS o
    LEFT JOIN customers AS c ON o.customer_id = c.customer_id
  ) AS left_joined_rows;
```

## null_prevalence

Add one `COUNT(*) FILTER` line per column the query reads.

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(*) FILTER (WHERE customer_id IS NULL) AS customer_id_nulls,
  COUNT(*) FILTER (WHERE status IS NULL) AS status_nulls,
  COUNT(*) FILTER (WHERE order_total IS NULL) AS order_total_nulls,
  COUNT(*) FILTER (WHERE order_date IS NULL) AS order_date_nulls
FROM orders;
```

## null_filter

`status <> 'canceled'` drops null `status`. `IS DISTINCT FROM` keeps those rows. The difference is the silent drop.

```sql
SELECT
  COUNT(*) FILTER (WHERE status IS NULL) AS null_status,
  COUNT(*) FILTER (WHERE status <> 'canceled') AS kept_by_not_equal,
  COUNT(*) FILTER (WHERE status IS DISTINCT FROM 'canceled') AS kept_by_is_distinct_from
FROM orders;
```

## null_aggregate

`SUM` skips nulls. `non_null_order_total` below `row_count` means the sum is over a smaller population than the table.

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(order_total) AS non_null_order_total,
  SUM(order_total) AS sum_skipping_nulls
FROM orders;
```

## null_join

Collapse the right side to one row per key so fan-out is not counted as a match. `null_keys` are dropped by an inner join. `non_null_unmatched` are dropped because the key is absent on the right.

```sql
WITH customers_one AS (
  SELECT customer_id
  FROM customers
  WHERE customer_id IS NOT NULL
  GROUP BY customer_id
)
SELECT
  COUNT(*) AS left_rows,
  COUNT(*) FILTER (WHERE o.customer_id IS NULL) AS null_keys,
  COUNT(*) FILTER (
    WHERE o.customer_id IS NOT NULL AND c.customer_id IS NULL
  ) AS non_null_unmatched,
  COUNT(*) FILTER (WHERE c.customer_id IS NOT NULL) AS matched
FROM orders AS o
LEFT JOIN customers_one AS c ON o.customer_id = c.customer_id;
```

## filter_range

`COUNT(DISTINCT status)` ignores nulls. The null count is in `null_prevalence`.

```sql
SELECT
  COUNT(*) AS rows_before,
  COUNT(*) FILTER (
    WHERE order_date >= DATE '2024-01-01'
      AND order_date < DATE '2025-01-01'
  ) AS rows_in_half_open_window,
  MIN(order_date) AS min_order_date,
  MAX(order_date) AS max_order_date,
  COUNT(DISTINCT status) AS distinct_status
FROM orders;
```

## filter_drop_split

Classify every row with the same precedence as the predicate. `kept` is the population the filter retains. Any other bucket is a drop. A null bucket the code does not mention is a silent failure. This split includes the status predicate. `rows_in_half_open_window` does not, so the two counts differ by the in-window rows the status predicate removes.

```sql
SELECT
  CASE
    WHEN order_date IS NULL THEN 'null_date'
    WHEN order_date < DATE '2024-01-01' OR order_date >= DATE '2025-01-01' THEN 'outside_window'
    WHEN status IS NULL THEN 'null_status'
    WHEN status = 'canceled' THEN 'canceled'
    ELSE 'kept'
  END AS bucket,
  COUNT(*) AS row_count
FROM orders
GROUP BY 1
ORDER BY 1;
```

## stage_counts

One row per stage. A jump at `joined` is fan-out. A drop at `filtered` must match `filter_drop_split`. SQL `GROUP BY` keeps a group for null keys; count that group on its own.

```sql
WITH filtered AS (
  SELECT *
  FROM orders
  WHERE order_date >= DATE '2024-01-01'
    AND order_date < DATE '2025-01-01'
    AND status <> 'canceled'
),
joined AS (
  SELECT f.order_id, f.customer_id
  FROM filtered AS f
  LEFT JOIN customers AS c ON f.customer_id = c.customer_id
),
aggregated AS (
  SELECT customer_id
  FROM filtered
  GROUP BY customer_id
)
SELECT 'source' AS stage, COUNT(*) AS row_count FROM orders
UNION ALL
SELECT 'filtered', COUNT(*) FROM filtered
UNION ALL
SELECT 'joined', COUNT(*) FROM joined
UNION ALL
SELECT 'aggregated', COUNT(*) FROM aggregated
UNION ALL
SELECT 'aggregated_null_key', COUNT(*)
FROM filtered
WHERE customer_id IS NULL;
```

## duplicate_keys

Counts only. `extra_rows` is how many rows a `SELECT DISTINCT` on the grain would remove.

```sql
SELECT
  COUNT(*) AS duplicate_key_groups,
  COALESCE(SUM(extra_rows_per_key), 0) AS extra_rows
FROM (
  SELECT COUNT(*) - 1 AS extra_rows_per_key
  FROM orders
  GROUP BY order_id
  HAVING COUNT(*) > 1
) AS duplicate_keys;
```

Run again on the output grain.

## date_bounds

Record the session time zone next to this result. `CAST(event_at AS DATE)` uses that zone. Min and max are cast to `VARCHAR` so a Python fetch does not need a timezone package.

```sql
SELECT CURRENT_SETTING('TimeZone') AS session_time_zone;

SELECT
  CAST(MIN(event_at) AS VARCHAR) AS min_event_at,
  CAST(MAX(event_at) AS VARCHAR) AS max_event_at,
  COUNT(*) AS row_count,
  COUNT(*) FILTER (WHERE event_at IS NULL) AS null_event_at
FROM events;
```

## date_boundary_mismatch

`half_open_utc` is `[2024-01-01, 2024-02-01)`. `inclusive_utc_date` includes the whole end date when the cast is in UTC. `exact_end_instant` is the row an inclusive end timestamp would add. The `SET` applies for the rest of the session. Record the zone, and set it again before a later cast that should use a different zone.

```sql
SET TimeZone = 'UTC';

SELECT
  COUNT(*) FILTER (
    WHERE event_at >= TIMESTAMPTZ '2024-01-01 00:00:00+00'
      AND event_at < TIMESTAMPTZ '2024-02-01 00:00:00+00'
  ) AS half_open_utc,
  COUNT(*) FILTER (
    WHERE CAST(event_at AS DATE) BETWEEN DATE '2024-01-01' AND DATE '2024-01-31'
  ) AS inclusive_utc_date,
  COUNT(*) FILTER (
    WHERE event_at = TIMESTAMPTZ '2024-02-01 00:00:00+00'
  ) AS exact_end_instant
FROM events;
```

## date_civil_day

Same instant, two civil days. A difference is a timezone shift. Use a day the sample actually contains. Include a DST transition day when one is present.

```sql
SELECT
  COUNT(*) FILTER (
    WHERE (event_at AT TIME ZONE 'UTC')::DATE = DATE '2024-03-10'
  ) AS civil_day_utc,
  COUNT(*) FILTER (
    WHERE (event_at AT TIME ZONE 'America/New_York')::DATE = DATE '2024-03-10'
  ) AS civil_day_new_york
FROM events;
```

## pandas_frame

In-memory check against the same read-only connection. `validate='m:1'` raises when `customers.customer_id` is not unique; record the exception. `duplicated` sums to the extra rows, not the groups. `groupby(..., dropna=False)` keeps null keys.

```python
import duckdb

con = duckdb.connect("data/sample.duckdb", read_only=True)
orders = con.execute("SELECT * FROM orders").fetchdf()
customers = con.execute("SELECT * FROM customers").fetchdf()

rows_before = len(orders)
merged = orders.merge(
    customers,
    on="customer_id",
    how="left",
    validate="m:1",
)
rows_after = len(merged)
null_order_total = int(orders["order_total"].isna().sum())
extra_duplicate_rows = int(orders.duplicated(subset=["order_id"]).sum())
status_counts = orders.groupby("status", dropna=False).size()
```
