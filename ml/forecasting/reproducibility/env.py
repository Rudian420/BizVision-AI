"""Environment snapshot — captured into every MLflow run."""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone


def capture_env_snapshot() -> dict[str, str]:
    """Return a JSON-serialisable dict describing the current env.

    Logged as MLflow params on every training run so a future re-run can
    inspect *exactly* the Python / numpy / OS versions that produced a
    given checkpoint.
    """
    snapshot: dict[str, str] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    try:
        import numpy as np

        snapshot["numpy_version"] = np.__version__
    except ImportError:
        snapshot["numpy_version"] = "absent"
    try:  # pragma: no cover - optional dep
        import pandas as pd

        snapshot["pandas_version"] = pd.__version__
    except ImportError:
        snapshot["pandas_version"] = "absent"
    return snapshot
