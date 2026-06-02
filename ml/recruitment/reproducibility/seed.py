"""Global seed control across numpy + Python + torch + xgboost."""

from __future__ import annotations

import os
import random


def set_global_seed(seed: int = 42, *, deterministic_cudnn: bool = True) -> None:
    """Seed every PRNG that affects training outcomes.

    Idempotent. Heavy libs are imported lazily so the function still works
    in environments where they're absent (CI lint, dev venv).
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if deterministic_cudnn:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass
