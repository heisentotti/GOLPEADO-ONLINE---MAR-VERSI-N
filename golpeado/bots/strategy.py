from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
import random
from typing import Iterable, Optional

from ..groups import completing_cards_for_group, find_group_partitions, is_valid_group
from ..models import Card, Group, Player


class Difficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    EXPERT = "expert"


class ActionKind(str, Enum):
    DRAW = "draw"
    TAKE_DISCARD = "take_discard"
    LOWER = "lower"
    DISCARD = "discard"


@dataclass(frozen=True, slots=True)
class BotAction:
    kind: ActionKind
    card_ids: tuple[str, ...] = ()
    card_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PublicGroupView:
    group_id: str
    owner_id: str
    cards: tuple[Card, ...]


@dataclass(frozen=True, slots=True)
class BotObservation:
    """Information a human player is allowed to know.

    It intentionally contains no other player's hand, no private plug and no
    undealt deck contents. The discard pile is public because all discards are
    visible on the table; only the last card is actionable.
    """

    player_id: str
    own_hand: tuple[Card, ...]
    own_lowered_group: Optional[PublicGroupView]
    own_plug_card: Optional[Card]
    public_groups: tuple[PublicGroupView, ...]
    discard_pile: tuple[Card, ...]
    player_count: int
    turn_number: int

    @property
    def last_discard(self) -> Optional[Card]:
        return self.discard_pile[-1] if self.discard_pile else None


class BotStrategy:
    """Base strategy. It can only reason over a BotObservation."""

    difficulty = Difficulty.NORMAL

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def choose_action(self, obs: BotObservation) -> BotAction:
        if self.should_take_last_discard(obs):
            group = self.best_group_using_card(obs.own_hand, obs.last_discard)
            if group:
                return BotAction(ActionKind.TAKE_DISCARD, tuple(c.id for c in group))
        return BotAction(ActionKind.DRAW)

    def choose_action_after_draw(self, obs: BotObservation) -> BotAction:
        group = self.choose_lowered_group(obs)
        if group:
            return BotAction(ActionKind.LOWER, tuple(c.id for c in group))
        return BotAction(ActionKind.DISCARD, card_id=self.choose_discard(obs).id)

    def should_take_last_discard(self, obs: BotObservation) -> bool:
        return bool(self.best_group_using_card(obs.own_hand, obs.last_discard))

    def choose_lowered_group(self, obs: BotObservation) -> Optional[tuple[Card, ...]]:
        return None

    def choose_discard(self, obs: BotObservation) -> Card:
        return self.rng.choice(list(obs.own_hand))

    @staticmethod
    def valid_groups(cards: Iterable[Card]) -> list[tuple[Card, ...]]:
        cards = tuple(cards)
        result: list[tuple[Card, ...]] = []
        for size in (4, 3):
            for combo in combinations(cards, size):
                if is_valid_group(combo):
                    result.append(tuple(combo))
        return result

    @classmethod
    def best_group_using_card(
        cls, hand: Iterable[Card], required: Optional[Card]
    ) -> Optional[tuple[Card, ...]]:
        if required is None:
            return None
        cards = tuple(hand)
        candidates = [
            group for group in cls.valid_groups(cards + (required,))
            if required.id in {c.id for c in group}
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda g: (len(g), cls.group_quality(g)), reverse=True)
        return candidates[0]

    @staticmethod
    def group_quality(group: tuple[Card, ...]) -> float:
        ranks = sorted(14 if c.value == 1 else c.value for c in group)
        return len(group) * 10 + sum(ranks) / len(ranks)

    @staticmethod
    def group_completions(group: tuple[Card, ...]) -> set[tuple[int, str]]:
        return {(c.value, c.suit.value) for c in completing_cards_for_group(group)}


