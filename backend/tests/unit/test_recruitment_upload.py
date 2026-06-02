"""Unit tests for `RecruitmentService.process_cv_uploads` — the
TASK-045 / ML-003 wiring of `ml.recruitment.parsers.ResumeParser`
into the FastAPI `/upload-cvs` endpoint.

We exercise the service layer directly with `UploadFile`-shaped
stubs (an `async read()` + a `filename`) rather than spinning up
the FastAPI test client, because the parsing path doesn't touch
the DB / Redis / Celery — it's a pure-function call against the
process-wide `ResumeParser` singleton.

We deliberately drive the `.txt` parser arm for the happy-path
tests so the suite stays runnable without pypdf / python-docx
installed in the lean CI image. The PDF arm is covered by
`ml.recruitment.tests` against real fixtures.
"""

from __future__ import annotations

import uuid

import pytest

from src.services.recruitment.recruitment_service import RecruitmentService


class _StubUpload:
    """Async file-like duck-type that matches the surface FastAPI's
    `UploadFile` exposes to the service: `.filename` + an `async
    read()` returning bytes. Synchronous bytes returned is fine — the
    service awaits it; the awaitable from a coroutine is enough."""

    def __init__(self, filename: str, payload: bytes) -> None:
        self.filename = filename
        self._payload = payload

    async def read(self) -> bytes:  # noqa: D401
        return self._payload


@pytest.mark.asyncio
async def test_process_cv_uploads_parses_plain_text_into_structured_fields():
    """A plain-text CV with skills + years + a master's degree
    should round-trip through `ResumeParser.parse_file('.txt')` and
    surface the extracted fields in the response."""
    cv_text = (
        "Senior Python engineer with 7 years experience.\n"
        "Strong on PostgreSQL, Docker, Kubernetes, and AWS.\n"
        "M.Sc. Computer Science.\n"
    )
    files = [_StubUpload("alice.txt", cv_text.encode("utf-8"))]

    resp = await RecruitmentService(db=None).process_cv_uploads(
        files, user_id=uuid.uuid4()
    )

    assert resp.count == 1
    assert resp.parsed_count == 1
    [item] = resp.uploaded
    assert item.filename == "alice.txt"
    assert item.source == "text"
    assert item.error is None
    assert item.cv_text == cv_text
    assert item.char_count == len(cv_text)
    # `EntityExtractor` lexicon matches case-insensitively + word-boundary.
    assert set(item.skills) >= {"python", "postgresql", "docker", "kubernetes", "aws"}
    assert item.years_experience == 7.0
    assert item.education_level == "master"


@pytest.mark.asyncio
async def test_process_cv_uploads_flags_unsupported_extensions():
    """A file with no supported extension is rejected with an
    `error` set — but the rest of the batch still processes."""
    ok = _StubUpload(
        "bob.txt",
        b"Junior Python developer with 2 years experience. Django, PostgreSQL.",
    )
    weird = _StubUpload("resume.zip", b"PK\x03\x04")  # zip header bytes; we don't crack it

    resp = await RecruitmentService(db=None).process_cv_uploads(
        [ok, weird], user_id=uuid.uuid4()
    )

    assert resp.count == 2
    assert resp.parsed_count == 1
    by_name = {u.filename: u for u in resp.uploaded}

    assert by_name["bob.txt"].error is None
    assert by_name["bob.txt"].years_experience == 2.0

    assert by_name["resume.zip"].error is not None
    assert "unsupported extension" in by_name["resume.zip"].error
    assert by_name["resume.zip"].cv_text == ""


@pytest.mark.asyncio
async def test_process_cv_uploads_empty_file_is_flagged_not_crashed():
    """A zero-byte upload returns an `error` rather than producing
    an empty-but-otherwise-valid record (avoids the downstream
    SBERT cosine == NaN path on empty text)."""
    files = [_StubUpload("ghost.pdf", b"")]
    resp = await RecruitmentService(db=None).process_cv_uploads(
        files, user_id=uuid.uuid4()
    )
    assert resp.count == 1
    assert resp.parsed_count == 0
    [item] = resp.uploaded
    assert item.error == "empty upload"
    assert item.cv_text == ""


@pytest.mark.asyncio
async def test_process_cv_uploads_returns_uuid_file_ids():
    """Every parsed file gets a synthetic UUID so the frontend can
    refer to a single upload in-flight (e.g. for retry UX) even
    before persistence to MinIO lands."""
    files = [
        _StubUpload(f"cv-{i}.txt", b"Software engineer, 3 years Python.") for i in range(3)
    ]
    resp = await RecruitmentService(db=None).process_cv_uploads(
        files, user_id=uuid.uuid4()
    )
    ids = [u.file_id for u in resp.uploaded]
    assert len(ids) == len(set(ids))  # no collisions
    assert all(isinstance(i, uuid.UUID) for i in ids)
