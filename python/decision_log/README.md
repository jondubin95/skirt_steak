# Decision log

Local record of a market-analyst review. The DuckDB file, inbox JSON, and playbooks stay under `Sensitive/`. This repository tracks the schema, the summary query, and the CLI.

The CLI checks that the JSON fields agree. It does not check that a claim is true. DuckDB allows one writer, so close other sessions before `record` or `resolve`.

`duckdb` is on the repository baseline install line. This package does not add a `requirements.txt`.

## Commands

From the repo root:

```powershell
python python/decision_log/record.py check --input Sensitive/decisions/inbox/<id>.json
python python/decision_log/record.py record --input Sensitive/decisions/inbox/<id>.json
python python/decision_log/record.py resolve --id <uuid> --outcome right --notes "..."
python python/decision_log/record.py verify --id <uuid>
```

```bash
python python/decision_log/record.py check --input Sensitive/decisions/inbox/<id>.json
python python/decision_log/record.py record --input Sensitive/decisions/inbox/<id>.json
python python/decision_log/record.py resolve --id <uuid> --outcome right --notes "..."
python python/decision_log/record.py verify --id <uuid>
```

`check` validates the JSON and the playbook. It does not create a database, and a passing check does not mean `record` will succeed. The input shape is `sql/decision_log/example_inbox.json`.

## Summary

Read-only. It does not create a missing database. Run it from the repo root.

```powershell
python -c "import duckdb; from pathlib import Path; sql=Path('sql/decision_log/review_summary.sql').read_text(encoding='utf-8'); con=duckdb.connect('Sensitive/decisions/market_decisions.duckdb', read_only=True); print(con.execute(sql).fetchall())"
```

```bash
python -c "import duckdb; from pathlib import Path; sql=Path('sql/decision_log/review_summary.sql').read_text(encoding='utf-8'); con=duckdb.connect('Sensitive/decisions/market_decisions.duckdb', read_only=True); print(con.execute(sql).fetchall())"
```

## Export

Backup copies go under `Sensitive/decisions/export/`, which is gitignored. There is no export subcommand.

The same command works in PowerShell and bash. It quotes the CSV paths without nested shell quotes.

```powershell
python -c "import duckdb; from pathlib import Path; d=Path('Sensitive/decisions/export'); d.mkdir(parents=True, exist_ok=True); con=duckdb.connect('Sensitive/decisions/market_decisions.duckdb', read_only=True); q=chr(39); con.execute('COPY decisions TO '+q+str((d/'decisions.csv').as_posix())+q+' (HEADER, DELIMITER '+q+','+q+')'); con.execute('COPY evidence TO '+q+str((d/'evidence.csv').as_posix())+q+' (HEADER, DELIMITER '+q+','+q+')')"
```

```bash
python -c "import duckdb; from pathlib import Path; d=Path('Sensitive/decisions/export'); d.mkdir(parents=True, exist_ok=True); con=duckdb.connect('Sensitive/decisions/market_decisions.duckdb', read_only=True); q=chr(39); con.execute('COPY decisions TO '+q+str((d/'decisions.csv').as_posix())+q+' (HEADER, DELIMITER '+q+','+q+')'); con.execute('COPY evidence TO '+q+str((d/'evidence.csv').as_posix())+q+' (HEADER, DELIMITER '+q+','+q+')')"
```

## Tests

```powershell
python -m unittest discover -s python/decision_log/tests -p "test_*.py"
```