class EasyBot(BotStrategy):
    difficulty = Difficulty.EASY

    def choose_lowered_group(self, obs: BotObservation) -> Optional[tuple[Card, ...]]:
        groups = self.valid_groups(obs.own_hand)
        if not groups:
            return None
        # Basic combinations, with some deliberate randomness.
        if self.rng.random() < 0.30:
            return self.rng.choice(groups)
        groups.sort(key=lambda g: (len(g), self.group_quality(g)), reverse=True)
        return groups[0]

    def choose_discard(self, obs: BotObservation) -> Card:
        # Keep the easy bot simple, but do not deliberately destroy an obvious
        # hidden group when a neutral discard exists.
        groups = self.valid_groups(obs.own_hand)
        protected = {card.id for group in groups for card in group}
        safe = [card for card in obs.own_hand if card.id not in protected]
        return self.rng.choice(safe or list(obs.own_hand))


class NormalBot(BotStrategy):
    difficulty = Difficulty.NORMAL

    def choose_lowered_group(self, obs: BotObservation) -> Optional[tuple[Card, ...]]:
        groups = self.valid_groups(obs.own_hand)
        if not groups:
            return None
        # Prefer 4s, then groups that consume fewer strategically useful cards.
        groups.sort(key=lambda g: (len(g), self.group_quality(g)), reverse=True)
        return groups[0]

    def choose_discard(self, obs: BotObservation) -> Card:
        hand = list(obs.own_hand)
        scored = [(self.discard_score(card, obs), card) for card in hand]
        scored.sort(key=lambda x: x[0], reverse=True)
        # Small tie/random variation prevents deterministic repetitive games.
        best = scored[0][0]
        candidates = [card for score, card in scored if score >= best - 1.0]
        return self.rng.choice(candidates)

    def discard_score(self, card: Card, obs: BotObservation) -> float:
        score = 0.0
        # Prefer discarding cards with few companions in the hand.
        companions = sum(1 for c in obs.own_hand if c.id != card.id and c.rank == card.rank)
        same_suit_near = sum(
            1
            for c in obs.own_hand
            if c.id != card.id and c.suit == card.suit and abs((14 if c.value == 1 else c.value) - (14 if card.value == 1 else card.value)) <= 2
        )
        score += (2 - companions) * 2
        score += max(0, 2 - same_suit_near)
        if any(card.id == c.id for group in self.valid_groups(obs.own_hand) for c in group):
            score -= 8
        return score


class HardBot(NormalBot):
    difficulty = Difficulty.HARD

    def should_take_last_discard(self, obs: BotObservation) -> bool:
        group = self.best_group_using_card(obs.own_hand, obs.last_discard)
        if not group:
            return False
        # If the discard completes a 4, normally take it. If it creates only a
        # 3, still take it unless doing so consumes an obvious winning structure.
        return len(group) == 4 or self.rng.random() < 0.90

    def choose_lowered_group(self, obs: BotObservation) -> Optional[tuple[Card, ...]]:
        groups = self.valid_groups(obs.own_hand)
        if not groups:
            return None
        scored = [(self.lower_group_score(g, obs), g) for g in groups]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def lower_group_score(self, group: tuple[Card, ...], obs: BotObservation) -> float:
        score = self.group_quality(group)
        if len(group) == 4:
            score += 18
        else:
            completions = completing_cards_for_group(group)
            visible = {c.id for c in obs.discard_pile}
            score += sum(1 for c in completions if c.id in visible) * 4
            score += len(completions) * 2
        return score

    def choose_discard(self, obs: BotObservation) -> Card:
        hand = list(obs.own_hand)
        visible = {c.id for c in obs.discard_pile}
        scored = []
        for card in hand:
            score = self.discard_score(card, obs)
            # Do not casually discard a card that is a known completion of a
            # public group; it can become somebody's plug.
            for public in obs.public_groups:
                if public.owner_id == obs.player_id or len(public.cards) != 3:
                    continue
                if card in completing_cards_for_group(public.cards):
                    score -= 10
            # Avoid repeatedly feeding the same visible card.
            if card.id in visible:
                score += 1
            scored.append((score, card))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][0]
        return self.rng.choice([c for s, c in scored if s >= best - 0.5])


