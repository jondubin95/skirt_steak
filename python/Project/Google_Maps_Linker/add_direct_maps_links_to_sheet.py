import json
import os
import pickle
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import requests
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / ".google_places_sheets_token.pickle"
PLACES_CACHE_FILE = PROJECT_ROOT / "python" / ".places_cache.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

NAME_HEADER = "Resturant Name"
LOCATION_HEADER = "Location"
TYPE_HEADER = "Food Type"
CATEGORY_HEADER = "Food Catigory"

OUTPUT_HEADERS = [
    "Google Maps Direct",
    "Google Place ID",
    "Google Match Name",
    "Google Match Address",
    "Google Match Confidence",
    "Google Match Query",
]


def normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def a1_quote(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def column_letter(index_1_based: int) -> str:
    letters = []
    while index_1_based:
        index_1_based, remainder = divmod(index_1_based - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def parse_sheet_url(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3:
        raise ValueError(f"Could not parse spreadsheet id from URL: {url}")

    spreadsheet_id = parts[2]
    query = parse_qs(parsed.query)
    if "gid" in query:
        gid = int(query["gid"][0])
    elif parsed.fragment.startswith("gid="):
        gid = int(parsed.fragment.split("=", 1)[1])
    else:
        gid = 0
    return spreadsheet_id, gid


def load_credentials():
    creds = None
    if TOKEN_FILE.exists():
        with TOKEN_FILE.open("rb") as token_file:
            creds = pickle.load(token_file)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with TOKEN_FILE.open("wb") as token_file:
            pickle.dump(creds, token_file)

    return creds


def load_cache() -> dict:
    try:
        if PLACES_CACHE_FILE.exists():
            return json.loads(PLACES_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_cache(cache: dict) -> None:
    PLACES_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=True, indent=2), encoding="utf-8")


def get_sheet(service, spreadsheet_id: str, target_gid: int):
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("sheetId") == target_gid:
            return props["title"]
    raise RuntimeError(f"No sheet found for gid={target_gid}")


def score_candidate(row: dict[str, str], place: dict) -> tuple[float, str]:
    display_name = place.get("displayName", {}).get("text", "")
    formatted_address = place.get("formattedAddress", "")
    primary_type = place.get("primaryTypeDisplayName", {}).get("text", "")

    name_score = similarity(row[NAME_HEADER], display_name)
    location_score = similarity(row[LOCATION_HEADER], formatted_address)
    type_score = max(
        similarity(row.get(TYPE_HEADER, ""), primary_type),
        similarity(row.get(CATEGORY_HEADER, ""), primary_type),
    )

    combined = (name_score * 0.7) + (location_score * 0.2) + (type_score * 0.1)
    if combined >= 0.88:
        confidence = "high"
    elif combined >= 0.72:
        confidence = "medium"
    else:
        confidence = "low"
    return combined, confidence


def build_query(row: dict[str, str]) -> str:
    parts = [row.get(NAME_HEADER, ""), row.get(LOCATION_HEADER, ""), "kosher restaurant"]
    return ", ".join(part.strip() for part in parts if part and part.strip())


def places_search_text_http(*, api_key: str, query: str) -> dict:
    resp = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": ",".join(
                [
                    "places.id",
                    "places.displayName",
                    "places.formattedAddress",
                    "places.primaryTypeDisplayName",
                ]
            ),
        },
        data=json.dumps(
            {
                "textQuery": query,
                "pageSize": 5,
                "languageCode": "en",
                "regionCode": "US",
            }
        ),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def lookup_place(*, api_key: str, row: dict[str, str]) -> dict:
    query = build_query(row)
    payload = places_search_text_http(api_key=api_key, query=query)

    places = payload.get("places", [])
    if not places:
        return {
            "query": query,
            "place_id": "",
            "display_name": "",
            "formatted_address": "",
            "confidence": "no-match",
            "url": "",
        }

    best_place = None
    best_score = -1.0
    best_confidence = "low"
    for place in places:
        score, confidence = score_candidate(row, place)
        if score > best_score:
            best_place = place
            best_score = score
            best_confidence = confidence

    place_id = best_place.get("id", "") if best_place else ""
    display_name = best_place.get("displayName", {}).get("text", "") if best_place else ""
    formatted_address = best_place.get("formattedAddress", "") if best_place else ""
    url = ""
    if place_id:
        query_param = quote(f"{row.get(NAME_HEADER, '').strip()} {row.get(LOCATION_HEADER, '').strip()}".strip())
        url = f"https://www.google.com/maps/search/?api=1&query={query_param}&query_place_id={place_id}"

    return {
        "query": query,
        "place_id": place_id,
        "display_name": display_name,
        "formatted_address": formatted_address,
        "confidence": best_confidence,
        "url": url,
    }


