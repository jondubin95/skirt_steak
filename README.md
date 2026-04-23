# Skirt Steak

This project is experimental and very much a work in progress. I am still exploring where it will go, so expect changes, rough edges, and frequent updates as ideas evolve.

## Setup for DuckDB + Python Development

This workspace is configured for local SQL and Python development. Using DuckDB for fast, free exploratory data analysis.

### Project Structure

```
skirt_steak/
├── .vscode/
│   ├── settings.json          # Workspace settings for Python & DuckDB
│   └── extensions.json        # Recommended extensions
├── .venv/                     # Virtual environment (created by setup)
├── sql/                       # SQL scripts
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
   python -m venv .venv
   
   # Activate (Windows)
   .\.venv\Scripts\Activate.ps1
   
   # Install packages
   pip install duckdb pandas black pylint
   ```

3. **Get Started with DuckDB**
   - Check out [python/duckdb_starter.py](python/duckdb_starter.py) for working examples
   - Learn how to:
     - Create and query local databases
     - Convert results to Pandas DataFrames
     - Read/write CSV files
     - Run fast analytical queries

### Workspace Settings

- Python formatter: Black (auto-format on save)
- Line rulers at 88 (Black) and 120 characters

### Tips

- **Local-first**: All data stays on your machine—no cloud dependencies
- **Fast**: DuckDB is optimized for analytical queries
- **Free**: No costs, no API keys, no setup
- **Extensible**: Easy to swap in other tools as your needs grow
