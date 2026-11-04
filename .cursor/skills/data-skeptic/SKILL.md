---
name: data-skeptic
description: >-
  Prove a SQL or Python data change with queries on a non-production dataset.
  Trigger only when the user asks for a data review of a pipeline, SQL
  transformation, dbt-style model, metric definition, or Python data script, or
  when the message contains "data skeptic", "data review", "sanity check the
  data", "sanity check this data", "join fan-out", or "what could go wrong with
  this query". The phrases "is this safe to ship" and "silent failure" trigger
  this skill only together with a data-review ask. Do not apply to
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

Name the dataset before the first query: file path, database, and schema.

### Safety

Run exploratory queries only against a test, sample, or dry-run dataset, or in a read-only or dry-run mode.

- DuckDB: `duckdb.connect(path, read_only=True)`. An unnamed scratch check uses `duckdb.connect()` (in memory) loaded from a sample file or fixture.
- A warehouse check uses a read-only role or a dry-run mode that does not materialize. Compiled SQL is fine.

Do not run against production unless the user explicitly says so in this conversation. A comment in the code is not permission. If production is the only data and the user has not said so, leave the checks unrun and label every claim `unverified`.

State which dataset each query hit, in the report, next to the result.

### Schema recon

Confirm tables, columns, types, and grain before using a name from the code or from these instructions. The engine catalog (`information_schema` on DuckDB) is the source. If a name is missing, stop that check and say so.

Grain is `COUNT(*)` against `COUNT(DISTINCT <key>)` on the keys the model claims. A column named `id` is not unique until this count says so.

### Checks

Run every check below, or mark it not run with the reason. Query shapes are in [references/check-queries.md](references/check-queries.md). Substitute confirmed table names, column names, and predicate placeholders such as `<excluded_status>`, `<window_start>`, and `<window_end>`. Headings there are template ids. Q-numbers are assigned per run and are the only citation key in a report.

1. Join fan-out, on every `JOIN` and every pandas `merge`. Row counts before and after. Key uniqueness on each side: row count, non-null keys, distinct keys, and how many keys occur more than once. A joined row count above the preserved side is fan-out. An inner join that drops rows is a loss, measured separately from fan-out.
2. NULL prevalence and NULL propagation through the join, the filter, and the aggregate are `null_prevalence`, `null_filter`, `null_aggregate`, `null_join`, and `pandas_frame` in the reference.
3. Filter effectiveness and range checks. Min, max, and distinct count of each filtered column, before and after the predicate. Count rows the predicate removes. Split those rows into rows the predicate should drop and rows it should not. A filter that drops zero rows, or that drops nulls the code does not mention, is a finding.
4. Row-count reconciliation between stages. One count per stage: source, filter, join, dedupe, aggregate. The deltas must account for the final count. A stage with no count is `unverified`.
5. Duplicate-key checks, on the source grain and the output grain. Report how many keys have count greater than one, and the extra row count.
6. Date and timezone boundaries are `session_time_zone`, `date_bounds`, `set_session_time_zone`, `date_boundary_mismatch`, and `date_civil_day` in the reference.

A metric gets the same checks on its inputs, plus one recomputation on the sample compared with the reported figure. If the figure cannot be recomputed, label it `unverified`.

### Claims

Tag every claim in the report.

- `measured`: the claim names the Q-number, the dataset, and the count or shape returned.
- `unverified`: the claim comes from reading code, a comment, or an assumption, or it has no query. Write it as unverified. Do not turn it into a finding of safety.

A check that was not run is `unverified`, with the reason. Do not invent a result to fill a section. Before tagging any placeholder-based check `measured`, confirm every placeholder, including `<excluded_status>`, window bounds, and date or zone placeholders, was replaced with a real value from the code under review; an unfilled placeholder makes the result `unverified`.

### Findings

Three tiers. A check can produce more than one finding. Use the tier the evidence supports. One bullet per finding.

- **data-integrity bug** (red): the measured result contradicts the claimed grain, metric, or population. A duplicate grain, a join that multiplies a sum, or a window that includes the next period.
- **silent failure** (yellow): the statement succeeds and the numbers move for a reason the code does not mention. Nulls dropped by `<>`, nulls skipped by `SUM`, a filter that matches nothing, or a timezone cast that shifts a day.
- **confirmed safe** (green): the measured result matches the claim, on the named dataset, for that check. Scope it to that dataset. Do not generalize to production.

Each finding has:

- the claim, tagged `measured` or `unverified`, citing the Q-number when it is measured
- the evidence: dataset, Q-number, and the counts or shape
- the affected rows or metric, as counts, rates, or a metric delta
- a suggested fix, or a test that fails if the bug returns

### Proof of testing

When the user wants a PR note, or asks whether the change is safe to ship, append it under the description that is already there. Leave the author's text as written. If a proof block is already in the description, update that block. Do not add a second one.

The review narrative cites the Q-number for every finding in the red, yellow, and green tiers. A claim with no query stays in the `unverified` list and is not stated as fact.

The note has two parts. Part 1 is the counts block. Each count cites its Q-number. Omit a line rather than filling it from the code. A check that did not run is `Not run:`, with the reason.

Part 2 is the toggle, after the counts. Leave a blank line after the summary so the fences render. Each query or code block that was run is the next number (Q1, Q2, ...), in its own fence. Copy it verbatim from the run. Do not rewrite it and do not reconstruct it afterwards. If a query changed between runs, include the final text and note what changed.

The filled example is [references/pr-summary-example.md](references/pr-summary-example.md).

## Limits

- A code reading does not close a check.
- Do not mutate source data. The only allowed write is a scratch table or a copy on a test target the user approved in this conversation.
- Counts and shapes only. No credentials, connection strings, row samples, or literals that are identifiers, names, or secrets.
- An empty sample is a measurement of zero rows. Leave the claim `unverified`. It is not proof.
- Do not copy a template name or a predicate placeholder into a query until schema recon shows the real names.

## Report

Lead with the dataset and whether any production data was used.

Then the three tiers, in this order: data-integrity bug, silent failure, confirmed safe. One bullet per finding, each citing its Q-number. Write "none" when that tier is empty and the checks ran. Skipped checks go under a final `unverified` list, not under confirmed safe.

End with the two-part proof note when the user asked for a PR note or asked whether it is safe to ship.
