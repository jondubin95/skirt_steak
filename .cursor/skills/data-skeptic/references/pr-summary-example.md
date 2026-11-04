# Proof of testing in a PR description

This example abbreviates for length: Q2 and Q4-Q10 show the check name only, and a real note contains the verbatim statement for every Q-number.

Append the note under the description that is already there. Leave the author's text as written. Counts cite a Q-number. The toggle's fences are the statements that were run.

Rebuild the sample with [fixture.sql](fixture.sql). Predicate in this run: excluded status `canceled`, half-open window 2024-01-01 to 2025-01-01, zones `UTC` and `America/New_York`.

Q5 and Q7 are the final statements from this run. Q5 counts before and after the kept predicate. Q7 adds a dedupe stage, aggregates the join, and sums `order_total`.

## Appended under Summary

The Summary is the author's. The review, the counts, and the toggle are added after it.

## Summary

- Canceled orders stay in the source table and drop out of the 2024 window.
- A null status stays in the population. The old inequality comparison removed it.

## Review

### data-integrity bug

- `measured`: `orders.order_id` is not a key: 9 rows, 8 distinct (Q1); 1 duplicate group, 1 extra row (Q2). Affected: 1 extra row. Fix: one row per `order_id` before any join.
- `measured`: `orders` to `customers` on `customer_id` fans out: left 9, right 4, inner 10, left join 12 (Q3). Affected: the join has more rows than `orders`. Fix: one row per `customer_id` on the right, then re-count.
- `measured`: The joined stage is 9 rows, sum 122; the filtered stage is 6 rows, sum 67 (Q7). The join adds 3 rows and 55 to the sum. Affected: 3 extra rows after the filter. Fix: one row per `customer_id` on the right, then re-count.

### silent failure

- `measured`: `status <> 'canceled'` keeps 6 rows; `IS DISTINCT FROM` keeps 8; null status is 2 (Q4). The inequality drops both nulls. Fix: use `IS DISTINCT FROM` when a null status should remain.
- `measured`: Civil day 2024-03-10 is 2 rows in UTC and 1 row in America/New_York (Q10). Affected: 1 event leaves that civil day when the zone changes. Fix: compare instants in one named zone.

### confirmed safe

- `measured`: The sample contains one null status inside the 2024 window, and `kept` retains it. The filtered stage is 6 (Q7), the 7 in-window rows minus the 1 canceled row (kept 6 plus excluded 1, Q6).

### unverified

- `unverified`: Output grain. No query was run on a table downstream of `orders`.
- `unverified`: schema, join_key_uniqueness, null_prevalence, null_aggregate, null_join, date_boundary_mismatch, pandas_frame, and control_total_tieout. The `Not run:` lines give the reason for each.

## Proof of testing

Dataset: in-memory sample (orders, customers, events)
Schema: orders.order_id has 9 rows and 8 distinct values (Q1); 1 duplicate group, 1 extra row (Q2); customers has 4 rows (Q3); events.event_at has 7 rows and 1 null (Q9)
Joins: orders to customers on customer_id, left 9 / right 4 / inner 10 / left join 12 (Q3)
Nulls: status nulls 2; `status <> 'canceled'` kept 6; `IS DISTINCT FROM` kept 8 (Q4)
Filters: 9 rows before the kept predicate, 6 after (Q5); min/max order_date 2024-01-15 to 2025-01-01 before, 2024-01-15 to 2024-12-31 after (Q5); distinct status 2 before, 1 after (Q5); split is excluded 1, kept 6, null date 1, outside window 1 (Q6). The 2025-01-01 null status is `outside_window` because the date test comes first; the in-window null status is `kept`.
Stages: source 9 rows sum 84, filtered 6 sum 67, joined 9 sum 122, deduped 5 sum 47, aggregated 4 sum 122, null-key groups 1 (Q7)
Dates: event_at min 2024-01-15 12:00:00+00, max 2024-03-10 12:00:00+00, session zone Etc/UTC (Q8, Q9); civil day 2024-03-10 is 2 rows in UTC and 1 in America/New_York (Q10)
Not run: schema. `schema_tables` and `schema_columns` were not queried.
Not run: join_key_uniqueness. `join_key_counts` and `join_key_duplicates` were not queried.
Not run: null_prevalence. Per-column null counts other than status were not queried.
Not run: null_aggregate. The sum of `order_total` was not queried.
Not run: null_join. Null-key loss after collapsing `customers` was not queried.
Not run: date_boundary_mismatch. Half-open versus inclusive counts were not queried.
Not run: pandas_frame. The pandas merge and groupby were not run.
Not run: control_total_tieout. No anchor was named.

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

`duplicate_keys`, verbatim from the run.

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

`null_filter`, verbatim from the run.

Q5

`filter_range`, verbatim from the run.

Q6

`filter_drop_split`, verbatim from the run.

Q7

`stage_counts`, verbatim from the run.

Q8

`session_time_zone`, verbatim from the run.

Q9

`date_bounds`, verbatim from the run.

Q10

`date_civil_day`, verbatim from the run.

</details>

If the description already has a `## Proof of testing` block, replace that block, including its toggle. Do not append a second one.
