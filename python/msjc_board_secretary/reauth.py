#!/usr/bin/env python3
"""Sign-in for the board-minutes writer.

Run from the repo root when write_tab.py reports that the Google token
refresh failed. The person approves the sign-in prompt where it is shown.
Approving the prompt replaces Sensitive/google/gdocs_token.json.
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

from msjc_board_secretary.auth import load_credentials  # noqa: E402
from msjc_board_secretary.write_tab import (  # noqa: E402
    DEFAULT_CREDS,
    DEFAULT_TOKEN,
    SCOPES,
)

WAIT_SECONDS = 300


def _sign_in_timeout_type() -> type[BaseException]:
    from google_auth_oauthlib.flow import WSGITimeoutError

    return WSGITimeoutError


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
    try:
        load_credentials(
            creds_path,
            token_path,
            SCOPES,
            interactive=True,
            force_consent=True,
            timeout_seconds=WAIT_SECONDS,
        )
    except _sign_in_timeout_type() as exc:
        raise SystemExit(
            "No sign-in arrived. Run this script again and approve the prompt."
        ) from exc
    delete_leftover_bad_token(token_path)
    print("token saved")


if __name__ == "__main__":
    main()
