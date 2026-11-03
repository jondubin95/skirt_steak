---
name: data-skeptic
description: >-
  Prove a SQL or Python data change with queries on a non-production dataset.
  Trigger only when the user asks for a data review of a pipeline, SQL
  transformation, dbt-style model, metric definition, or Python data script, or
  when the message contains "data skeptic", "data review", "sanity check the
  data", "sanity check this data", "is this safe to ship", "silent failure",
  "join fan-out", or "what could go wrong with this query". Do not apply to
  market-outcome claims, and do not apply to coding that is not a data check.
---

# Data Skeptic

## Purpose

Prove that a data change does what it claims. Reading the code is not evidence. Each check is a query or a computation on a named non-production dataset, and the report says what that run returned.

## Inputs

The pipeline, SQL transformation, dbt-style model, metric definition, or Python data script under review, and a dataset the user has named as test, sample, or dry-run. If no safe dataset is named, stop and ask. Do not guess a connection.

## Steps

### Confirm the work

If the artifact is not data work, say this skill does not apply and stop.

Name the dataset before the first query: file path, database, and schema. A connection string is not a name. Do not print credentials.

### Safety

Run exploratory queries only against a test, sample, or dry-run dataset, or in a read-only or dry-run mode.

- DuckDB: `duckdb.connect(path, read_only=True)`. An unnamed scratch check uses `duckdb.connect()` (in memory) loaded from a sample file or fixture.
- A warehouse check uses a read-only role or a dry-run mode that does not materialize. Compiled SQL is fine. A job that writes tables is not a check.
- Python: transform a sample frame or fixture in memory. Do not write results back to a shared table.

Do not mutate data. Do not run SQL that writes (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `DROP`, `ALTER`, or `COPY` to a destination). Do not write a frame back to a shared table. A pandas `merge` that stays in memory is a check, not a write.

Do not run against production unless the user explicitly says so in this conversation. A comment in the code is not permission. If production is the only data and the user has not said so, leave the checks unrun and label every claim `unverified`.

State which dataset each query hit, in the report, next to the result.

### Schema recon

Confirm tables, columns, types, and grain before using a name from the code or from these instructions. The engine catalog (`information_schema` on DuckDB) is the source. If a name is missing, stop that check and say so.

Grain is `COUNT(*)` against `COUNT(DISTINCT <key>)` on the keys the model claims. A column named `id` is not unique until this count says so.

### Checks

Run every check below, or mark it not run with the reason. Query shapes are in [references/check-queries.md](references/check-queries.md). Replace `orders`, `customers`, and `events` with names confirmed in schema recon. The templates return counts and ranges. Do not extend them to list key values or row samples in the report.

1. Join fan-out, on every `JOIN` and every pandas `merge`. Row counts before and after. Key uniqueness on each side: row count, non-null keys, distinct keys, and how many keys occur more than once. A joined row count above the preserved side is fan-out. An inner join that drops rows is a loss, measured separately from fan-out.
2. NULL prevalence and NULL propagation. Null count per column the logic reads. Then show what those nulls do in the join, the filter, and the aggregate. In SQL, `col <> 'x'` and `NOT IN` reject nulls. `SUM` and `AVG` skip nulls. An inner join drops null keys. SQL `GROUP BY` keeps one group for null keys. Pandas `merge` defaults to an inner join, and `groupby` drops null keys unless `dropna=False`.
3. Filter effectiveness and range checks. Min, max, and distinct count of each filtered column, before and after the predicate. Count rows the predicate removes. Split those rows into "the predicate should drop these" and "the predicate dropped something else." A filter that drops zero rows, or that drops nulls the code does not mention, is a finding.
4. Row-count reconciliation between stages. One count per stage: source, filter, join, dedupe, aggregate. The deltas must account for the final count. A stage with no count is `unverified`.
5. Duplicate-key checks, on the source grain and the output grain. Report how many keys have count greater than one, and the extra row count. Do not report the key values.
6. Date and timezone boundaries. Min and max of each timestamp. Compare a half-open window `[start, end)` with the inclusive predicate the code uses, and count rows on the boundary instant. If one side is a date and the other is a timestamp, count rows the cast moves across the boundary. Record the session time zone. If the column has a time zone, count the same civil day in that zone and in UTC, including a DST transition day when the sample contains one.

A metric gets the same checks on its inputs, plus one recomputation on the sample compared with the reported figure. If the figure cannot be recomputed, label it `unverified`.

### Claims

Tag every claim in the report.

- `measured`: the claim names the query or computation, the dataset, and the count or shape returned.
- `unverified`: the claim comes from reading code, a comment, or an assumption. Write it as unverified. Do not turn it into a finding of safety.

A check that was not run is `unverified`, with the reason. Do not invent a result to fill a section.

### Findings

Three tiers. A check can produce more than one finding. Use the tier the evidence supports.

- **data-integrity bug** (red): the measured result contradicts the claimed grain, metric, or population. A duplicate grain, a join that multiplies a sum, or a window that includes the next period.
- **silent failure** (yellow): the statement succeeds and the numbers move for a reason the code does not mention. Nulls dropped by `<>`, nulls skipped by `SUM`, a filter that matches nothing, or a timezone cast that shifts a day.
- **confirmed safe** (green): the measured result matches the claim, on the named dataset, for that check. Scope it to that dataset. Do not generalize to production.

Each finding has:

- the claim, tagged `measured` or `unverified`
- the evidence: dataset, query name from the references (or the computation), and the counts or shape
- the affected rows or metric, as counts, rates, or a metric delta
- a suggested fix, or a test that fails if the bug returns

Counts, rates, min and max of dates and numeric measures, and distinct counts are enough. Omit a min or max that is itself an identifier, a name, an email, free text, or a secret.

### Proof of testing

When the user wants a PR note, or asks whether the change is safe to ship, append a short block they can paste. Counts and shapes only. No row samples, credentials, or connection strings. Omit a line rather than filling it from the code.

Append the block under the description that is already there, or under a `## Proof of testing` heading. Leave the author's text as written. If a proof block is already in the description, update that block. Do not add a second one.

A filled example is in [references/pr-summary-example.md](references/pr-summary-example.md).

```md
## Proof of testing
Dataset: <file or database.schema, no connection string>
Schema: <tables and grain keys confirmed>
Joins: <left rows / right rows / after rows / duplicate keys per side>
Nulls: <column null counts that changed a result>
Filters: <rows before, rows after, unexpected drops>
Stages: <count per stage>
Dates: <min, max, boundary mismatch count, zone used>
Not run: <check and reason>
```

## Limits

- A code reading does not close a check.
- Do not mutate data, and do not query production unless the user explicitly allows it in this conversation.
- Do not print credentials, connection strings, or row samples.
- An empty sample is a measurement of zero rows. Leave the claim `unverified`. It is not proof.
- Do not copy example table names into a query until schema recon shows them.
- `dbt run`, `CREATE TABLE AS`, and a notebook cell that writes a table are out of scope unless the user explicitly asked for a write to a non-production target.

## Report

Lead with the dataset and whether any production data was used.

Then the three tiers, in this order: data-integrity bug, silent failure, confirmed safe. One finding per result. Write "none" when that tier is empty and the checks ran. Skipped checks go under a final `unverified` list, not under confirmed safe.

End with the proof-of-testing block when the user asked for a PR note or asked whether it is safe to ship.
