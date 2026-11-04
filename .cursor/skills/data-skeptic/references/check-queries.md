# Check query templates

Shapes for the checks in `../SKILL.md`. One statement per fence. DuckDB dialect: `FILTER` and `information_schema`.

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

`row_count` and `distinct_order_id` differ when `order_id` is not a key. `COUNT(DISTINCT ...)` ignores nulls, so a column named `id` is not unique until these counts say so.

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(order_id) AS non_null_order_id,
  COUNT(DISTINCT order_id) AS distinct_order_id
FROM orders;
```

## join_key_counts

Run once per side. `keys_with_duplicates` is how many keys occur more than once. `row_count` above `distinct_keys` means that side can multiply rows.

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(customer_id) AS non_null_keys,
  COUNT(DISTINCT customer_id) AS distinct_keys,
  (
    SELECT COUNT(*)
    FROM (
      SELECT customer_id
      FROM orders
      WHERE customer_id IS NOT NULL
      GROUP BY customer_id
      HAVING COUNT(*) > 1
    ) AS duplicate_keys
  ) AS keys_with_duplicates
FROM orders;
```

## join_row_counts

A joined count above the preserved side is fan-out. A smaller inner join is loss. Report them separately, and read `join_key_counts` before attributing the delta.

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

`status <> '<excluded_status>'` drops null `status`. `IS DISTINCT FROM` keeps those rows. The difference is the silent drop. The `CASE` errors when `<excluded_status>` is still a placeholder.

```sql
SELECT
  COUNT(*) FILTER (WHERE status IS NULL) AS null_status,
  COUNT(*) FILTER (WHERE status <> '<excluded_status>') AS kept_by_not_equal,
  COUNT(*) FILTER (WHERE status IS DISTINCT FROM '<excluded_status>') AS kept_by_is_distinct_from
FROM orders
WHERE (CASE WHEN '<excluded_status>' LIKE '%<%' THEN error('unfilled placeholder') ELSE 1 END) = 1;
```

## null_aggregate

`SUM` skips nulls. `non_null_order_total` below `row_count` means the sum covers a smaller population.

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(order_total) AS non_null_order_total,
  SUM(order_total) AS sum_skipping_nulls
FROM orders;
```

## null_join

The right side is one row per key so fan-out is not counted as a match. `null_keys` are dropped by an inner join. `non_null_unmatched` are absent on the right.

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

`kept` is the same predicate as `filter_drop_split`. `COUNT(DISTINCT status)` ignores nulls.

```sql
WITH tagged AS (
  SELECT
    *,
    (
      order_date IS NOT NULL
      AND order_date >= DATE '<window_start>'
      AND order_date < DATE '<window_end>'
      AND status IS DISTINCT FROM '<excluded_status>'
    ) AS kept
  FROM orders
)
SELECT
  COUNT(*) AS rows_before,
  COUNT(*) FILTER (WHERE kept) AS rows_after,
  MIN(order_date) AS min_order_date_before,
  MAX(order_date) AS max_order_date_before,
  MIN(order_date) FILTER (WHERE kept) AS min_order_date_after,
  MAX(order_date) FILTER (WHERE kept) AS max_order_date_after,
  COUNT(DISTINCT status) AS distinct_status_before,
  COUNT(DISTINCT status) FILTER (WHERE kept) AS distinct_status_after
FROM tagged;
```

## filter_drop_split

Same `kept` predicate as `filter_range`. A null bucket the predicate does not mention is a silent failure. A row dropped for two reasons counts once, in the first matching `CASE` branch. Reorder that `CASE` for the cause being checked. The counts still sum to the source row count.

```sql
SELECT
  CASE
    WHEN order_date IS NULL THEN 'null_date'
    WHEN order_date < DATE '<window_start>'
      OR order_date >= DATE '<window_end>' THEN 'outside_window'
    WHEN status IS NOT DISTINCT FROM '<excluded_status>' THEN 'excluded'
    ELSE 'kept'
  END AS bucket,
  COUNT(*) AS row_count
