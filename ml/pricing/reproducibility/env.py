"""Environment capture — library versions + git SHA + platform.

Attached as MLflow tags so every pricing experiment reproducibly
identifies its toolchain."""

from __future__ import annotations

import importlib
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version

_TRACKED_PACKAGES: tuple[str, ...] = (
    "numpy",
    "pandas",
    "scikit-learn",
    "lightgbm",
    "torch",
    "gymnasium",
    "stable-baselines3",
    "shap",
    "mlflow",
)


def capture_environment() -> dict[str, str]:
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
