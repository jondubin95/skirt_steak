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

If the artifact is not data work, say this skill does not apply and stop. Name the dataset before the first query: file path, database, and schema.

Run only on a test, sample, or dry-run dataset, or in a read-only or dry-run mode. DuckDB: `duckdb.connect(path, read_only=True)`, or `duckdb.connect()` loaded from a sample file. A warehouse check uses a read-only role or a dry-run that does not materialize; compiled SQL is fine. Do not run against production unless the user explicitly says so in this conversation. A comment in the code is not permission. If production is the only data and the user has not said so, leave the checks unrun.

Confirm tables, columns, types, and grain from the engine catalog before using a name (`schema_tables`, `schema_columns`, `grain`). If a name is missing, stop that check.

Run every check, or mark it not run with the reason. Shapes: [references/check-queries.md](references/check-queries.md). Headings there are template ids. Q-numbers are assigned per run and are the only citation key. Fill table names, column names, and every placeholder from schema recon and the code before running. An unfilled placeholder is `unverified`.

1. Join fan-out and row loss, on every `JOIN` and pandas `merge`: `join_key_counts`, `join_row_counts`.
2. NULL prevalence and propagation through the join, the filter, and the aggregate: `null_prevalence`, `null_filter`, `null_aggregate`, `null_join`, `pandas_frame`.
3. Filter effectiveness and range (`filter_range`, `filter_drop_split`). A filter that drops zero rows, or that drops nulls the code does not mention, is a finding.
4. Row-count reconciliation (`stage_counts`): one count per stage (source, filter, join, dedupe, aggregate). The deltas must account for the final count. A stage with no count is `unverified`.
5. Duplicate keys on the source grain and the output grain: `duplicate_keys`.
6. Date and timezone boundaries: `session_time_zone`, `date_bounds`, `set_session_time_zone`, `date_boundary_mismatch`, `date_civil_day`.
7. Control-total tie-out (`control_total_tieout`) to a named anchor: a control total, a prior-period output, or a separate source table, not an upstream CTE. No anchor: `unverified`.

A metric gets the same checks on its inputs, plus one recomputation on the sample compared with the reported figure. If the figure cannot be recomputed, it is `unverified`.

### Claims
- `measured`: names the Q-number, the dataset, and the count or shape returned.
- `unverified`: from reading code, a comment, or an assumption, or it has no query. A check that was not run is `unverified`, with the reason. Do not turn it into a finding of safety.

### Findings
Three tiers. A check can produce more than one finding. One bullet per finding. Use the tier the evidence supports.

- **data-integrity bug** (red): the measured result contradicts the claimed grain, metric, or population.
- **silent failure** (yellow): the statement succeeds and the numbers move for a reason the code does not mention.
- **confirmed safe** (green): the measured result matches the claim, on the named dataset, for that check. Do not generalize to production.

Each finding has the tagged claim, the evidence (dataset, Q-number, and the counts or shape), the affected rows or metric, and a suggested fix or a test that fails if the bug returns.

### Proof of testing
When the user wants a PR note, or asks whether the change is safe to ship, append it under the description that is already there. Leave the author's text as written. If a proof block is already there, update that block. Do not add a second one.

Part 1 is the counts block. Omit a line rather than filling it from the code. A check that did not run is `Not run:`, with the reason. Part 2 is the toggle, after the counts. Leave a blank line after the summary so the fences render. Each query or code block that was run is the next number (Q1, Q2, ...), in its own fence, copied verbatim from the run. If a query changed between runs, include the final text and note what changed. The filled example is [references/pr-summary-example.md](references/pr-summary-example.md).

## Limits

- Do not mutate source data. The only allowed write is a scratch table or a copy on a test target the user approved in this conversation.
- Counts and shapes only. No credentials, connection strings, row samples, or literals that are identifiers, names, or secrets.
- An empty sample is a measurement of zero rows. Leave the claim `unverified`. It is not proof.

## Report

Lead with the dataset and whether any production data was used. Then the three tiers, in this order. A green finding must state that the sample contained the edge case the check targets. Write "none" when that tier is empty and the checks ran. Skipped checks go under a final `unverified` list, not under confirmed safe. End with the two-part proof note when the user asked for a PR note or asked whether it is safe to ship.
