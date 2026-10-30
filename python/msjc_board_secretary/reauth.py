#!/usr/bin/env python3
"""Browser sign-in for the board-minutes writer.

Run from the repo root when write_tab.py reports that the Google token
refresh failed. Approving the prompt replaces Sensitive/google/gdocs_token.json.
The previous token file is replaced only after sign-in succeeds.
The script does not print the saved token or the authorization code.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError  # noqa: E402

from msjc_board_secretary.write_tab import (  # noqa: E402
    DEFAULT_CREDS,
    DEFAULT_TOKEN,
    SCOPES,
)

WAIT_SECONDS = 300


def delete_leftover_bad_token(token_path: Path) -> None:
    leftover = token_path.with_name("gdocs_token.bad.json")
    if leftover.is_file():
        leftover.unlink()


def main() -> None:
    creds_path = Path(DEFAULT_CREDS)
    token_path = Path(DEFAULT_TOKEN)
    if not creds_path.is_file():
        raise SystemExit(f"Missing OAuth client file: {creds_path}")
    logging.getLogger("google_auth_oauthlib").setLevel(logging.WARNING)
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    try:
        creds = flow.run_local_server(
            port=0,
            timeout_seconds=WAIT_SECONDS,
            access_type="offline",
            prompt="consent",
        )
    except WSGITimeoutError as exc:
        raise SystemExit(
            "No sign-in arrived. Run this script again and approve the prompt."
        ) from exc
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    delete_leftover_bad_token(token_path)
    print("token saved")


if __name__ == "__main__":
    main()
