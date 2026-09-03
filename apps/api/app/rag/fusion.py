"""Reciprocal Rank Fusion — pure function, unit-tested."""
from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import TypeVar

T = TypeVar("T")


def rrf(rankings: Sequence[Sequence[T]], key=lambda x: x, k: int = 60) -> list[tuple[T, float]]:
    scores: dict[Hashable, float] = {}
    first: dict[Hashable, T] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            kk = key(item)
            scores[kk] = scores.get(kk, 0.0) + 1.0 / (k + rank)
            first.setdefault(kk, item)
    ordered = sorted(scores.items(), key=lambda kv: -kv[1])
    return [(first[kk], s) for kk, s in ordered]
