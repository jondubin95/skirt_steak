# Skirt Steak

This project is experimental and very much a work in progress. I am still exploring where it will go, so expect changes, rough edges, and frequent updates as ideas evolve.

## Setup for BigQuery + Python Development

This workspace is configured for SQL and Python development with GitHub Copilot, replicating Cursor's Rules and Skills in VS Code.

### Project Structure

```
skirt_steak/
├── .vscode/
│   ├── settings.json          # Workspace settings for Python & BigQuery SQL
│   └── extensions.json        # Recommended extensions
├── sql/                       # BigQuery SQL scripts
├── python/                    # Python scripts
├── notebooks/                 # Jupyter notebooks
└── README.md
```

### Getting Started

1. **Install Recommended Extensions**
   - Open VS Code and go to Extensions (Ctrl+Shift+X)
   - Click "Show Recommended Extensions"
   - Install: Python, Pylance, SQLFluff, Black Formatter, GitHub Copilot, Copilot Chat

2. **Set Up Python Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate (Windows)
   .\venv\Scripts\Activate.ps1
   
   # Install common packages
   pip install pandas pandas-gbq google-cloud-bigquery black pylint
   ```

3. **Use Custom Prompt "Skills" with Copilot Chat**
   - Create these `.prompt` files in your user prompts folder: `c:\Users\jondu\AppData\Roaming\Code\User\prompts\`
   
   **bigquery-sql-optimization.prompt:**
   ```
   # BigQuery SQL Optimization Skill
   You are an expert BigQuery SQL developer.
   
   ## Your expertise includes:
   - Query optimization (partitioning, clustering, WHERE clauses)
   - BigQuery-specific features (ARRAY/STRUCT, UNNEST, window functions)
   - Performance tips (INT64 vs STRING, column pruning, LIMIT in dev)
   - Approximate functions (APPROX_COUNT_DISTINCT, APPROX_QUANTILES)
   ```
   
   **python-data-scripting.prompt:**
   ```
   # Python Data Scripting Skill
   You are an expert Python data engineer.
   
   ## Your expertise includes:
   - pandas/pandas-gbq for BigQuery integration
   - Python best practices (type hints, docstrings, error handling)
   - Performance optimization (vectorization, chunking large queries)
   - Logging and debugging patterns
   ```

4. **Workspace Settings**
   - Python formatter: Black (auto-format on save)
   - SQL formatter: SQLFluff (BigQuery dialect)
   - Line rulers at 88 (Black) and 120 characters

### Using Copilot Chat with Skills

1. Open Copilot Chat (Ctrl+Shift+I or Cmd+Shift+I)
2. Reference your skill by typing: `@bigquery-sql-optimization` or `@python-data-scripting`
3. Ask your question - the skill context will guide Copilot's responses

### Tips

- **Low-tech setup**: All configuration is in `.vscode/settings.json` and `.prompt` files
- **No licenses needed**: Uses GitHub Copilot Free or your existing license
- **Replaces Cursor features**: `.prompt` files function like Cursor's Skills, `settings.json` like Rules
- **Extensible**: Add more `.prompt` files for other domains as needed
