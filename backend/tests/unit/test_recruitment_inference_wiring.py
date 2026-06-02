"""Offline tests for the recruitment inference orchestrator.

We inject a hand-rolled `RankingModel` stub so the test doesn't touch
SBERT / XGBoost / torch. This verifies the wiring (request translation
→ ranker call → response translation) without booting the ML chain.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

pytest.importorskip("ml.recruitment.models.base")

from ml.recruitment.models.base import RankingModel, ScoreDetail  # noqa: E402
from src.api.v1.schemas.recruitment import (  # noqa: E402
    CandidateInput,
    JobDescriptionInput,
    RecruitmentAnalysisRequest,
)
from src.services.recruitment.inference import (  # noqa: E402
    RecruitmentInferenceClient,
    get_inference_client,
    reset_inference_client,
)

# ── Stub ranker — deterministic score per candidate ───────────────


class StubRanker(RankingModel):
    """Returns score = len(cv_text) / 100. Pure stdlib."""

    requires_training = False

    @property
    def name(self) -> str:
        return "stub-ranker"

    def fit(self, pairs):
        return self

    def score(self, jd, candidates):
        import numpy as np

        return np.asarray([len(c.cv_text or "") / 100.0 for c in candidates], dtype=float)

    def score_with_detail(self, jd, candidates):
        scores = self.score(jd, candidates)
        return [
            ScoreDetail(
                candidate_id=c.candidate_id,
                score=float(s),
                sub_scores={"semantic": float(s) * 0.6, "structured": float(s) * 0.4},
                features={"years_experience": 5.0, "education_rank": 1},
            )
            for c, s in zip(candidates, scores, strict=False)
        ]


@pytest.fixture(autouse=True)
def _clear_client():
    """Each test starts with a fresh singleton."""
    reset_inference_client(None)
    yield
    reset_inference_client(None)


def _request(n: int = 3, anonymize: bool = True) -> RecruitmentAnalysisRequest:
    return RecruitmentAnalysisRequest(
        job_description=JobDescriptionInput(
            title="ML Engineer",
            description="Description text that meets the 50 character minimum length OK.",
            required_skills=["python", "ml"],
            preferred_skills=["pytorch"],
        ),
        candidates=[
            CandidateInput(
                candidate_id=f"cand-{i:03d}",
                cv_text="X" * (50 + i * 5),  # length differs per candidate
                name=f"Person {i}",
            )
            for i in range(n)
        ],
        anonymize_names=anonymize,
        protected_attributes=["gender"],
        top_k=2,
    )


def test_inference_client_returns_sorted_ranking():
    client = RecruitmentInferenceClient(ranker=StubRanker())
    out = client.score_candidates(_request(n=4))
    # Ranks must be 1..N descending by score.
    assert [r.rank for r in out] == [1, 2, 3, 4]
    scores = [r.composite_score for r in out]
    assert scores == sorted(scores, reverse=True)


def test_inference_client_respects_anonymisation():
    client = RecruitmentInferenceClient(ranker=StubRanker())
    out = client.score_candidates(_request(n=2, anonymize=True))
    assert all(r.display_name is None for r in out)

    client2 = RecruitmentInferenceClient(ranker=StubRanker())
    out2 = client2.score_candidates(_request(n=2, anonymize=False))
    assert {r.display_name for r in out2} == {"Person 0", "Person 1"}


def test_get_inference_client_is_singleton():
    a = get_inference_client()
    b = get_inference_client()
    assert a is b


def test_reset_inference_client_replaces_singleton():
    sentinel = RecruitmentInferenceClient(ranker=StubRanker())
    reset_inference_client(sentinel)
    assert get_inference_client() is sentinel


def test_inference_source_for_injected_ranker_does_not_change_to_mlflow():
    """When a ranker is injected the loader path is never taken."""
    client = RecruitmentInferenceClient(ranker=StubRanker())
    # First call should not flip `_source` because injected rangers bypass _load_ranker.
    client.score_candidates(_request(n=1))
    assert client.source == "uninitialised"


# ── Schema-side smoke for the stub: confirms the translator handles
#    a ranker whose `features` dict is sparse. ────────────────────────


def test_inference_handles_sparse_features():
    class SparseRanker(StubRanker):
        def score_with_detail(self, jd, candidates: Any):
            return [
                ScoreDetail(
                    candidate_id=c.candidate_id,
                    score=0.5,
                    sub_scores={"semantic": 0.5},  # no "structured"
                    features={},  # no education_rank, no years_experience
                )
                for c in candidates
            ]

    client = RecruitmentInferenceClient(ranker=SparseRanker())
    out = client.score_candidates(_request(n=2))
    assert all(r.structured_score == 0.0 for r in out)
    assert all(r.years_experience is None for r in out)
    assert all(r.education_level is None for r in out)


# ── TASK-049 / FE-016 wave 3a: LIME wired into the ranking response ──


def test_lime_features_empty_when_no_xgb_or_background_captured():
    """A stub ranker injection leaves `_xgb_ranker` + `_lime_background`
    as None. The client must still serve the response cleanly; LIME just
    stays empty per candidate."""
    client = RecruitmentInferenceClient(ranker=StubRanker())
    out = client.score_candidates(_request(n=3))
    assert all(r.top_lime_features == [] for r in out)


def test_lime_features_populated_from_stub_explainer():
    """Inject a hand-rolled LIME explainer so the client's wave-3a
    plumbing can be tested without booting the real `lime` chain.

    Asserts: per-candidate dict keyed by candidate_id; rule-style
    feature names + magnitudes flow into `top_lime_features` with
    rank 1..N; the SHAP path is unaffected."""
    pytest.importorskip("numpy")
    import numpy as np

    from ml.recruitment.explainability.lime_adapter import (
        LIMEExplanation,
        LIMERule,
    )

    captured_args: list[tuple[Any, str]] = []

    class StubLIMEExplainer:
        def explain(self, x, candidate_id: str = "", num_features: int = 5):
            captured_args.append((np.asarray(x).copy(), candidate_id))
            # Two synthetic rules so we can assert rank assignment + signs.
            return LIMEExplanation(
                candidate_id=candidate_id,
                predicted_proba=0.7,
                rules=(
                    LIMERule(condition="years_experience > 5", weight=0.31),
                    LIMERule(condition="required_skill_overlap <= 0.3", weight=-0.12),
                ),
            )

    class StubXGB:
        # Minimal duck-type so `_get_lime_explainer` doesn't degrade
        # to None. The real `LIMERecruitmentExplainer.__init__` doesn't
        # *use* the ranker until `explain()` — which we're stubbing —
        # so this stays untouched.
        name = "stub-xgb"

    client = RecruitmentInferenceClient(ranker=StubRanker())
    # Wire the wave-3a singletons directly (bypassing the real
    # `_load_ranker` → `_reconstruct_ensemble_from_result` chain).
    client._xgb_ranker = StubXGB()  # type: ignore[assignment]
    client._lime_background = np.zeros((4, 3), dtype=float)
    client._lime_explainer = StubLIMEExplainer()  # type: ignore[assignment]

    out = client.score_candidates(_request(n=2))

    # Both candidates got their rules surfaced.
    assert len(captured_args) == 2
    for result in out:
        assert len(result.top_lime_features) == 2
        # Rules in insertion order = ranks 1..N.
        assert [f.importance_rank for f in result.top_lime_features] == [1, 2]
        # Rule-style feature names (containing a threshold expression).
        names = [f.feature_name for f in result.top_lime_features]
        assert names == [
            "years_experience > 5",
            "required_skill_overlap <= 0.3",
        ]
        # Signs map to contribution_direction.
        assert result.top_lime_features[0].contribution_direction == "positive"
        assert result.top_lime_features[1].contribution_direction == "negative"
        # The SHAP path is unchanged by wave 3a.
        assert isinstance(result.top_shap_features, list)


def test_lime_features_swallow_per_candidate_failures():
    """If the explainer raises on one candidate, the rest of the batch
    still scores cleanly — LIME stays empty for the failing candidate
    rather than tanking the whole response."""
    pytest.importorskip("numpy")
    import numpy as np

    from ml.recruitment.explainability.lime_adapter import (
        LIMEExplanation,
        LIMERule,
    )

    class FlakyLIMEExplainer:
        def __init__(self):
            self._calls = 0

        def explain(self, x, candidate_id: str = "", num_features: int = 5):
            self._calls += 1
            if self._calls % 2 == 0:
                raise RuntimeError("flaky explainer")
            return LIMEExplanation(
                candidate_id=candidate_id,
                predicted_proba=0.6,
                rules=(LIMERule(condition="dummy > 0", weight=0.5),),
            )

    class StubXGB:
        name = "stub-xgb"

    client = RecruitmentInferenceClient(ranker=StubRanker())
    client._xgb_ranker = StubXGB()  # type: ignore[assignment]
    client._lime_background = np.zeros((4, 3), dtype=float)
    client._lime_explainer = FlakyLIMEExplainer()  # type: ignore[assignment]

    out = client.score_candidates(_request(n=4))

    # Half the candidates have LIME, half don't — order depends on
    # rank-sort by score, but counts must add up.
    populated = [r for r in out if r.top_lime_features]
    empty = [r for r in out if not r.top_lime_features]
    assert len(populated) == 2
    assert len(empty) == 2
