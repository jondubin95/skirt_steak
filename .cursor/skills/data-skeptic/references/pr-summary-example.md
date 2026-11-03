# Proof of testing in a PR description

Append the block under the description that is already there. Leave the author's text as written. Counts and shapes only. No row samples, credentials, or connection strings.

The counts are from an in-memory DuckDB sample of `orders`, `customers`, and `events`.

## Appended under Summary

The Summary is the author's. The proof block is added after it.

```md
## Summary

- Canceled orders stay in the source table and drop out of the 2024 window.
- A null status stays in the population. The old inequality comparison removed it.

## Proof of testing
Dataset: in-memory sample (orders, customers, events)
Schema: orders.order_id has 8 rows and 7 distinct values (1 duplicate group, 1 extra row); customers has 4 rows; events.event_at has 7 rows and 1 null
Joins: orders to customers on customer_id, left 8 / right 4 / inner 9 / left join 11
Nulls: status nulls 1; `status <> 'canceled'` kept 6; `IS DISTINCT FROM` kept 7
Filters: 8 rows before; 6 in the half-open 2024 window; split is canceled 1, kept 5, null date 1, outside window 1
Stages: source 8, filtered 5, joined 8, aggregated 3
Dates: event_at min 2024-01-15 12:00:00+00, max 2024-03-10 12:00:00+00, session zone UTC; civil day 2024-03-10 is 2 rows in UTC and 1 in America/New_York
```

## When a line is omitted

A check that did not run has no count line. The reason goes on `Not run:`. This paste measured the join only. It does not invent a date count.

```md
## Proof of testing
Dataset: in-memory sample (orders, customers, events)
Joins: orders to customers on customer_id, left 8 / right 4 / inner 9 / left join 11
Not run: date and timezone boundaries. The query under review has no timestamp column.
```

If the description already has a `## Proof of testing` block, replace that block. Do not append a second one.
