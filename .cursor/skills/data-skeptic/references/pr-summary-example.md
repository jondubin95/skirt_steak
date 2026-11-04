# Proof of testing in a PR description

Append the note under the description that is already there. Leave the author's text as written. Counts cite a Q-number. The toggle's fences are the statements that were run.

Rebuild the sample with [fixture.sql](fixture.sql). Predicate in this run: excluded status `canceled`, half-open window 2024-01-01 to 2025-01-01, zones `UTC` and `America/New_York`.

Q5 and Q7 are the final statements from this run. Q5 counts before and after the kept predicate. Q7 adds a dedupe stage and aggregates the join.

## Appended under Summary

The Summary is the author's. The review, the counts, and the toggle are added after it.

## Summary

- Canceled orders stay in the source table and drop out of the 2024 window.
- A null status stays in the population. The old inequality comparison removed it.

## Review

### data-integrity bug

- `measured`: `orders.order_id` is not a key: 8 rows, 7 distinct (Q1); 1 duplicate group, 1 extra row (Q2). Affected: 1 extra row. Fix: one row per `order_id` before any join.
- `measured`: `orders` to `customers` on `customer_id` fans out: left 8, right 4, inner 9, left join 11 (Q3). Affected: the join has more rows than `orders`. Fix: one row per `customer_id` on the right, then re-count.
- `measured`: The joined stage is 8 and the filtered stage is 5 (Q7). The join adds 3 rows. Affected: 3 extra rows after the filter. Fix: one row per `customer_id` on the right, then re-count.

### silent failure

- `measured`: `status <> 'canceled'` keeps 6 rows; `IS DISTINCT FROM` keeps 7; null status is 1 (Q4). The inequality drops the null. Fix: use `IS DISTINCT FROM` when a null status should remain.
- `measured`: Civil day 2024-03-10 is 2 rows in UTC and 1 row in America/New_York (Q10). Affected: 1 event leaves that civil day when the zone changes. Fix: compare instants in one named zone.

### confirmed safe

- `measured`: The filtered stage is 5 (Q7). That is the 6-row window minus the 1 canceled row (kept 5 plus excluded 1, Q6).

### unverified

- `unverified`: Output grain. No query was run on a table downstream of `orders`.
- `unverified`: schema, join_key_uniqueness, null_prevalence, null_aggregate, null_join, date_boundary_mismatch, and pandas_frame. The `Not run:` lines give the reason for each.

## Proof of testing

Dataset: in-memory sample (orders, customers, events)
Schema: orders.order_id has 8 rows and 7 distinct values (Q1); 1 duplicate group, 1 extra row (Q2); customers has 4 rows (Q3); events.event_at has 7 rows and 1 null (Q9)
Joins: orders to customers on customer_id, left 8 / right 4 / inner 9 / left join 11 (Q3)
Nulls: status nulls 1; `status <> 'canceled'` kept 6; `IS DISTINCT FROM` kept 7 (Q4)
Filters: 8 rows before the kept predicate, 5 after (Q5); min/max order_date 2024-01-15 to 2025-01-01 before, 2024-01-15 to 2024-12-31 after (Q5); distinct status 2 before, 1 after (Q5); split is excluded 1, kept 5, null date 1, outside window 1 (Q6). The one null-status row is in `outside_window` because the date test comes first.
Stages: source 8, filtered 5, joined 8, deduped 4, aggregated 3, null-key groups 1 (Q7)
Dates: event_at min 2024-01-15 12:00:00+00, max 2024-03-10 12:00:00+00, session zone Etc/UTC (Q8, Q9); civil day 2024-03-10 is 2 rows in UTC and 1 in America/New_York (Q10)
Not run: schema. `schema_tables` and `schema_columns` were not queried.
Not run: join_key_uniqueness. `join_key_counts` and `join_key_duplicates` were not queried.
Not run: null_prevalence. Per-column null counts other than status were not queried.
Not run: null_aggregate. The sum of `order_total` was not queried.
Not run: null_join. Null-key loss after collapsing `customers` was not queried.
Not run: date_boundary_mismatch. Half-open versus inclusive counts were not queried.
Not run: pandas_frame. The pandas merge and groupby were not run.

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
