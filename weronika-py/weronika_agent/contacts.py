"""Conservative contact matching: rank candidates, never silently choose a fuzzy match."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable

from .models import RecipientCandidate, VisibleContact


def normalize_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).casefold()
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w@]+", " ", without_marks, flags=re.UNICODE).split())


def _score(query: str, candidate: str) -> tuple[float, bool]:
    q = normalize_name(query)
    c = normalize_name(candidate)
    if not q or not c:
        return 0.0, False
    if q == c:
        return 1.0, True
    if len(q) < 3:
        return 0.0, False
    if c.startswith(q):
        return 0.91, False
    if q in c:
        return 0.84, False
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    token_score = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
    edit_score = SequenceMatcher(None, q, c).ratio()
    return max(edit_score, token_score * 0.88), False


def rank_candidates(
    query: str,
    visible_names: Iterable[str | VisibleContact],
    *,
    limit: int = 5,
    minimum_score: float = 0.45,
) -> list[RecipientCandidate]:
    """Rank visible app results, retaining duplicate names as separate choices."""
    ranked: list[tuple[str, str, float, bool, int]] = []
    for input_index, item in enumerate(visible_names):
        if isinstance(item, VisibleContact):
            name, source_id = item.display_name, item.source_id
        else:
            name, source_id = " ".join(str(item or "").split()), str(input_index)
        name = " ".join(str(name or "").split())
        if not normalize_name(name):
            continue
        score, exact = _score(query, name)
        if score >= minimum_score:
            ranked.append((name, source_id, score, exact, input_index))
    ranked.sort(key=lambda row: (not row[3], -row[2], row[0].casefold(), row[4]))

    name_counts: dict[str, int] = {}
    for name, *_ in ranked:
        key = normalize_name(name)
        name_counts[key] = name_counts.get(key, 0) + 1

    candidates = []
    for index, (name, source_id, score, exact, _) in enumerate(ranked[:limit], start=1):
        context = f"separate result {index}" if name_counts[normalize_name(name)] > 1 else ""
        candidates.append(
            RecipientCandidate(
                id=str(index),
                display_name=name,
                confidence=round(score, 3),
                exact=exact,
                context=context,
                source_id=source_id,
            )
        )
    return candidates


def unique_exact_match(candidates: list[RecipientCandidate]) -> RecipientCandidate | None:
    exact = [candidate for candidate in candidates if candidate.exact]
    return exact[0] if len(exact) == 1 else None
