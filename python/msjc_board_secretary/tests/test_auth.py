"""OAuth loader and the callers that share it. Standard library only."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from msjc_board_secretary import auth, docs_mcp, reauth, write_tab  # noqa: E402

DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive.readonly"]


class RefreshError(Exception):
    pass


class OtherFailureError(Exception):
    pass


class FakeCreds:
    def __init__(self, *, valid: bool, expired: bool = False, refresh_token: str | None = "rt") -> None:
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.payload = "refreshed"

    def refresh(self, request: object) -> None:
        self.refresh_calls.append(request)
        self.valid = True

    refresh_calls: list[object] = []

    def to_json(self) -> str:
        return self.payload


class CredentialsApi:
    instance: FakeCreds | None = None
    seen: tuple[str, list[str]] | None = None

    @staticmethod
    def from_authorized_user_file(path: str, scopes: list[str]) -> FakeCreds:
        CredentialsApi.seen = (path, list(scopes))
        assert CredentialsApi.instance is not None
        return CredentialsApi.instance


class FlowApi:
    calls: list[tuple] = []
    result = FakeCreds(valid=True)

    @staticmethod
    def from_client_secrets_file(path: str, scopes: list[str]) -> "FlowApi":
        FlowApi.calls.append(("secrets", path, list(scopes)))
        return FlowApi()

    def run_local_server(self, **kwargs: object) -> FakeCreds:
        FlowApi.calls.append(("server", kwargs))
        return FlowApi.result


def oauth_modules() -> tuple[object, object, object, type[BaseException]]:
    return (lambda: "request", CredentialsApi, FlowApi, RefreshError)


class LoadCredentialsTests(unittest.TestCase):
    def setUp(self) -> None:
        CredentialsApi.instance = None
        CredentialsApi.seen = None
        FlowApi.calls = []
        FlowApi.result = FakeCreds(valid=True)
        FlowApi.result.payload = "consented"
        FakeCreds.refresh_calls = []
        self.patcher = patch.object(auth, "_oauth_modules", oauth_modules)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()

    def test_valid_token_is_returned_without_refresh_or_consent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "token.json"
            token.write_text("original", encoding="utf-8")
            saved = FakeCreds(valid=True)
            CredentialsApi.instance = saved
            loaded = auth.load_credentials(Path(tmp) / "missing.json", token, DRIVE_SCOPE)
            self.assertEqual(token.read_text(encoding="utf-8"), "original")
        self.assertIs(loaded, saved)
        self.assertEqual(CredentialsApi.seen[1], DRIVE_SCOPE)
        self.assertEqual(FlowApi.calls, [])

    def test_expired_token_refreshes_and_saves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "google" / "token.json"
            token.parent.mkdir()
            token.write_text("old", encoding="utf-8")
            saved = FakeCreds(valid=False, expired=True, refresh_token="rt")
            saved.payload = "refreshed-json"
            CredentialsApi.instance = saved
            loaded = auth.load_credentials(Path(tmp) / "credentials.json", token, DRIVE_SCOPE)
            self.assertEqual(token.read_text(encoding="utf-8"), "refreshed-json")
        self.assertIs(loaded, saved)
        self.assertEqual(FakeCreds.refresh_calls, ["request"])
        self.assertEqual(FlowApi.calls, [])

    def test_refresh_failure_message_exits_before_consent(self) -> None:
        class Expired(FakeCreds):
            def refresh(self, request: object) -> None:
                raise RefreshError("rejected")

        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "token.json"
            token.write_text("old", encoding="utf-8")
            CredentialsApi.instance = Expired(valid=False, expired=True, refresh_token="rt")
            with self.assertRaises(SystemExit) as caught:
                auth.load_credentials(
                    Path(tmp) / "credentials.json",
                    token,
                    DRIVE_SCOPE,
                    refresh_failure_message="refresh failed",
                )
            self.assertEqual(str(caught.exception), "refresh failed")
            self.assertEqual(token.read_text(encoding="utf-8"), "old")
        self.assertEqual(FlowApi.calls, [])

    def test_other_refresh_errors_propagate(self) -> None:
        class Expired(FakeCreds):
            def refresh(self, request: object) -> None:
                raise OtherFailureError("offline")

        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "token.json"
            token.write_text("old", encoding="utf-8")
            CredentialsApi.instance = Expired(valid=False, expired=True, refresh_token="rt")
            with self.assertRaises(OtherFailureError):
                auth.load_credentials(Path(tmp) / "c.json", token, DRIVE_SCOPE)
        self.assertEqual(FlowApi.calls, [])

    def test_missing_token_runs_consent_with_offline_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            creds = Path(tmp) / "credentials.json"
            creds.write_text("{}", encoding="utf-8")
            token = Path(tmp) / "google" / "token.json"
            loaded = auth.load_credentials(creds, token, DRIVE_SCOPE)
            self.assertEqual(token.read_text(encoding="utf-8"), "consented")
        self.assertIs(loaded, FlowApi.result)
        self.assertEqual(FlowApi.calls[0], ("secrets", str(creds), DRIVE_SCOPE))
        self.assertEqual(
            FlowApi.calls[1],
            ("server", {"port": 0, "access_type": "offline", "prompt": "consent"}),
        )

    def test_interactive_false_does_not_start_consent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            creds = Path(tmp) / "credentials.json"
            creds.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                auth.load_credentials(
                    creds,
                    Path(tmp) / "token.json",
                    DRIVE_SCOPE,
                    interactive=False,
                )
        self.assertIn("interactive sign-in is disabled", str(caught.exception))
        self.assertEqual(FlowApi.calls, [])

    def test_missing_client_file_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as caught:
                auth.load_credentials(
                    Path(tmp) / "credentials.json",
                    Path(tmp) / "token.json",
                    DRIVE_SCOPE,
                )
        self.assertIn("Missing OAuth client file", str(caught.exception))
        self.assertEqual(FlowApi.calls, [])

    def test_force_consent_ignores_a_valid_token_and_passes_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            creds = Path(tmp) / "credentials.json"
            creds.write_text("{}", encoding="utf-8")
            token = Path(tmp) / "token.json"
            token.write_text("original", encoding="utf-8")
            CredentialsApi.instance = FakeCreds(valid=True)
            auth.load_credentials(
                creds,
                token,
                write_tab.SCOPES,
                force_consent=True,
                timeout_seconds=300,
            )
            self.assertEqual(token.read_text(encoding="utf-8"), "consented")
        self.assertIsNone(CredentialsApi.seen)
        self.assertEqual(FlowApi.calls[0][2], list(write_tab.SCOPES))
        self.assertEqual(FlowApi.calls[1][1]["timeout_seconds"], 300)
        self.assertEqual(FlowApi.calls[1][1]["prompt"], "consent")


class CallerTests(unittest.TestCase):
    def test_writer_keeps_its_scopes_and_refresh_message(self) -> None:
        with patch("msjc_board_secretary.auth.load_credentials", return_value="token") as load:
            self.assertEqual(write_tab.load_credentials(Path("c"), Path("t")), "token")
        self.assertEqual(load.call_args.args, (Path("c"), Path("t"), write_tab.SCOPES))
        self.assertEqual(load.call_args.kwargs["refresh_failure_message"], write_tab.REAUTH_MESSAGE)
        self.assertEqual(
            write_tab.DEFAULT_TOKEN,
            write_tab.REPO_ROOT / "Sensitive" / "google" / "gdocs_token.json",
        )
        self.assertEqual(
            write_tab.DEFAULT_CREDS,
            write_tab.REPO_ROOT / "Sensitive" / "credentials.json",
        )

    def test_docs_mcp_stays_on_the_writer_token(self) -> None:
        with (
            patch.object(docs_mcp, "load_credentials", return_value="token") as load,
            patch.object(docs_mcp, "build_docs_service", return_value="service") as build,
        ):
            self.assertEqual(docs_mcp.docs_service(), "service")
        build.assert_called_once_with("token")
        self.assertEqual(
            load.call_args.args,
            (write_tab.DEFAULT_CREDS, write_tab.DEFAULT_TOKEN, write_tab.SCOPES),
        )
        self.assertEqual(load.call_args.kwargs["refresh_failure_message"], write_tab.REAUTH_MESSAGE)
        self.assertNotIn("update_doc", {tool["name"] for tool in docs_mcp.TOOLS})

    def test_reauth_forces_consent_on_the_writer_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            creds = Path(tmp) / "credentials.json"
            creds.write_text("{}", encoding="utf-8")
            token = Path(tmp) / "gdocs_token.json"
            bad = Path(tmp) / "gdocs_token.bad.json"
            bad.write_text("bad", encoding="utf-8")
            with (
                patch.object(reauth, "DEFAULT_CREDS", creds),
                patch.object(reauth, "DEFAULT_TOKEN", token),
                patch.object(reauth, "load_credentials") as load,
                redirect_stdout(io.StringIO()) as stdout,
            ):
                reauth.main()
            self.assertEqual(stdout.getvalue().strip(), "token saved")
            self.assertFalse(bad.exists())
        self.assertEqual(load.call_args.args, (creds, token, write_tab.SCOPES))
        self.assertTrue(load.call_args.kwargs["force_consent"])
        self.assertTrue(load.call_args.kwargs["interactive"])
        self.assertEqual(load.call_args.kwargs["timeout_seconds"], reauth.WAIT_SECONDS)

    def test_reauth_timeout_leaves_the_token_file(self) -> None:
        class SignInTimeoutError(Exception):
            pass

        with tempfile.TemporaryDirectory() as tmp:
            creds = Path(tmp) / "credentials.json"
            creds.write_text("{}", encoding="utf-8")
            token = Path(tmp) / "gdocs_token.json"
            token.write_text("old", encoding="utf-8")
            with (
                patch.object(reauth, "DEFAULT_CREDS", creds),
                patch.object(reauth, "DEFAULT_TOKEN", token),
                patch.object(reauth, "_sign_in_timeout_type", return_value=SignInTimeoutError),
                patch.object(reauth, "load_credentials", side_effect=SignInTimeoutError("closed")),
            ):
                with self.assertRaises(SystemExit) as caught:
                    reauth.main()
            self.assertIn("No sign-in arrived", str(caught.exception))
            self.assertEqual(token.read_text(encoding="utf-8"), "old")
