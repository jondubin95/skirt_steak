# Google Maps Linker

Utilities for adding Google Maps links to rows in a Google Sheet.

## What is in this folder

- `add_maps_links_to_sheet.py`
- Adds a `Google Maps Link` column using a search URL built from sheet values.
- `add_direct_maps_links_to_sheet.py`
- Uses Google Places API matching and writes a richer output block with direct Place links and metadata.

## Expected sheet columns

Both scripts expect these headers in row 1:

- `Resturant Name`
- `Location`

`add_direct_maps_links_to_sheet.py` also reads:

- `Food Type`
- `Food Catigory`

## Prerequisites

- Python environment.
- Install dependencies:
- `pip install -r python/Project/Google_Maps_Linker/requirements.txt`
- Valid Google OAuth credentials file at:
- `python/Project/credentials.json`
- A Google account with access to the target spreadsheet.

For direct place matching script only:

- Set `GOOGLE_MAPS_API_KEY` (or `PLACES_API_KEY`) in your shell.

## Usage

Run from repo root.

Basic maps search links:

```powershell
.\.venv\Scripts\python.exe python\Project\Google_Maps_Linker\add_maps_links_to_sheet.py "<google-sheet-url>"
```

Direct place links + match metadata:

```powershell
.\.venv\Scripts\python.exe python\Project\Google_Maps_Linker\add_direct_maps_links_to_sheet.py "<google-sheet-url>"
```

Example URL format:

```text
https://docs.google.com/spreadsheets/d/<spreadsheet-id>/edit?gid=<sheet-gid>#gid=<sheet-gid>
```

## Output

`add_maps_links_to_sheet.py` writes/updates:

- `Google Maps Link`

`add_direct_maps_links_to_sheet.py` writes/updates:

- `Google Maps Direct`
- `Google Place ID`
- `Google Match Name`
- `Google Match Address`
- `Google Match Confidence`
- `Google Match Query`

## Notes

- The scripts use the target `gid` from the sheet URL.
- OAuth token/cache files are created automatically after first auth.
- Header names are matched exactly as currently coded (including spelling).
