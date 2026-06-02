"""Global seed control — same shape as ml.sustainability.reproducibility.seed."""

from __future__ import annotations

import os
import random


def seed_everything(seed: int = 42) -> None:
    """Seed every PRNG that affects training outcomes.

    Idempotent. Heavy libs are imported lazily so the function still
    works in environments where they're absent (CI lint, dev venv)."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    try:  # pragma: no cover - optional dep
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass
