"""Resume parsing — PDF / DOCX / plain-text → CandidateRecord."""

from ml.recruitment.parsers.entity_extractor import EntityExtractor
from ml.recruitment.parsers.resume_parser import ResumeParser

__all__ = ["EntityExtractor", "ResumeParser"]
