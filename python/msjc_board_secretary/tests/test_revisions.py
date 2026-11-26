"""Drive revision CLI. Standard library only; no network and no real minutes."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from msjc_board_secretary import revisions  # noqa: E402

DOC_URL = "https://docs.google.com/document/d/abc_DEF-123/edit?usp=sharing"
MODIFIED = "2026-04-12T15:30:00.000Z"


class Response:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


class Session:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def get(self, url: str) -> Response:
        self.urls.append(url)
        return self.responses.pop(0)


class Execute:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.kwargs: dict | None = None

    def execute(self, **kwargs: object) -> dict:
        self.kwargs = kwargs
        return self.payload


class ListApi:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = list(pages)
        self.calls: list[dict] = []
        self.requests: list[Execute] = []

    def list(self, **kwargs: object) -> Execute:
        self.calls.append(kwargs)
        request = Execute(self.pages.pop(0))
        self.requests.append(request)
        return request


class FileApi:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict] = []
        self.requests: list[Execute] = []

    def get(self, **kwargs: object) -> Execute:
        self.calls.append(kwargs)
        request = Execute({"name": self.name})
        self.requests.append(request)
        return request


class Drive:
    def __init__(
        self,
        revision_pages: list[dict] | None = None,
        comment_pages: list[dict] | None = None,
        name: str = "April minutes",
    ) -> None:
        self.revision_api = ListApi(revision_pages or [])
        self.comment_api = ListApi(comment_pages or [])
        self.file_api = FileApi(name)

    def revisions(self) -> ListApi:
        return self.revision_api

    def comments(self) -> ListApi:
        return self.comment_api

    def files(self) -> FileApi:
        return self.file_api


def revision(revision_id: str, links: dict[str, str] | None) -> dict:
    payload = {"id": revision_id, "modifiedTime": MODIFIED}
    if links is not None:
        payload["exportLinks"] = links
    return payload


class DocIdTests(unittest.TestCase):
    def test_doc_id_from_url_or_raw_id(self) -> None:
        self.assertEqual(revisions.doc_id(DOC_URL), "abc_DEF-123")
        self.assertEqual(revisions.doc_id("abc_DEF-123"), "abc_DEF-123")
        self.assertEqual(
            revisions.doc_id("https://docs.google.com/document/d/abc_DEF-123"),
            "abc_DEF-123",
        )

    def test_empty_document_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            revisions.doc_id("   ")
        self.assertIn("empty", str(caught.exception))

    def test_doc_id_rejects_path_characters(self) -> None:
        for value in ("../secret", "/tmp/out", "abc/def", "has space", "id.txt"):
            with self.subTest(value=value):
                with self.assertRaises(SystemExit) as caught:
                    revisions.doc_id(value)
                self.assertIn("letters, digits", str(caught.exception))


class PathAndScopeTests(unittest.TestCase):
    def test_defaults_and_drive_readonly_scope(self) -> None:
        root = revisions.REPO_ROOT
        self.assertEqual(
            revisions.DEFAULT_CREDS, root / "Sensitive" / "credentials.json"
        )
        self.assertEqual(
            revisions.DEFAULT_TOKEN,
            root / "Sensitive" / "google" / "gdocs_token_drive_readonly.json",
        )
        self.assertEqual(
            revisions.DEFAULT_OUT, root / "Sensitive" / "msjc" / "revisions"
        )
        self.assertEqual(
            revisions.SCOPES, ["https://www.googleapis.com/auth/drive.readonly"]
        )
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/Sensitive/**", gitignore)
        self.assertIn("!/Sensitive/README.md", gitignore)


class RevisionListTests(unittest.TestCase):
    def test_pagination_passes_the_page_token_and_fields(self) -> None:
        drive = Drive(
            revision_pages=[
                {"revisions": [revision("1", {})], "nextPageToken": "next"},
                {"revisions": [revision("2", {})]},
            ]
        )
        listed = revisions.list_revisions(drive, "abc_DEF-123")
        self.assertEqual([item["id"] for item in listed], ["1", "2"])
        self.assertEqual(drive.revision_api.calls[0]["pageToken"], None)
        self.assertEqual(drive.revision_api.calls[1]["pageToken"], "next")
        self.assertEqual(drive.revision_api.calls[0]["pageSize"], 1000)
        self.assertEqual(drive.revision_api.calls[0]["fileId"], "abc_DEF-123")
        self.assertIn("exportLinks", drive.revision_api.calls[0]["fields"])
        self.assertNotIn("emailAddress", drive.revision_api.calls[0]["fields"])
        self.assertIn("nextPageToken", drive.revision_api.calls[0]["fields"])
        self.assertEqual(
            drive.revision_api.requests[0].kwargs,
            {"num_retries": revisions.DRIVE_REQUEST_RETRY_COUNT},
        )


class ExportTests(unittest.TestCase):
    def test_filename_uses_the_chosen_mime(self) -> None:
        self.assertEqual(revisions.revision_stamp(MODIFIED), "20260412T153000")
        self.assertEqual(
            revisions.export_filename(MODIFIED, "9", "text/markdown"),
            "20260412T153000_rev9.md",
        )
        self.assertEqual(
            revisions.choose_export_mime(
                {"text/plain": "http://plain"}, "text/markdown"
            ),
            "text/plain",
        )
        self.assertIsNone(revisions.choose_export_mime({}, "text/markdown"))

    def test_export_writes_the_fallback_and_skips_a_missing_link(self) -> None:
        listed = [
            revision("1", {"text/plain": "http://plain"}),
            revision("2", {}),
        ]
        session = Session([Response(200, b"plain-export")])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            stderr = io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                result = revisions.export_revisions(
                    session, "doc", ["1", "2"], "text/markdown", out, listed
                )
            path = out / "doc" / "20260412T153000_rev1.txt"
            self.assertEqual(result.written, [path])
            self.assertEqual(result.skipped, ["2"])
            self.assertEqual(result.failed, [])
            self.assertEqual(path.read_bytes(), b"plain-export")
            self.assertIn("using text/plain", stderr.getvalue())
            self.assertIn("2: no export link", stderr.getvalue())
            self.assertFalse((out / "doc" / "20260412T153000_rev2.bin").exists())
        self.assertEqual(session.urls, ["http://plain"])

    def test_missing_revision_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with self.assertRaises(SystemExit) as caught:
                revisions.export_revisions(
                    Session([]),
                    "doc",
                    ["1", "missing"],
                    "text/markdown",
                    out,
                    [revision("1", {"text/markdown": "http://md"})],
                )
            self.assertIn("missing", str(caught.exception))
            self.assertFalse((out / "doc").exists())

    def test_429_retries_then_writes(self) -> None:
        session = Session([Response(429), Response(200, b"after-retry")])
        listed = [revision("4", {"text/markdown": "http://md"})]
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(revisions.time, "sleep") as sleep,
                redirect_stdout(io.StringIO()),
            ):
                result = revisions.export_revisions(
                    session, "doc", ["4"], "text/markdown", Path(tmp), listed
                )
            self.assertEqual(result.written[0].read_bytes(), b"after-retry")
            self.assertEqual(result.written[0].name, "20260412T153000_rev4.md")
        sleep.assert_called_once_with(5)
        self.assertEqual(session.urls, ["http://md", "http://md"])

    def test_repeated_429_gives_up_after_six_attempts(self) -> None:
        session = Session([Response(429) for _ in range(6)])
        listed = [revision("4", {"text/markdown": "http://md"})]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(revisions.time, "sleep") as sleep:
                with self.assertRaises(RuntimeError):
                    revisions.export_revisions(
                        session, "doc", ["4"], "text/markdown", Path(tmp), listed
                    )
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [5, 10, 20, 40, 80],
        )
        self.assertEqual(session.urls, ["http://md"] * 6)

    def test_http_error_on_one_revision_does_not_abort_the_rest(self) -> None:
        class HttpError(Exception):
            pass

        HttpError.__module__ = "googleapiclient.errors"

        def fetch(session: object, url: str) -> Response:
            del session
            if url == "http://bad":
                raise HttpError("403 rate limit")
            return Response(200, b"kept")

        listed = [
            revision("1", {"text/markdown": "http://bad"}),
            revision("2", {"text/markdown": "http://good"}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with (
                patch.object(revisions, "fetch_export", side_effect=fetch),
                redirect_stderr(stderr),
                redirect_stdout(io.StringIO()),
            ):
                result = revisions.export_revisions(
                    Session([]), "doc", ["1", "2"], "text/markdown", Path(tmp), listed
                )
            path = Path(tmp) / "doc" / "20260412T153000_rev2.md"
            self.assertEqual(result.failed, ["1"])
            self.assertEqual(result.written, [path])
            self.assertEqual(path.read_bytes(), b"kept")
            self.assertIn("403 rate limit", stderr.getvalue())


class CommentTests(unittest.TestCase):
    def test_comments_pagination_writes_replies_as_json(self) -> None:
        drive = Drive(
            comment_pages=[
                {
                    "comments": [
                        {
                            "id": "c1",
                            "content": "fictional remark",
                            "replies": [{"id": "r1", "content": "fictional reply"}],
                        }
                    ],
                    "nextPageToken": "page-2",
                },
                {"comments": [{"id": "c2", "content": "second remark"}]},
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                path = revisions.write_comments(drive, "doc", Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["fileId"], "doc")
        self.assertEqual([item["id"] for item in payload["comments"]], ["c1", "c2"])
        self.assertEqual(
            payload["comments"][0]["replies"][0]["content"], "fictional reply"
        )
        self.assertNotIn("fictional", stdout.getvalue())
        self.assertTrue(stdout.getvalue().strip().endswith("comments.json"))
        self.assertEqual(drive.comment_api.calls[0]["pageToken"], None)
        self.assertEqual(drive.comment_api.calls[1]["pageToken"], "page-2")
        self.assertEqual(drive.comment_api.calls[0]["pageSize"], 100)
        self.assertIn("replies", drive.comment_api.calls[0]["fields"])
        self.assertEqual(drive.comment_api.calls[0]["fields"], revisions.COMMENT_FIELDS)
        self.assertEqual(
            drive.comment_api.requests[0].kwargs,
            {"num_retries": revisions.DRIVE_REQUEST_RETRY_COUNT},
        )


class MainTests(unittest.TestCase):
    def test_list_uses_the_drive_readonly_defaults(self) -> None:
        drive = Drive(
            revision_pages=[
                {
                    "revisions": [
                        {
                            "id": "1",
                            "modifiedTime": MODIFIED,
                            "lastModifyingUser": {"displayName": "Sam Ortiz"},
                        }
                    ]
                }
            ]
        )
        with (
            patch.object(revisions, "load_credentials", return_value="creds") as load,
            patch.object(revisions, "build_drive", return_value=drive) as build,
            patch.object(revisions, "authorized_session") as session,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            code = revisions.main(["list", DOC_URL])
        self.assertEqual(code, 0)
        self.assertFalse(session.called)
        build.assert_called_once_with("creds")
        self.assertEqual(
            load.call_args.args,
            (revisions.DEFAULT_CREDS, revisions.DEFAULT_TOKEN, revisions.SCOPES),
        )
        self.assertTrue(load.call_args.kwargs["interactive"])
        self.assertEqual(
            load.call_args.kwargs["timeout_seconds"],
            revisions.SIGN_IN_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            load.call_args.kwargs["refresh_failure_message"],
            revisions.REFRESH_FAILURE_MESSAGE,
        )
        self.assertEqual(drive.file_api.calls[0]["fileId"], "abc_DEF-123")
        self.assertEqual(
            drive.file_api.requests[0].kwargs,
            {"num_retries": revisions.DRIVE_REQUEST_RETRY_COUNT},
        )
        self.assertIn("Sam Ortiz", stdout.getvalue())
        self.assertIn("1 revisions", stdout.getvalue())

    def test_export_all_and_comment_paths_honor_out_dir(self) -> None:
        markdown = {"text/markdown": "http://md"}
        drive = Drive(
            revision_pages=[{"revisions": [revision("9", markdown)]}],
            comment_pages=[{"comments": [{"id": "c1", "content": "kept on disk"}]}],
        )
        session = Session([Response(200, b"export-bytes")])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            creds = out / "credentials.json"
            token = out / "token.json"
            with (
                patch.object(
                    revisions, "load_credentials", return_value="creds"
                ) as load,
                patch.object(revisions, "build_drive", return_value=drive),
                patch.object(revisions, "authorized_session", return_value=session),
                redirect_stdout(io.StringIO()),
            ):
                code = revisions.main(
                    [
                        "--creds",
                        str(creds),
                        "--token",
                        str(token),
                        "--out",
                        str(out),
                        "export",
                        "raw-doc",
                        "--all",
                    ]
                )
            self.assertEqual(code, 0)
            exported = out / "raw-doc" / "20260412T153000_rev9.md"
            self.assertEqual(exported.read_bytes(), b"export-bytes")
            self.assertEqual(load.call_args.args[0], creds)
            self.assertEqual(load.call_args.args[1], token)
            with (
                patch.object(revisions, "load_credentials", return_value="creds"),
                patch.object(revisions, "build_drive", return_value=drive),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                code = revisions.main(
                    [
                        "--creds",
                        str(creds),
                        "--token",
                        str(token),
                        "--out",
                        str(out),
                        "comments",
                        "raw-doc",
                    ]
                )
            self.assertEqual(code, 0)
            comments = json.loads(
                (out / "raw-doc" / "comments.json").read_text(encoding="utf-8")
            )
            self.assertEqual(comments["comments"][0]["id"], "c1")
            self.assertNotIn("kept on disk", stdout.getvalue())

    def test_export_requires_ids_or_all_before_credentials(self) -> None:
        with patch.object(revisions, "load_credentials") as load:
            with self.assertRaises(SystemExit) as caught:
                revisions.main(["export", "raw-doc"])
        self.assertIn("Pass revision ids or --all", str(caught.exception))
        self.assertFalse(load.called)

    def test_list_prints_unknown_when_the_display_name_is_missing(self) -> None:
        drive = Drive(
            revision_pages=[
                {
                    "revisions": [
                        {
                            "id": "1",
                            "modifiedTime": MODIFIED,
                            "lastModifyingUser": {"emailAddress": "member@example.com"},
                        }
                    ]
                }
            ]
        )
        with (
            patch.object(revisions, "load_credentials", return_value="creds"),
            patch.object(revisions, "build_drive", return_value=drive),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            code = revisions.main(["list", "raw-doc"])
        self.assertEqual(code, 0)
        self.assertIn("unknown", stdout.getvalue())
        self.assertNotIn("member@example.com", stdout.getvalue())
        self.assertNotIn("emailAddress", revisions.REVISION_FIELDS)

    def test_export_all_with_ids_exits_before_credentials(self) -> None:
        with patch.object(revisions, "load_credentials") as load:
            with self.assertRaises(SystemExit) as caught:
                revisions.main(["export", "raw-doc", "1", "--all"])
        self.assertIn("not both", str(caught.exception))
        self.assertFalse(load.called)

    def test_invalid_doc_id_exits_before_credentials(self) -> None:
        with patch.object(revisions, "load_credentials") as load:
            with self.assertRaises(SystemExit) as caught:
                revisions.main(["list", "../secret"])
        self.assertIn("letters, digits", str(caught.exception))
        self.assertFalse(load.called)

    def test_incomplete_export_exits_nonzero(self) -> None:
        listed = [
            revision("1", {"text/plain": "http://plain"}),
            revision("2", {}),
        ]
        drive = Drive(revision_pages=[{"revisions": listed}])
        session = Session([Response(200, b"plain-export")])
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with (
                patch.object(revisions, "load_credentials", return_value="creds"),
                patch.object(revisions, "build_drive", return_value=drive),
                patch.object(revisions, "authorized_session", return_value=session),
                redirect_stdout(io.StringIO()),
                redirect_stderr(stderr),
            ):
                code = revisions.main(
                    ["export", "raw-doc", "--all", "--mime", "text/markdown"]
                )
        self.assertEqual(code, 1)
        self.assertIn("Wrote 1 of 2 revisions; skipped 1; failed 0.", stderr.getvalue())

    def test_failed_revision_export_exits_nonzero(self) -> None:
        class HttpError(Exception):
            pass

        HttpError.__module__ = "googleapiclient.errors"
        listed = [revision("1", {"text/markdown": "http://md"})]
        drive = Drive(revision_pages=[{"revisions": listed}])
        stderr = io.StringIO()
        with (
            patch.object(revisions, "load_credentials", return_value="creds"),
            patch.object(revisions, "build_drive", return_value=drive),
            patch.object(revisions, "authorized_session", return_value=Session([])),
            patch.object(revisions, "fetch_export", side_effect=HttpError("500")),
            redirect_stderr(stderr),
            redirect_stdout(io.StringIO()),
        ):
            code = revisions.main(["export", "raw-doc", "--all"])
        self.assertEqual(code, 1)
        self.assertIn("Wrote 0 of 1 revisions; skipped 0; failed 1.", stderr.getvalue())

    def test_drive_http_error_exits_nonzero_without_a_traceback(self) -> None:
        class HttpError(Exception):
            pass

        HttpError.__module__ = "googleapiclient.errors"
        stderr = io.StringIO()
        with (
            patch.object(revisions, "load_credentials", return_value="creds"),
            patch.object(
                revisions, "build_drive", side_effect=HttpError("404 missing")
            ),
            redirect_stderr(stderr),
        ):
            code = revisions.main(["list", "raw-doc"])
        self.assertEqual(code, 1)
        message = stderr.getvalue()
        self.assertIn("Drive request failed: 404 missing", message)
        self.assertNotIn("Traceback", message)

    def test_sign_in_timeout_exits_before_drive_calls(self) -> None:
        class WSGITimeoutError(Exception):
            pass

        with (
            patch.object(
                revisions, "load_credentials", side_effect=WSGITimeoutError("closed")
            ),
            patch.object(revisions, "build_drive") as build,
        ):
            with self.assertRaises(SystemExit) as caught:
                revisions.main(["list", "raw-doc"])
        self.assertIn("No sign-in arrived", str(caught.exception))
        self.assertFalse(build.called)

    def test_export_all_with_no_revisions_exits(self) -> None:
        drive = Drive(revision_pages=[{"revisions": []}])
        with (
            patch.object(revisions, "load_credentials", return_value="creds"),
            patch.object(revisions, "build_drive", return_value=drive),
        ):
            with self.assertRaises(SystemExit) as caught:
                revisions.main(["export", "raw-doc", "--all"])
        self.assertIn("no revisions", str(caught.exception))