class ExpertBot(HardBot):
    difficulty = Difficulty.EXPERT

    def __init__(self, rng: Optional[random.Random] = None):
        super().__init__(rng)
        self.seen_public: dict[str, Card] = {}

    def choose_action(self, obs: BotObservation) -> BotAction:
        self._remember(obs)
        # Prefer a discard pickup only when it creates the strongest available
        # immediate group. This remains strictly based on public information.
        group = self.best_group_using_card(obs.own_hand, obs.last_discard)
        if group:
            score = self._group_score(group, obs, uses_discard=True)
            if score >= 35:
                return BotAction(ActionKind.TAKE_DISCARD, tuple(c.id for c in group))
        return BotAction(ActionKind.DRAW)

    def choose_lowered_group(self, obs: BotObservation) -> Optional[tuple[Card, ...]]:
        self._remember(obs)
        groups = self.valid_groups(obs.own_hand)
        if not groups:
            return None
        scored = [(self._group_score(g, obs), g) for g in groups]
        scored.sort(key=lambda x: x[0], reverse=True)
        # Lowering is only one-time, so an expert avoids spending it merely on
        # a weak group when a stronger hidden structure exists.
        if scored[0][0] < 28 and self.rng.random() < 0.20:
            return None
        return scored[0][1]

    def choose_discard(self, obs: BotObservation) -> Card:
        self._remember(obs)
        scored = [(self._expert_discard_score(card, obs), card) for card in obs.own_hand]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[0][0]
        candidates = [c for s, c in scored if s >= top - 1.0]
        return self.rng.choice(candidates)

    def _remember(self, obs: BotObservation) -> None:
        for card in obs.discard_pile:
            self.seen_public[card.id] = card
        for group in obs.public_groups:
            for card in group.cards:
                self.seen_public[card.id] = card
        if obs.own_lowered_group:
            for card in obs.own_lowered_group.cards:
                self.seen_public[card.id] = card
        for card in obs.own_hand:
            self.seen_public[card.id] = card
        if obs.own_plug_card:
            self.seen_public[obs.own_plug_card.id] = obs.own_plug_card

    def _group_score(self, group: tuple[Card, ...], obs: BotObservation, uses_discard: bool = False) -> float:
        score = self.group_quality(group)
        score += 22 if len(group) == 4 else 8
        if uses_discard:
            score += 8
        if len(group) == 3:
            completions = completing_cards_for_group(group)
            unseen = [c for c in completions if c.id not in self.seen_public]
            score += min(12, len(unseen) * 3)
            # A 3 with a visible completion is less speculative.
            score += sum(2 for c in completions if c.id in {x.id for x in obs.discard_pile})
        return score

    def _expert_discard_score(self, card: Card, obs: BotObservation) -> float:
        score = self.discard_score(card, obs)
        # High penalty for throwing away a likely completion of public groups.
        for public in obs.public_groups:
            if public.owner_id != obs.player_id and len(public.cards) == 3:
                if card in completing_cards_for_group(public.cards):
                    score -= 20
        # Preserve cards participating in any hidden 3/4 group.
        for group in self.valid_groups(obs.own_hand):
            if card in group:
                score -= 3 + len(group)
        # Prefer discarding already-public cards when strategically neutral.
        if card.id in self.seen_public:
            score += 2
        return score


def strategy_for(difficulty: Difficulty | str, rng: Optional[random.Random] = None) -> BotStrategy:
    difficulty = Difficulty(difficulty)
    cls = {
        Difficulty.EASY: EasyBot,
        Difficulty.NORMAL: NormalBot,
        Difficulty.HARD: HardBot,
        Difficulty.EXPERT: ExpertBot,
    }[difficulty]
    return cls(rng)
