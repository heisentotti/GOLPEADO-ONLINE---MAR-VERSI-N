from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Suit(str, Enum):
    CLUBS = "C"
    DIAMONDS = "D"
    HEARTS = "H"
    SPADES = "S"

    @property
    def symbol(self) -> str:
        return {"C": "♣", "D": "♦", "H": "♥", "S": "♠"}[self.value]


class Rank(int, Enum):
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13

    @property
    def label(self) -> str:
        return {1: "A", 11: "J", 12: "Q", 13: "K"}.get(self.value, str(self.value))


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    rank: Rank
    suit: Suit

    @property
    def value(self) -> int:
        return self.rank.value

    def __str__(self) -> str:
        return f"{self.rank.label}{self.suit.symbol}"


class PlayerType(str, Enum):
    HUMAN = "human"
    BOT = "bot"


@dataclass(frozen=True, slots=True)
class Group:
    id: str
    cards: tuple[Card, ...]
    owner_id: str

    @property
    def size(self) -> int:
        return len(self.cards)


@dataclass(frozen=True, slots=True)
class Plug:
    card: Card
    owner_id: str
    target_group_id: str


@dataclass
class Player:
    id: str
    name: str
    type: PlayerType = PlayerType.HUMAN
    hand: list[Card] = field(default_factory=list)
    lowered_group: Optional[Group] = None
    plug: Optional[Plug] = None

    def remove_card(self, card_id: str) -> Card:
        for index, card in enumerate(self.hand):
            if card.id == card_id:
                return self.hand.pop(index)
        raise ValueError(f"Player {self.id} does not own {card_id}")

    def has_card(self, card_id: str) -> bool:
        return any(card.id == card_id for card in self.hand)
