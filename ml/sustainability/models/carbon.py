"""
Carbon footprint estimator — Scope 1 / 2 / 3 decomposition.

Closed-form physics-style model. Mirrors what the backend mock service
already does (`backend/src/services/sustainability/sustainability_service.py`
`estimate_carbon`) but lives here so the ML package owns the
coefficients and a future regression-fit refinement can replace the
constants without touching the backend.

Default emission factors are research-grade approximations — every
constant is documented with its provenance so a thesis reviewer can
trace what's empirical vs assumed. A real-data fit will live in
`models/carbon.py.fit()` once the IPCC factor tables are wired in.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ml.sustainability.data.schema import (
    CarbonEstimate,
    CompanyProfile,
    ESGObservation,
)

# Carbon-intensity floor by industry (tCO2e / $1M revenue) — same keys
# as `data.loader.INDUSTRIES`. These match the backend mock's table so
# the flag flip doesn't shift numbers. Replace via fit() when an IPCC
# factor table is wired in.
_INDUSTRY_INTENSITY: dict[str, float] = {
    "manufacturing": 220.0,
    "retail": 60.0,
    "technology": 25.0,
    "logistics": 300.0,
    "agriculture": 180.0,
}
_DEFAULT_INTENSITY = 100.0

# Standard grid-emission factor (kgCO2e / kWh, US average — EIA 2023).
_KG_PER_KWH = 0.40
# Light-duty fleet emissions (kgCO2e / km, EPA 2022).
_KG_PER_KM = 0.17


class CarbonEstimatorModel:
    """Industry-intensity-based carbon scope decomposition.

    Distinct from `ESGScorer` — carbon is a *regression* target with no
    binary label. Following pricing's two-ABC posture, we keep it in
    its own concrete class with its own fit/predict surface.
    """

    requires_training: bool = False

    def __init__(
        self,
        *,
        intensity: dict[str, float] | None = None,
        kg_per_kwh: float = _KG_PER_KWH,
        kg_per_km: float = _KG_PER_KM,
    ) -> None:
        self._intensity = dict(intensity or _INDUSTRY_INTENSITY)
        self._kg_per_kwh = kg_per_kwh
        self._kg_per_km = kg_per_km

    @property
    def name(self) -> str:
        return "CarbonEstimator"

    def fit(self, observations: Sequence[ESGObservation]) -> CarbonEstimatorModel:
        """No-op for the closed-form version.

        A future data-driven fit would re-estimate `_intensity[industry]`
        from observed (industry, revenue, total_tco2e) triples; the
        method signature stays the same so the AS-004 ablation runner
        can swap arms uniformly.
        """
        return self

    def predict(
        self,
        *,
        industry: str,
        annual_revenue: float,
        energy_kwh: float | None = None,
        fleet_km: float | None = None,
    ) -> CarbonEstimate:
        """Compute Scope 1 / 2 / 3 estimates in tCO2e.

        Conversions:
          • kWh × kg_per_kwh / 1000 → tCO2e for Scope 2
          • km  × kg_per_km  / 1000 → tCO2e for Scope 1
          • (revenue / 1M) × industry_intensity → tCO2e for Scope 3
        """
        intensity = self._intensity.get(industry.lower(), _DEFAULT_INTENSITY)
        revenue_millions = annual_revenue / 1_000_000.0
        scope_1 = (fleet_km or 0.0) * self._kg_per_km / 1_000.0
        scope_2 = (energy_kwh or 0.0) * self._kg_per_kwh / 1_000.0
        scope_3 = intensity * revenue_millions
        return CarbonEstimate(
            industry=industry,
            scope_1_tco2e=round(scope_1, 2),
            scope_2_tco2e=round(scope_2, 2),
            scope_3_tco2e=round(scope_3, 2),
        )

    def predict_from_profile(self, profile: CompanyProfile) -> CarbonEstimate:
        """Convenience wrapper — same Scope 1/2/3 with profile shape."""
        # Profile doesn't carry energy / fleet directly; we estimate
        # them from revenue + headcount as a research-grade fallback so
        # the package can score on the synthetic dataset without
        # requiring carbon-specific inputs. The backend's
        # `/carbon-estimate` endpoint takes them explicitly.
        rough_kwh = max(profile.employee_count, 1) * 3_000.0  # ~3 MWh / FTE / yr
        rough_km = max(profile.employee_count, 1) * 12_000.0  # ~12k km / FTE / yr
        return self.predict(
            industry=profile.industry,
            annual_revenue=profile.annual_revenue,
            energy_kwh=rough_kwh,
            fleet_km=rough_km,
        )

    def reduction_pathways(self, estimate: CarbonEstimate) -> tuple[str, ...]:
        """Return the top-3 reduction levers ordered by attributable
        scope share. Deterministic — same `narrative` adapter contract
        as `ml.forecasting.explainability.narrative`."""
        shares = np.array(
            [
                estimate.scope_1_tco2e,
                estimate.scope_2_tco2e,
                estimate.scope_3_tco2e,
            ],
            dtype=np.float64,
        )
        labels = (
            "Electrify or optimise fleet routing",
            "Procure renewable energy (largest Scope 2 lever)",
            "Engage top suppliers on Scope 3 reductions",
        )
        order = np.argsort(-shares)
        return tuple(labels[int(i)] for i in order)
