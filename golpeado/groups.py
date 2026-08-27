from __future__ import annotations
from itertools import combinations
from typing import Iterable

from .models import Card, Rank, Suit


# Valid 4-card straight rank windows. A is represented as 1 in A-2-3-4 and
# as 14 in J-Q-K-A. K-A-2-3 is intentionally absent.
FOUR_WINDOWS: tuple[tuple[int, int, int, int], ...] = (
    (1, 2, 3, 4),
    (2, 3, 4, 5),
    (3, 4, 5, 6),
    (4, 5, 6, 7),
    (5, 6, 7, 8),
    (6, 7, 8, 9),
    (7, 8, 9, 10),
    (8, 9, 10, 11),
    (9, 10, 11, 12),
    (10, 11, 12, 13),
    (11, 12, 13, 14),
)


def _same_rank(cards: tuple[Card, ...]) -> bool:
    return len({card.rank for card in cards}) == 1


def _same_suit(cards: tuple[Card, ...]) -> bool:
    return len({card.suit for card in cards}) == 1


def _straight_windows_for_size(size: int) -> tuple[tuple[int, ...], ...]:
    return tuple(window for window in FOUR_WINDOWS if size == 4 or size == 3 and len(window) == 4)


def _straight_values(cards: tuple[Card, ...]) -> set[int]:
    return {14 if card.rank == Rank.ACE else card.value for card in cards}


def _is_consecutive(values: set[int]) -> bool:
    ordered = sorted(values)
    return ordered == list(range(ordered[0], ordered[0] + len(ordered)))


def is_valid_group(cards: Iterable[Card]) -> bool:
    """Return True only for an official 3- or 4-card group."""
    cards = tuple(cards)
    if len(cards) not in (3, 4):
        return False
    if len({card.id for card in cards}) != len(cards):
        return False

    if _same_rank(cards):
        return True

    if not _same_suit(cards) or len({card.rank for card in cards}) != len(cards):
        return False

    # Ace-low: A-2-3-4.
    low_values = {card.value for card in cards}
    if low_values == {1, 2, 3, 4} if len(cards) == 4 else low_values == {1, 2, 3}:
        return True

    # Ordinary consecutive ranks, including J-Q-K and 10-J-Q-K.
    values = _straight_values(cards)
    if _is_consecutive(values):
        if len(cards) == 4:
            return True
        # A high is only valid in the special J-Q-K-A construction.
        return 14 not in values or values == {12, 13, 14}

    return False

def group_type(cards: Iterable[Card]) -> str | None:
    cards = tuple(cards)
    if not is_valid_group(cards):
        return None
    return "same_rank" if _same_rank(cards) else "straight"


def completing_cards_for_group(cards: Iterable[Card]) -> set[Card]:
    """Return every physical card that can legally extend a 3-card group.

    The completion is derived from the same authoritative ``is_valid_group``
    predicate used for lowering. This is important for the Ace: A may be low
    (A-2-3-4) or high (J-Q-K-A), so groups such as 2-3-4 and J-Q-K can have
    two valid completion cards.
    """
    cards = tuple(cards)
    if len(cards) != 3 or not is_valid_group(cards):
        return set()

    used_ids = {card.id for card in cards}
    result: set[Card] = set()

    # Same-rank group: any unused suit of the same rank completes the four.
    if _same_rank(cards):
        rank = cards[0].rank
        for suit in Suit:
            candidate = Card(f"{rank.name}-{suit.name}", rank, suit)
            if candidate.id not in used_ids and is_valid_group(cards + (candidate,)):
                result.add(candidate)
        return result

    # Straight: test every unused physical card of the same suit against the
    # authoritative validator. This automatically handles both Ace positions.
    suit = cards[0].suit
    for rank in Rank:
        candidate = Card(f"{rank.name}-{suit.name}", rank, suit)
        if candidate.id in used_ids:
            continue
        if is_valid_group(cards + (candidate,)):
            result.add(candidate)
    return result

def find_group_partitions(cards: Iterable[Card]) -> list[tuple[tuple[Card, ...], ...]]:
    """Find all ways to partition the supplied cards into valid hidden groups.

    Used by victory evaluation. It deliberately does not mutate the player's hand.
    """
    cards = tuple(cards)
    if not cards:
        return [()]
    if len(cards) < 3:
        return []

    first = cards[0]
    results: list[tuple[tuple[Card, ...], ...]] = []
    for size in (3, 4):
        for combo in combinations(cards[1:], size - 1):
            group = (first, *combo)
            if not is_valid_group(group):
                continue
            used_ids = {card.id for card in group}
            rest = tuple(card for card in cards if card.id not in used_ids)
            for remainder in find_group_partitions(rest):
                results.append((group, *remainder))
    return results
