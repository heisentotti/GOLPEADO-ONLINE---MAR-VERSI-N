from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Optional

from ..game import Game, GameState, TurnPhase
from ..models import Player
from .strategy import ActionKind, BotAction, BotObservation, Difficulty, PublicGroupView, strategy_for


class BotController:
    """Adapter between a bot strategy and the authoritative Game.

    The controller never passes Game.players' hidden hands to the strategy.
    It constructs a restricted BotObservation first and then submits the
    resulting action back to Game, exactly like a future human client will.
    """

    def __init__(self, difficulty: Difficulty | str, seed: Optional[int] = None):
        self.difficulty = Difficulty(difficulty)
        self.rng = random.Random(seed)
        self.strategy = strategy_for(self.difficulty, self.rng)

    def observe(self, game: Game, player_id: str) -> BotObservation:
        player = next(p for p in game.players if p.id == player_id)
        public_groups = tuple(
            PublicGroupView(p.lowered_group.id, p.id, p.lowered_group.cards)
            for p in game.players
            if p.lowered_group is not None
        )
        own_group = None
        if player.lowered_group is not None:
            own_group = PublicGroupView(
                player.lowered_group.id,
                player.id,
                player.lowered_group.cards,
            )
        return BotObservation(
            player_id=player.id,
            own_hand=tuple(player.hand),
            own_lowered_group=own_group,
            own_plug_card=player.plug.card if player.plug else None,
            public_groups=public_groups,
            discard_pile=tuple(game.discard_pile),
            player_count=len(game.players),
            turn_number=game.turn_number,
        )

    def play_turn(self, game: Game, player_id: str) -> BotAction:
        """Play one complete bot turn through the authoritative Game.

        On a normal turn the bot chooses exactly one way to obtain a card:
        draw from the deck OR take the last discard. Taking the discard must
        immediately lower a valid group containing that card.
        """
        if game.state != GameState.PLAYING or game.current_player.id != player_id:
            raise ValueError("El bot no puede actuar fuera de su turno")
        player = game.current_player

        # The starting player already has 8 cards and begins in ACTION. Every
        # later turn begins in DRAW, where draw and take-last-discard are
        # mutually exclusive alternatives.
        if game.phase == TurnPhase.DRAW:
            obs = self.observe(game, player_id)
            obtain = self.strategy.choose_action(obs) if player.lowered_group is None else BotAction(ActionKind.DRAW)
            if obtain.kind == ActionKind.TAKE_DISCARD:
                game.take_last_discard(player_id, obtain.card_ids)
                if game.state == GameState.WON:
                    return obtain
                return self._discard_after_action(game, player, player_id)
            game.draw(player_id)

        # On the initial turn the first player already has 8 dealt cards, so
        # there is no obtain step. On every later turn exactly one obtain step
        # has now happened.
        obs = self.observe(game, player_id)
        if game.phase != TurnPhase.ACTION:
            raise RuntimeError(f"Fase de partida no manejada por bot: {game.phase}")

        # The initial player, or a bot that drew from the deck, may now decide
        # whether to lower its one allowed hidden group or simply discard.
        if player.lowered_group is None:
            group = self.strategy.choose_lowered_group(obs)
            if group:
                action = BotAction(ActionKind.LOWER, tuple(c.id for c in group))
                game.lower_group(player_id, action.card_ids)
                if game.state == GameState.WON:
                    return action
                return self._discard_after_action(game, player, player_id)

        action = BotAction(ActionKind.DISCARD, card_id=self.strategy.choose_discard(obs).id)
        game.discard(player_id, action.card_id)
        return action

    def _discard_after_action(self, game: Game, player: Player, player_id: str) -> BotAction:
        obs = self.observe(game, player_id)
        card = self.strategy.choose_discard(obs)
        action = BotAction(kind=ActionKind.DISCARD, card_id=card.id)
        game.discard(player_id, card.id)
        return action

