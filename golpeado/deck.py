from __future__ import annotations
from collections import deque
import random
from typing import Iterable, Optional

from .models import Card, Rank, Suit


class Deck:
    """Single 52-card deck. A Card object is a physical card identified by id."""

    def __init__(self, cards: Optional[Iterable[Card]] = None, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.cards = deque(cards if cards is not None else self.standard_cards())

    @staticmethod
    def standard_cards() -> list[Card]:
        return [
            Card(f"{rank.name}-{suit.name}", rank, suit)
            for suit in Suit
            for rank in Rank
        ]

    @classmethod
    def standard(cls, seed: Optional[int] = None) -> "Deck":
        rng = random.Random(seed)
        cards = cls.standard_cards()
        rng.shuffle(cards)
        return cls(cards, rng)

    def __len__(self) -> int:
        return len(self.cards)

    def __bool__(self) -> bool:
        return bool(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            raise IndexError("La baraja está agotada")
        return self.cards.popleft()

    def draw_many(self, amount: int) -> list[Card]:
        if amount < 0 or amount > len(self.cards):
            raise ValueError("Cantidad inválida")
        return [self.draw() for _ in range(amount)]

    def shuffle(self) -> None:
        cards = list(self.cards)
        self.rng.shuffle(cards)
        self.cards = deque(cards)
