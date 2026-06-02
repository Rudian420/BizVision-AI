"""
Multi-format resume parser → `CandidateRecord`.

Format dispatch by file suffix:
   .pdf  → pypdf
   .docx → python-docx
   .txt  → plain UTF-8

Both heavy libraries are lazy-imported so the module imports cleanly even
in environments where they aren't installed (tests, dev venv, CI lint).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from ml.recruitment.data.schema import CandidateRecord, ProtectedAttributes
from ml.recruitment.parsers.entity_extractor import EntityExtractor


class ResumeParser:
    def __init__(self, extractor: EntityExtractor | None = None) -> None:
        self._extractor = extractor or EntityExtractor()

    # ── public API ──────────────────────────────────────────────────
    def parse_file(
        self,
        path: str | Path,
        *,
        candidate_id: str | None = None,
        protected: ProtectedAttributes | None = None,
    ) -> CandidateRecord:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            text = self._read_pdf(path)
            source = "pdf"
        elif suffix in (".docx", ".doc"):
            text = self._read_docx(path)
            source = "docx"
        elif suffix == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
            source = "text"
        else:
            raise ValueError(f"Unsupported resume format: {suffix}")
        return self.parse_text(
            text,
            candidate_id=candidate_id,
            protected=protected,
            source=source,
        )

    def parse_text(
        self,
        text: str,
        *,
        candidate_id: str | None = None,
        protected: ProtectedAttributes | None = None,
        source: str = "text",
    ) -> CandidateRecord:
        entities = self._extractor.extract(text)
        return CandidateRecord(
            candidate_id=candidate_id or f"cand-{uuid.uuid4().hex[:10]}",
            cv_text=text,
            years_experience=entities.years_experience,
            skills=entities.skills,
            education_level=entities.education_level,
            protected=protected or ProtectedAttributes(),
            source=source,
        )

    # ── private readers ─────────────────────────────────────────────
    @staticmethod
    def _read_pdf(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PDF parsing requires `pypdf`. Install with `pip install pypdf`."
            ) from exc
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    @staticmethod
    def _read_docx(path: Path) -> str:
        try:
            import docx  # python-docx package
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "DOCX parsing requires `python-docx`. Install with `pip install python-docx`."
            ) from exc
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
