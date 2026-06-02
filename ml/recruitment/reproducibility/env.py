"""
Environment capture — library versions, Python version, OS, git SHA.

The output dict is small enough to attach as MLflow tags so every
experiment in the registry reproducibly identifies its toolchain.
"""

from __future__ import annotations

import importlib
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version

_TRACKED_PACKAGES: tuple[str, ...] = (
    "numpy",
    "pandas",
    "scikit-learn",
    "xgboost",
    "lightgbm",
    "torch",
    "sentence-transformers",
    "transformers",
    "shap",
    "lime",
    "fairlearn",
    "aif360",
    "mlflow",
)


def capture_environment() -> dict[str, str]:
    """Return a flat string→string map of versions + environment."""
    out: dict[str, str] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for pkg in _TRACKED_PACKAGES:
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            out[pkg] = "not-installed"

    out["git_sha"] = _git_sha() or "unknown"
    out["cuda"] = _cuda_version()
    return out


def _git_sha() -> str | None:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        return sha or None
    except Exception:
        return None


def _cuda_version() -> str:
    try:
        torch = importlib.import_module("torch")
        if torch.cuda.is_available():
            return torch.version.cuda or "cuda"
        return "cpu"
    except Exception:
        return "cpu"