def main(sheet_url: str):
    spreadsheet_id, gid = parse_sheet_url(sheet_url)
    creds = load_credentials()
    sheets = build("sheets", "v4", credentials=creds)
    sheet_title = get_sheet(sheets, spreadsheet_id, gid)
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("PLACES_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing Places API key. Set env var GOOGLE_MAPS_API_KEY (or PLACES_API_KEY) "
            "after enabling the Places API for your Google Cloud project."
        )
    cache = load_cache()

    rows = (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=a1_quote(sheet_title))
        .execute()
        .get("values", [])
    )
    if not rows:
        raise RuntimeError("Target sheet is empty.")

    headers = rows[0]
    if NAME_HEADER not in headers or LOCATION_HEADER not in headers:
        raise RuntimeError(f"Missing required columns: {NAME_HEADER} and/or {LOCATION_HEADER}")

    # Prefer reusing an existing output block if present; otherwise append a new block.
    existing_start = None
    if OUTPUT_HEADERS[0] in headers:
        idx0 = headers.index(OUTPUT_HEADERS[0])
        if headers[idx0 : idx0 + len(OUTPUT_HEADERS)] == OUTPUT_HEADERS:
            existing_start = idx0 + 1  # 1-based

    output_start_idx = existing_start or (len(headers) + 1)
    start_col = column_letter(output_start_idx)
    end_col = column_letter(output_start_idx + len(OUTPUT_HEADERS) - 1)

    values = [OUTPUT_HEADERS]
    processed = 0
    for raw_row in rows[1:]:
        row = {headers[i]: raw_row[i] if i < len(raw_row) else "" for i in range(len(headers))}
        if not row.get(NAME_HEADER, "").strip():
            values.append(["", "", "", "", "", ""])
            continue

        query = build_query(row)
        match = cache.get(query)
        if not isinstance(match, dict):
            match = None
        if not match:
            match = lookup_place(api_key=api_key, row=row)
            cache[query] = match

        if match.get("url"):
            label = match.get("display_name") or row.get(NAME_HEADER, "").strip() or "Open Place"
            label = label.replace('"', "'")
            direct_formula = f'=HYPERLINK("{match["url"]}","{label}")'
        else:
            direct_formula = ""

        values.append(
            [
                direct_formula,
                match.get("place_id", ""),
                match.get("display_name", ""),
                match.get("formatted_address", ""),
                match.get("confidence", ""),
                match.get("query", query),
            ]
        )
        processed += 1

    # Persist cache even if the sheet update fails (helps resume).
    try:
        save_cache(cache)
    except Exception:
        pass

    target_range = f"{a1_quote(sheet_title)}!{start_col}1:{end_col}{len(values)}"
    (
        sheets.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=target_range,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )

    print(
        f"Updated {sheet_title}!{start_col}1:{end_col}{len(values)} "
        f"with direct Google place links for {processed} rows."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_direct_maps_links_to_sheet.py <google-sheet-url>")
        raise SystemExit(1)
    main(sys.argv[1])
