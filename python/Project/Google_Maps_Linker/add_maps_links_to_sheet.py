import pickle
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from googleapiclient.discovery import build


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = PROJECT_ROOT / ".google_drive_token.pickle"
SCOPES = ["https://www.googleapis.com/auth/drive"]
MAPS_HEADER = "Google Maps Link"
NAME_HEADER = "Resturant Name"
LOCATION_HEADER = "Location"


def load_credentials():
    with TOKEN_FILE.open("rb") as token_file:
        creds = pickle.load(token_file)

    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with TOKEN_FILE.open("wb") as token_file:
            pickle.dump(creds, token_file)

    if not creds.valid:
        raise RuntimeError("Google credentials are not valid; re-run the OAuth flow first.")

    return creds


def parse_sheet_url(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    try:
        spreadsheet_id = parts[2]
    except IndexError as exc:
        raise ValueError(f"Could not parse spreadsheet id from URL: {url}") from exc

    query = parse_qs(parsed.query)
    if "gid" in query:
        gid = int(query["gid"][0])
    elif parsed.fragment.startswith("gid="):
        gid = int(parsed.fragment.split("=", 1)[1])
    else:
        gid = 0

    return spreadsheet_id, gid


def column_letter(index_1_based: int) -> str:
    letters = []
    while index_1_based:
        index_1_based, remainder = divmod(index_1_based - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def a1_quote(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def main(sheet_url: str):
    spreadsheet_id, target_gid = parse_sheet_url(sheet_url)
    creds = load_credentials()
    service = build("sheets", "v4", credentials=creds)

    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_props = None
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("sheetId") == target_gid:
            sheet_props = props
            break

    if not sheet_props:
        raise RuntimeError(f"No sheet found for gid={target_gid}")

    sheet_title = sheet_props["title"]
    rows = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=a1_quote(sheet_title))
        .execute()
        .get("values", [])
    )

    if not rows:
        raise RuntimeError("The target sheet is empty.")

    headers = rows[0]
    try:
        name_idx = headers.index(NAME_HEADER) + 1
        location_idx = headers.index(LOCATION_HEADER) + 1
    except ValueError as exc:
        raise RuntimeError(
            f"Required headers not found. Expected '{NAME_HEADER}' and '{LOCATION_HEADER}'."
        ) from exc

    if MAPS_HEADER in headers:
        maps_idx = headers.index(MAPS_HEADER) + 1
    else:
        maps_idx = len(headers) + 1

    maps_col = column_letter(maps_idx)
    name_col = column_letter(name_idx)
    location_col = column_letter(location_idx)
    last_row = len(rows)

    values = [[MAPS_HEADER]]
    for row_num in range(2, last_row + 1):
        formula = (
            f'=IF(LEN(TRIM({name_col}{row_num}))=0,"",'
            f'HYPERLINK("https://www.google.com/maps/search/?api=1&query="&'
            f'ENCODEURL(TRIM({name_col}{row_num}&" "&{location_col}{row_num})),"Google Maps"))'
        )
        values.append([formula])

    target_range = f"{a1_quote(sheet_title)}!{maps_col}1:{maps_col}{last_row}"
    (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=target_range,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )

    print(f"Updated {sheet_title}!{maps_col}1:{maps_col}{last_row} with {MAPS_HEADER}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_maps_links_to_sheet.py <google-sheet-url>")
        raise SystemExit(1)

    main(sys.argv[1])
