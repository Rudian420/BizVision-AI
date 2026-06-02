"""
BizVision AI — Generate synthetic datasets for all modules.

    python -m ml.data.synthetic.generate_all [--out data/processed]

Writes one Parquet file per module (CSV fallback if pyarrow is unavailable).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ml.data.synthetic.generators import GENERATORS


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ML datasets")
    parser.add_argument("--out", default="data/processed", help="output directory")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for module, generate in GENERATORS.items():
        df = generate(seed=args.seed)
        target = out_dir / f"{module}.parquet"
        try:
            df.to_parquet(target, index=False)
        except Exception:  # pyarrow/fastparquet missing → CSV fallback
            target = out_dir / f"{module}.csv"
            df.to_csv(target, index=False)
        print(f"[data] {module}: {len(df):>5} rows -> {target}")

    print("[data] Synthetic data generation complete.")


if __name__ == "__main__":
    main()
