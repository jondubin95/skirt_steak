"""Shared OAuth load for the board-secretary package.

Callers keep their own scopes and token paths. This module does not pick a
default client file or a default token file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence


def _oauth_modules() -> tuple[Any, Any, Any, type[BaseException]]:
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    return Request, Credentials, InstalledAppFlow, RefreshError


def load_credentials(
    creds_path: Path,
    token_path: Path,
    scopes: Sequence[str],
    *,
    interactive: bool = True,
    force_consent: bool = False,
    timeout_seconds: int | None = None,
    refresh_failure_message: str | None = None,
) -> Any:
    """Load a token, refresh it, or run a local-server consent and save it.

    A valid saved token is returned as-is. An expired token with a refresh
    token is refreshed and written back. Otherwise, when interactive is true,
    InstalledAppFlow runs on port 0 with offline access and prompt consent.
    force_consent skips the saved token and always runs that flow. reauth.py
    uses that path so a failed refresh is replaced by a new sign-in.
    timeout_seconds is passed through only when the caller sets it.
    """
    request_cls, credentials_cls, flow_cls, refresh_error = _oauth_modules()
    scope_list = list(scopes)
    creds = None
    if not force_consent and token_path.exists():
        creds = credentials_cls.from_authorized_user_file(str(token_path), scope_list)
    needs_flow = force_consent or not creds or not creds.valid
    if not needs_flow:
        return creds
    if not force_consent and creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(request_cls())
        except refresh_error as exc:
            if refresh_failure_message is None:
                raise
            raise SystemExit(refresh_failure_message) from exc
    else:
        if not interactive:
            raise SystemExit(
                "Google sign-in is required and interactive sign-in is disabled."
            )
        if not creds_path.is_file():
            raise SystemExit(f"Missing OAuth client file: {creds_path}")
        flow = flow_cls.from_client_secrets_file(str(creds_path), scope_list)
        server_kwargs: dict[str, Any] = {
            "port": 0,
            "access_type": "offline",
            "prompt": "consent",
        }
        if timeout_seconds is not None:
            server_kwargs["timeout_seconds"] = timeout_seconds
        creds = flow.run_local_server(**server_kwargs)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds
