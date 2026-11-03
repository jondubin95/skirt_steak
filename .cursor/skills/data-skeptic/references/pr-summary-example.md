# Proof of testing in a PR description

Append the note under the description that is already there. Leave the author's text as written. The counts cite a Q-number. The toggle holds the statements that were run, copied verbatim. None of the statements below were edited after the run.

Counts and shapes only. The dataset is named without a connection string. No row samples, credentials, or identifier literals.

The counts are from an in-memory DuckDB sample of `orders`, `customers`, and `events`.

## Appended under Summary

The Summary is the author's. The review, the counts, and the toggle are added after it.

## Summary

- Canceled orders stay in the source table and drop out of the 2024 window.
- A null status stays in the population. The old inequality comparison removed it.

## Review

### data-integrity bug

- `orders.order_id` is not a key: 8 rows, 7 distinct (Q1); 1 duplicate group, 1 extra row (Q2). Affected: 1 extra row. Fix: one row per `order_id` before any join.
- `orders` to `customers` on `customer_id` fans out: left 8, right 4, inner 9, left join 11 (Q3). Affected: the join has more rows than `orders`. Fix: one row per `customer_id` on the right, then re-count.

### silent failure

- `status <> 'canceled'` keeps 6 rows; `IS DISTINCT FROM` keeps 7; null status is 1 (Q4). The inequality drops the null. Fix: use `IS DISTINCT FROM` when a null status should remain.
- Civil day 2024-03-10 is 2 rows in UTC and 1 row in America/New_York (Q10). Affected: 1 event leaves that civil day when the zone changes. Fix: compare instants in one named zone.

### confirmed safe

- On this sample, the half-open 2024 window holds 6 of 8 rows (Q5), 1 row is canceled (Q6), and the filtered stage is 5 (Q7). That stage is the window minus the canceled row.

### unverified

- Output grain. No query was run on a table downstream of `orders`.

## Proof of testing

Dataset: in-memory sample (orders, customers, events)
Schema: orders.order_id has 8 rows and 7 distinct values (Q1); 1 duplicate group, 1 extra row (Q2); customers has 4 rows (Q3); events.event_at has 7 rows and 1 null (Q9)
Joins: orders to customers on customer_id, left 8 / right 4 / inner 9 / left join 11 (Q3)
Nulls: status nulls 1; `status <> 'canceled'` kept 6; `IS DISTINCT FROM` kept 7 (Q4)
Filters: 8 rows before; 6 in the half-open 2024 window (Q5); split is canceled 1, kept 5, null date 1, outside window 1 (Q6)
Stages: source 8, filtered 5, joined 8, aggregated 3, aggregated null key 1 (Q7)
Dates: event_at min 2024-01-15 12:00:00+00, max 2024-03-10 12:00:00+00, session zone UTC (Q8, Q9); civil day 2024-03-10 is 2 rows in UTC and 1 in America/New_York (Q10)

<details>
<summary>Queries run</summary>

Q1

```sql
SELECT
  COUNT(*) AS row_count,
  COUNT(order_id) AS non_null_order_id,
  COUNT(DISTINCT order_id) AS distinct_order_id
FROM orders;
```

Q2

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

Q3

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

Q4

```sql
SELECT
  COUNT(*) FILTER (WHERE status IS NULL) AS null_status,
  COUNT(*) FILTER (WHERE status <> 'canceled') AS kept_by_not_equal,
  COUNT(*) FILTER (WHERE status IS DISTINCT FROM 'canceled') AS kept_by_is_distinct_from
FROM orders;
```

Q5

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

Q6

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

Q7

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

Q8

```sql
SELECT CURRENT_SETTING('TimeZone') AS session_time_zone;
```

Q9

```sql
SELECT
  CAST(MIN(event_at) AS VARCHAR) AS min_event_at,
  CAST(MAX(event_at) AS VARCHAR) AS max_event_at,
  COUNT(*) AS row_count,
  COUNT(*) FILTER (WHERE event_at IS NULL) AS null_event_at
FROM events;
```

Q10

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

</details>

## When a line is omitted

A check that did not run has no count line. The reason goes on `Not run:`, and it stays unverified. This paste measured the join only. Its Q1 is the join statement from that run, not Q3 above.

## Proof of testing

Dataset: in-memory sample (orders, customers, events)
Joins: orders to customers on customer_id, left 8 / right 4 / inner 9 / left join 11 (Q1)
Not run: date and timezone boundaries. The query under review has no timestamp column.

<details>
<summary>Queries run</summary>

Q1

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

</details>

If the description already has a `## Proof of testing` block, replace that block, including its toggle. Do not append a second one.