FROM orders
GROUP BY 1
ORDER BY 1;
```

## stage_counts

One row per stage, in pipeline order, using the `kept` predicate. Dedupe is one row per grain key. The aggregate reads `joined`, so fan-out shows in `sum_order_total`. `aggregated_null_group` counts groups with a null key, not null-key rows.

```sql
WITH filtered AS (
  SELECT *
  FROM orders
  WHERE order_date IS NOT NULL
    AND order_date >= DATE '<window_start>'
    AND order_date < DATE '<window_end>'
    AND status IS DISTINCT FROM '<excluded_status>'
),
joined AS (
  SELECT f.order_id, f.customer_id, f.order_total
  FROM filtered AS f
  LEFT JOIN customers AS c ON f.customer_id = c.customer_id
),
deduped AS (
  SELECT order_id, MAX(order_total) AS order_total
  FROM joined
  GROUP BY order_id
),
aggregated AS (
  SELECT customer_id, SUM(order_total) AS order_total
  FROM joined
  GROUP BY customer_id
)
SELECT 'source' AS stage, COUNT(*) AS row_count, SUM(order_total) AS sum_order_total FROM orders
UNION ALL
SELECT 'filtered', COUNT(*), SUM(order_total) FROM filtered
UNION ALL
SELECT 'joined', COUNT(*), SUM(order_total) FROM joined
UNION ALL
SELECT 'deduped', COUNT(*), SUM(order_total) FROM deduped
UNION ALL
SELECT 'aggregated', COUNT(*), SUM(order_total) FROM aggregated
UNION ALL
SELECT 'aggregated_null_group', COUNT(*), SUM(order_total)
FROM aggregated
WHERE customer_id IS NULL;
```

## duplicate_keys

`extra_rows` is how many rows a `SELECT DISTINCT` on the grain would remove.

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

## session_time_zone

`CAST(event_at AS DATE)` uses this zone.

```sql
SELECT CURRENT_SETTING('TimeZone') AS session_time_zone;
```

## date_bounds

Min and max are `VARCHAR` so a Python fetch does not need a timezone package.

```sql
SELECT
  CAST(MIN(event_at) AS VARCHAR) AS min_event_at,
  CAST(MAX(event_at) AS VARCHAR) AS max_event_at,
  COUNT(*) AS row_count,
  COUNT(*) FILTER (WHERE event_at IS NULL) AS null_event_at
FROM events;
```

## set_session_time_zone

Sets the zone for later date casts in this session. Set it again before a cast that should use a different zone.

```sql
SET TimeZone = '<session_zone>';
```

## date_boundary_mismatch

`half_open` is `[<range_start>, <range_end>)`. `inclusive_date` is `<inclusive_start>` through `<inclusive_end>` in the session zone. `exact_end_instant` is the row an inclusive end timestamp would add.

```sql
SELECT
  COUNT(*) FILTER (
    WHERE event_at >= TIMESTAMPTZ '<range_start>'
      AND event_at < TIMESTAMPTZ '<range_end>'
  ) AS half_open,
  COUNT(*) FILTER (
    WHERE CAST(event_at AS DATE) BETWEEN DATE '<inclusive_start>' AND DATE '<inclusive_end>'
  ) AS inclusive_date,
  COUNT(*) FILTER (
    WHERE event_at = TIMESTAMPTZ '<boundary_instant>'
  ) AS exact_end_instant
FROM events;
```

## date_civil_day

Same instant, two civil days. A difference is a timezone shift. Use a day the sample contains, and a DST day when one is present.

```sql
SELECT
  COUNT(*) FILTER (
    WHERE (event_at AT TIME ZONE '<zone_a>')::DATE = DATE '<civil_day>'
  ) AS civil_day_zone_a,
  COUNT(*) FILTER (
    WHERE (event_at AT TIME ZONE '<zone_b>')::DATE = DATE '<civil_day>'
  ) AS civil_day_zone_b
FROM events;
```

## pandas_frame

Same read-only connection. `validate='m:1'` raises when the right-hand key is not unique; record the exception. `duplicated` sums to the extra rows, not the groups. The default `merge` is an inner join, and the default `groupby` drops null keys.

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

## control_total_tieout

Count tolerance defaults to zero.

```sql
WITH anchor AS (
  SELECT <grain_key> AS grain_key, <measure> AS measure FROM <anchor_table>
),
output AS (
  SELECT <grain_key> AS grain_key, <measure> AS measure FROM <output_table>
)
SELECT
  (SELECT COUNT(*) FROM output) - (SELECT COUNT(*) FROM anchor) AS count_variance,
  ROUND(100.0 * ((SELECT COUNT(*) FROM output) - (SELECT COUNT(*) FROM anchor)) / NULLIF((SELECT COUNT(*) FROM anchor), 0), 2) AS count_variance_pct,
  (SELECT SUM(measure) FROM output) - (SELECT SUM(measure) FROM anchor) AS measure_variance,
  (SELECT COUNT(DISTINCT grain_key) FROM output) - (SELECT COUNT(DISTINCT grain_key) FROM anchor) AS distinct_key_variance,
  (SELECT COUNT(*) FROM output AS o ANTI JOIN anchor AS a ON o.grain_key IS NOT DISTINCT FROM a.grain_key) AS keys_in_output_only,
  (SELECT COUNT(*) FROM anchor AS a ANTI JOIN output AS o ON a.grain_key IS NOT DISTINCT FROM o.grain_key) AS keys_in_anchor_only,
  (SELECT COUNT(*) FROM output AS o JOIN anchor AS a ON o.grain_key IS NOT DISTINCT FROM a.grain_key AND o.measure IS DISTINCT FROM a.measure) AS keys_in_both_value_differs;
```
