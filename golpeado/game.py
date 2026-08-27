from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional
from itertools import combinations

from .deck import Deck
from .groups import completing_cards_for_group, find_group_partitions, is_valid_group
from .models import Card, Group, Player, Plug


class InvalidMove(Exception):
    """An action violates the official game rules or current phase."""


class GameOver(Exception):
    """An action was attempted after the game had already ended."""


class GameState(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    WON = "won"
    ENDED = "ended"


class TurnPhase(str, Enum):
    ACTION = "action"
    DRAW = "draw"
    DISCARD = "discard"


@dataclass(frozen=True, slots=True)
class Victory:
    player_id: str
    reason: str


class Game:
    """Authoritative, UI-independent Golpeado rules engine."""

    def __init__(self, players: list[Player], seed: Optional[int] = None):
        if not 2 <= len(players) <= 4:
            raise ValueError("La partida debe tener entre 2 y 4 jugadores")
        if len({player.id for player in players}) != len(players):
            raise ValueError("IDs de jugadores duplicados")

        self.players = players
        self.deck = Deck.standard(seed)
        self.discard_pile: list[Card] = []
        self.state = GameState.WAITING
        self.phase: Optional[TurnPhase] = None
        self.current_index = 0
        self.winner: Optional[Victory] = None
        self.turn_number = 0
        self._group_seq = 0
        self.active_player_ids: set[str] = {player.id for player in players}
        self.abandoned_player_ids: set[str] = set()
        self.out_of_play: list[Card] = []
        self._turn_card_obtained = False

    @property
    def current_player(self) -> Player:
        return self.players[self.current_index]

    @property
    def active_players(self) -> list[Player]:
        return [p for p in self.players if p.id in self.active_player_ids]

    @property
    def last_discard(self) -> Optional[Card]:
        return self.discard_pile[-1] if self.discard_pile else None

    def start(self) -> None:
        if self.state != GameState.WAITING:
            raise InvalidMove("La partida ya fue iniciada")

        # El jugador inicial se elige aleatoriamente.
        # Ese jugador recibe 8 cartas y comienza la partida.
        import random

        starting_index = random.randrange(len(self.players))

        deal = self.deck.draw_many(7 * len(self.players) + 1)

        for index, player in enumerate(self.players):
            player.hand.clear()
            player.lowered_group = None
            player.plug = None
            player.hand.extend(deal[index * 7 : index * 7 + 7])

        self.players[starting_index].hand.append(deal[-1])

        self.state = GameState.PLAYING
        self.current_index = starting_index
        self.turn_number = 1
        self.phase = TurnPhase.ACTION
        self._turn_card_obtained = False  # jugador inicial ya recibió sus 8 cartas
        self._assert_invariants()

    def abandon(self, player_id: str) -> None:
        """Permanently remove a player; their cards leave the game."""
        if self.state not in (GameState.PLAYING,):
            raise InvalidMove("La partida no está en curso")
        if player_id not in self.active_player_ids:
            raise InvalidMove("El jugador ya no está activo")
        if len(self.active_player_ids) <= 2:
            self._remove_player_cards(player_id)
            self.active_player_ids.remove(player_id)
            self.abandoned_player_ids.add(player_id)
            self.state = GameState.ENDED
            self.phase = None
            self._assert_invariants()
            return
        was_current = self.current_player.id == player_id
        self._remove_player_cards(player_id)
        self.active_player_ids.remove(player_id)
        self.abandoned_player_ids.add(player_id)
        if was_current:
            self._advance_to_next_active()
        else:
            # Keep current player, but adjust index if a prior seat disappeared.
            self.current_index = next(i for i,p in enumerate(self.players) if p.id == self.current_player.id)
        self._assert_invariants()

    def _remove_player_cards(self, player_id: str) -> None:
        player = self._find_player(player_id)
        self.out_of_play.extend(player.hand)
        if player.lowered_group is not None:
            self.out_of_play.extend(player.lowered_group.cards)
        player.hand.clear()
        player.lowered_group = None
        player.plug = None

    def _advance_to_next_active(self) -> None:
        if len(self.active_player_ids) < 2:
            self.state = GameState.ENDED
            self.phase = None
            return
        start = self.current_index
        for offset in range(1, len(self.players) + 1):
            idx = (start + offset) % len(self.players)
            if self.players[idx].id in self.active_player_ids:
                self.current_index = idx
                self.turn_number += 1
                self.phase = TurnPhase.DRAW
                self._turn_card_obtained = False
                return
        raise RuntimeError("No se encontró siguiente jugador activo")

    def _require_current(self, player_id: str) -> Player:
        if self.state == GameState.WON:
            raise GameOver("La partida ya terminó")
        if self.state != GameState.PLAYING:
            raise InvalidMove("La partida no está iniciada")
        if self.current_player.id != player_id:
            raise InvalidMove("No es el turno de este jugador")
        return self.current_player

    def draw(self, player_id: str) -> Card:
        """Obtain exactly one card from the deck for the current turn.

        On normal turns DRAW is one of two mutually exclusive ways to obtain
        the turn card: the other is take_last_discard().
        """
        player = self._require_current(player_id)
        if self.phase != TurnPhase.DRAW:
            raise InvalidMove("No es momento de obtener una carta del mazo")
        if not self.deck:
            self._recycle()
        card = self.deck.draw()
        player.hand.append(card)
        self._turn_card_obtained = True
        self._refresh_plug_for_player(player)
        self.phase = TurnPhase.ACTION
        self._assert_invariants()
        return card

    def lower_group(self, player_id: str, card_ids: Iterable[str]) -> Group:
        player = self._require_current(player_id)
        if self.phase != TurnPhase.ACTION:
            raise InvalidMove("Debes obtener una carta antes de bajar un grupo")
        if player.lowered_group is not None:
            raise InvalidMove("Cada jugador solo puede bajar un grupo en toda la partida")

        ids = tuple(card_ids)
        if len(ids) not in (3, 4) or len(set(ids)) != len(ids):
            raise InvalidMove("Un grupo debe tener 3 o 4 cartas físicas distintas")

        cards = self._cards_from_hand(player, ids)
        if not is_valid_group(cards):
            raise InvalidMove("El grupo no es válido según las reglas de Golpeado")

        for card in cards:
            player.remove_card(card.id)
        if player.plug is not None and any(card.id == player.plug.card.id for card in cards):
            player.plug = None

        group = self._make_group(cards, player.id)
        player.lowered_group = group
        self._assign_plugs(group)
        self._check_immediate_victory(player)
        if self.state != GameState.WON:
            self.phase = TurnPhase.DISCARD
        self._assert_invariants()
        return group

    def take_last_discard(self, player_id: str, card_ids: Iterable[str]) -> Group:
        """Obtain the last discard instead of drawing and lower it immediately."""
        player = self._require_current(player_id)
        if self.phase == TurnPhase.ACTION and self._turn_card_obtained:
            raise InvalidMove("Ya obtuviste la carta de este turno")
        if self.phase not in (TurnPhase.DRAW, TurnPhase.ACTION):
            raise InvalidMove("No es momento de recoger el último descarte")
        if player.lowered_group is not None:
            raise InvalidMove("Ya bajaste tu único grupo permitido")

        last = self.last_discard
        if last is None:
            raise InvalidMove("No hay carta descartada para recoger")

        ids = tuple(card_ids)
        if last.id not in ids:
            raise InvalidMove("Debes incluir el último descarte en el grupo")
        if len(ids) not in (3, 4) or len(set(ids)) != len(ids):
            raise InvalidMove("Un grupo debe tener 3 o 4 cartas físicas distintas")

        cards: list[Card] = []
        for card_id in ids:
            if card_id == last.id:
                cards.append(last)
            else:
                owned = next((card for card in player.hand if card.id == card_id), None)
                if owned is None:
                    raise InvalidMove("Las demás cartas deben estar en la mano del jugador")
                cards.append(owned)

        if not is_valid_group(cards):
            raise InvalidMove("La carta recogida no permite formar un grupo válido")

        for card in cards:
            if card.id != last.id:
                player.remove_card(card.id)
        self.discard_pile.pop()
        self._turn_card_obtained = True
        if player.plug is not None and any(card.id == player.plug.card.id for card in cards):
            player.plug = None

        group = self._make_group(tuple(cards), player.id)
        player.lowered_group = group
        self._assign_plugs(group)
        self._check_immediate_victory(player)
        if self.state != GameState.WON:
            self.phase = TurnPhase.DISCARD
        self._assert_invariants()
        return group

    def discard(self, player_id: str, card_id: str) -> Card:
        player = self._require_current(player_id)
        if self.phase not in (TurnPhase.ACTION, TurnPhase.DISCARD):
            raise InvalidMove("No es momento de descartar")

        # Every normal turn discards exactly one card. The hand size may be
        # below seven after a group has been lowered; that does not affect the
        # obligation to draw one and discard one on future turns.
        if not player.has_card(card_id):
            raise InvalidMove("No puedes descartar una carta que no tienes")

        if len(player.hand) < 1:
            raise InvalidMove("No hay cartas para descartar")

        card = player.remove_card(card_id)
        self.discard_pile.append(card)
        if player.plug is not None and player.plug.card.id == card.id:
            player.plug = None

        self._check_discard_victory(player)
        if self.state != GameState.WON:
            self._next_turn()
        self._assert_invariants()
        return card

    def can_win(self, player_id: str) -> Optional[str]:
        player = self._find_player(player_id)
        if self._has_four_plus_three(player):
            return "group4_plus_group3"
        if self._has_two_fours(player):
            return "two_group4_before_discard"
        if self._has_three_three_plug(player):
            return "group3_plus_group3_plus_plug"
        return None

    def claim_victory(self, player_id: str) -> Victory:
        player = self._require_current(player_id)
        reason = self.can_win(player.id)
        if reason is None:
            raise InvalidMove("El jugador no cumple una condición de victoria")
        if reason == "two_group4_before_discard":
            raise InvalidMove("Con dos grupos de 4 debe descartarse una carta para terminar 4+3")

        self.winner = Victory(player.id, reason)
        self.state = GameState.WON
        self.phase = None
        return self.winner

    def _find_player(self, player_id: str) -> Player:
        for player in self.players:
            if player.id == player_id:
                return player
        raise ValueError("Jugador inexistente")

    def _cards_from_hand(self, player: Player, ids: tuple[str, ...]) -> tuple[Card, ...]:
        cards: list[Card] = []
        for card_id in ids:
            card = next((card for card in player.hand if card.id == card_id), None)
            if card is None:
                raise InvalidMove("El jugador no posee todas las cartas indicadas")
            cards.append(card)
        return tuple(cards)

    def _make_group(self, cards: tuple[Card, ...], owner_id: str) -> Group:
        self._group_seq += 1
        return Group(f"G{self._group_seq}", cards, owner_id)

    def _next_turn(self) -> None:
        self._advance_to_next_active()

    def _assign_plugs(self, group: Group) -> None:
        # Only a group of 3 can create enchufes. Each player may have at most one.
        if group.size != 3:
            return

        candidates = completing_cards_for_group(group.cards)
        for player in self.players:
            if player.id == group.owner_id or player.plug is not None:
                continue
            matching = next((card for card in player.hand if card in candidates), None)
            if matching is not None:
                player.plug = Plug(matching, player.id, group.id)

    def _refresh_plug_for_player(self, player: Player) -> None:
        """Assign a newly obtained card as a plug when it completes a public 3.

        This also covers the official anticipatory-plug rule: a player may
        already have the card when a group is lowered, or may obtain the card
        later while the public group remains on the table. The one-plug limit
        is always enforced.
        """
        if player.plug is not None:
            return
        for other in self.players:
            group = other.lowered_group
            if group is None or group.size != 3 or other.id == player.id:
                continue
            candidates = completing_cards_for_group(group.cards)
            matching = next((card for card in player.hand if card in candidates), None)
            if matching is not None:
                player.plug = Plug(matching, player.id, group.id)
                return

    def _hidden_partitions(self, cards: Iterable[Card]) -> list[tuple[tuple[Card, ...], ...]]:
        return find_group_partitions(tuple(cards))

    def _combined_groups(self, player: Player) -> list[tuple[Card, ...]]:
        groups: list[tuple[Card, ...]] = []
        if player.lowered_group is not None:
            groups.append(player.lowered_group.cards)
        for partition in self._hidden_partitions(player.hand):
            groups.extend(partition)
        return groups

    def _has_exact_group(self, cards: Iterable[Card], size: int) -> bool:
        cards = tuple(cards)
        return len(cards) == size and is_valid_group(cards)

    def _has_exact_partition(self, cards: Iterable[Card], first_size: int, second_size: int) -> bool:
        cards = tuple(cards)
        if len(cards) != first_size + second_size:
            return False
        for first in combinations(cards, first_size):
            if not is_valid_group(first):
                continue
            used = {card.id for card in first}
            second = tuple(card for card in cards if card.id not in used)
            if len(second) == second_size and is_valid_group(second):
                return True
        return False

    def _has_four_plus_three(self, player: Player) -> bool:
        if player.lowered_group is not None:
            required = 3 if player.lowered_group.size == 4 else 4
            return self._has_exact_group(player.hand, required)
        return self._has_exact_partition(player.hand, 4, 3)

    def _has_two_fours(self, player: Player) -> bool:
        if player.lowered_group is not None:
            if player.lowered_group.size != 4:
                return False
            return self._has_exact_group(player.hand, 4)
        return self._has_exact_partition(player.hand, 4, 4)

    def _has_three_three_plug(self, player: Player) -> bool:
        if player.plug is None:
            return False
        if player.lowered_group is not None and player.lowered_group.size != 3:
            return False
        if not player.has_card(player.plug.card.id):
            return False

        remaining = tuple(card for card in player.hand if card.id != player.plug.card.id)
        if player.lowered_group is not None:
            return self._has_exact_group(remaining, 3)
        return self._has_exact_partition(remaining, 3, 3)

    def _check_immediate_victory(self, player: Player) -> None:
        reason = self.can_win(player.id)
        if reason and reason != "two_group4_before_discard":
            self.winner = Victory(player.id, reason)
            self.state = GameState.WON
            self.phase = None

    def _check_discard_victory(self, player: Player) -> None:
        reason = self.can_win(player.id)
        if reason == "group4_plus_group3":
            self.winner = Victory(player.id, reason)
            self.state = GameState.WON
            self.phase = None
        elif reason == "group3_plus_group3_plus_plug":
            self.winner = Victory(player.id, reason)
            self.state = GameState.WON
            self.phase = None
        elif reason == "two_group4_before_discard":
            # This is only reachable if the discarded card was not from the
            # second 4. If the remaining three form a group, victory is 4+3.
            if self._has_four_plus_three(player):
                self.winner = Victory(player.id, "group4_plus_group3")
                self.state = GameState.WON
                self.phase = None

    def _recycle(self) -> None:
        if len(self.discard_pile) <= 1:
            raise InvalidMove("No hay suficientes descartes para reciclar la baraja")

        last = self.discard_pile[-1]
        recycled = self.discard_pile[:-1]
        self.discard_pile = [last]
        self.deck.cards.clear()
        self.deck.cards.extend(recycled)
        self.deck.shuffle()

    def force_recycle_for_test(self) -> None:
        self._recycle()

    def _assert_invariants(self) -> None:
        """Internal integrity checks; never trust UI/client state."""
        if self.state == GameState.WAITING:
            return

        all_cards: list[Card] = list(self.deck.cards) + list(self.discard_pile) + list(self.out_of_play)
        for player in self.players:
            all_cards.extend(player.hand)
            if player.lowered_group is not None:
                all_cards.extend(player.lowered_group.cards)

        ids = [card.id for card in all_cards]
        if len(ids) != len(set(ids)):
            raise RuntimeError("Invariante rota: una carta física aparece en más de un lugar")

        if any(player.plug is not None and not player.has_card(player.plug.card.id) for player in self.players):
            raise RuntimeError("Invariante rota: un enchufe no pertenece a la mano de su propietario")

        if any(player.lowered_group is not None and player.lowered_group.owner_id != player.id for player in self.players):
            raise RuntimeError("Invariante rota: grupo bajado con propietario incorrecto")
