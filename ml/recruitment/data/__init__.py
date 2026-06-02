"""Data schemas + reproducible loaders for Recruitment Intelligence."""

from ml.recruitment.data.loader import RecruitmentDataLoader, RecruitmentDataset
from ml.recruitment.data.schema import (
    CandidateRecord,
    JobDescription,
    Pair,
    ProtectedAttributes,
)

__all__ = [
    "CandidateRecord",
    "JobDescription",
    "Pair",
    "ProtectedAttributes",
    "RecruitmentDataLoader",
    "RecruitmentDataset",
]
