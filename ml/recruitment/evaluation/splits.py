"""Helpers for grouping eval data by query (job)."""

from __future__ import annotations

from collections.abc import Sequence

from ml.recruitment.data.schema import Pair


def group_by_query(pairs: Sequence[Pair]) -> dict[str, list[Pair]]:
    """Group a list of pairs by job_id (= query). Preserves the input
    insertion order within each group for reproducibility."""
    groups: dict[str, list[Pair]] = {}
    for p in pairs:
        groups.setdefault(p.job.job_id, []).append(p)
    return groups
