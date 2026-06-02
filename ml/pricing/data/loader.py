"""
Pricing data loader — synthetic + JSONL paths.

Mirror of `ml.recruitment.data.loader`:
  • `load_synthetic()` adapts the synthetic generator in
    `ml/data/synthetic/generators.py:generate_pricing` into the `Product`
    + `PriceObservation` schema; deterministic.
  • `load_jsonl()` ingests one observation per line for real customer data.

The `PricingDataset` value type exposes deterministic train/val/test
splits keyed on `(product_id, seed)` so adding new products never
reshuffles existing ones.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ml.pricing.data.schema import PriceObservation, Product


@dataclass
class PricingDataset:
    """Container for a list of observations with reproducible splits."""

    observations: list[PriceObservation]
    products: dict[str, Product]
    name: str = "unnamed"

    def __len__(self) -> int:
        return len(self.observations)

    def __iter__(self) -> Iterator[PriceObservation]:
        return iter(self.observations)

    def split(
        self,
        train: float = 0.7,
        val: float = 0.15,
        seed: int = 42,
    ) -> tuple[PricingDataset, PricingDataset, PricingDataset]:
        """Hash-based split — repeated calls produce identical partitions, and
        adding new observations won't reshuffle existing ones. The bucket key
        is `(product_id, price)` so a single product's observations get
        spread across splits proportionally."""
        if not 0 < train < 1 or not 0 <= val < 1 or train + val >= 1:
            raise ValueError("Invalid split proportions")

        def bucket(obs: PriceObservation) -> float:
            key = f"{seed}:{obs.product_id}:{obs.price:.4f}".encode()
            return int(hashlib.sha256(key).hexdigest()[:8], 16) / 0xFFFFFFFF

        tr: list[PriceObservation] = []
        va: list[PriceObservation] = []
        te: list[PriceObservation] = []
        for obs in self.observations:
            b = bucket(obs)
            if b < train:
                tr.append(obs)
            elif b < train + val:
                va.append(obs)
            else:
                te.append(obs)
        return (
            PricingDataset(tr, self.products, f"{self.name}/train"),
            PricingDataset(va, self.products, f"{self.name}/val"),
            PricingDataset(te, self.products, f"{self.name}/test"),
        )

    def by_product(self, product_id: str) -> list[PriceObservation]:
        return [o for o in self.observations if o.product_id == product_id]

    def prices(self) -> np.ndarray:
        return np.asarray([o.price for o in self.observations], dtype=np.float64)

    def demands(self) -> np.ndarray:
        return np.asarray([o.demand for o in self.observations], dtype=np.float64)


class PricingDataLoader:
    """Synthetic path is the canonical fixture for CI / ablation; JSONL is
    the production entry point once partner pricing data exists."""

    def load_synthetic(
        self,
        n_observations: int = 3_000,
        seed: int = 42,
    ) -> PricingDataset:
        from ml.data.synthetic.generators import generate_pricing

        df = generate_pricing(n=n_observations, seed=seed)

        # The synthetic generator emits per-row prices; group into products
        # by binning the base price. Real ingestion supplies real `product_id`.
        rng = np.random.default_rng(seed)
        n_products = 20
        product_ids = [f"sku-{i:03d}" for i in range(n_products)]
        # Stable assignment: a row's product is determined by its row index
        # mod n_products so re-running with the same seed → same partition.
        df = df.reset_index(drop=True)
        df["product_id"] = [product_ids[i % n_products] for i in range(len(df))]

        # Build the Product map.
        products: dict[str, Product] = {}
        for pid in product_ids:
            sub = df[df["product_id"] == pid]
            if len(sub) == 0:
                continue
            avg_competitor = float(sub["competitor_price"].mean())
            avg_price = float(sub["price"].mean())
            products[pid] = Product(
                product_id=pid,
                category="synthetic",
                unit_cost=float(rng.uniform(2, 10)),
                current_price=avg_price,
                competitor_prices=(avg_competitor,),
                seasonal_factor=1.0,
            )

        # Build observations.
        observations: list[PriceObservation] = []
        for _, row in df.iterrows():
            observations.append(
                PriceObservation(
                    product_id=str(row["product_id"]),
                    price=float(row["price"]),
                    demand=float(row["demand"]),
                    season=int(row["season"]),
                    competitor_price=float(row["competitor_price"]),
                    promotion=False,
                )
            )

        return PricingDataset(observations, products, name="synthetic")

    def load_jsonl(self, path: str | Path) -> PricingDataset:
        """Read a JSONL file where each line is one observation record.

        Format:
            {"product_id": ..., "price": ..., "demand": ...,
             "season": ..., "competitor_price": ..., "promotion": ...}

        Products are derived from the observations (one per unique
        `product_id`); supply a separate products file path or override
        for richer product metadata.
        """
        path = Path(path)
        observations: list[PriceObservation] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                observations.append(
                    PriceObservation(
                        product_id=str(rec["product_id"]),
                        price=float(rec["price"]),
                        demand=float(rec["demand"]),
                        season=int(rec.get("season", 0)),
                        competitor_price=rec.get("competitor_price"),
                        promotion=bool(rec.get("promotion", False)),
                        timestamp=rec.get("timestamp"),
                    )
                )

        # Build a minimal Product map from the observations (means).
        products: dict[str, Product] = {}
        ids = {o.product_id for o in observations}
        for pid in ids:
            sub = [o for o in observations if o.product_id == pid]
            avg_price = float(np.mean([o.price for o in sub]))
            comp = [o.competitor_price for o in sub if o.competitor_price is not None]
            products[pid] = Product(
                product_id=pid,
                current_price=avg_price,
                competitor_prices=(float(np.mean(comp)),) if comp else (),
            )
        return PricingDataset(observations, products, name=path.stem)
