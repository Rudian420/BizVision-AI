"""
Content-hash keyed embedding cache.

We frequently re-embed the same text (a JD scored against many candidate
pools, or a CV ranked against many JDs across an ablation run). The cache
turns those repeats into O(1) lookups.

Layout: `~/.cache/bizvision/embeddings/{encoder_name}/{sha256[:2]}/{sha256}.npy`
— two-letter shard keeps the directory size sane even with 100K files.

In-process LRU sits on top so adjacent calls within one training run never
touch disk. Disabled by default in tests; enable with `enable_disk=True`.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from pathlib import Path
from typing import Final

import numpy as np

_DEFAULT_DIR: Final[Path] = Path.home() / ".cache" / "bizvision" / "embeddings"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """In-memory LRU + optional disk backing.

    Keys are `(encoder_name, sha256(text))` so different encoders can
    coexist in the same cache.
    """

    def __init__(
        self,
        encoder_name: str,
        *,
        max_in_memory: int = 4096,
        disk_dir: Path | None = None,
        enable_disk: bool = False,
    ) -> None:
        self._name = encoder_name
        self._max_in_memory = max_in_memory
        self._mem: OrderedDict[str, np.ndarray] = OrderedDict()
        self._disk_dir: Path | None = None
        if enable_disk:
            self._disk_dir = (disk_dir or _DEFAULT_DIR) / encoder_name
            self._disk_dir.mkdir(parents=True, exist_ok=True)

    # ── core ───────────────────────────────────────────────────────
    def get(self, text: str) -> np.ndarray | None:
        key = _hash(text)
        hit = self._mem.get(key)
        if hit is not None:
            self._mem.move_to_end(key)
            return hit
        if self._disk_dir is not None:
            path = self._disk_path(key)
            if path.exists():
                arr = np.load(path)
                self._put_mem(key, arr)
                return arr
        return None

    def put(self, text: str, vec: np.ndarray) -> None:
        key = _hash(text)
        self._put_mem(key, vec)
        if self._disk_dir is not None:
            path = self._disk_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, vec, allow_pickle=False)

    # ── helpers ────────────────────────────────────────────────────
    def _put_mem(self, key: str, vec: np.ndarray) -> None:
        self._mem[key] = vec
        self._mem.move_to_end(key)
        while len(self._mem) > self._max_in_memory:
            self._mem.popitem(last=False)

    def _disk_path(self, key: str) -> Path:
        assert self._disk_dir is not None
        return self._disk_dir / key[:2] / f"{key}.npy"

    def stats(self) -> dict[str, int]:
        return {
            "in_memory": len(self._mem),
            "limit": self._max_in_memory,
            "disk_enabled": int(self._disk_dir is not None),
        }
