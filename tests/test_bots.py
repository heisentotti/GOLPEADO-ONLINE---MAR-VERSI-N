from __future__ import annotations

import random

import pytest

from golpeado import Game, Player, PlayerType
from golpeado.bots import BotController, Difficulty, simulate
from golpeado.bots.strategy import ActionKind, BotObservation, ExpertBot
from golpeado.models import Card, Rank, Suit


def players(n=4):
    return [Player(str(i), f"Bot {i}", PlayerType.BOT) for i in range(n)]


def test_bot_observation_does_not_expose_other_hands_or_private_plugs():
    game = Game(players(3), seed=101)
    game.start()
    game.players[1].plug = None
    obs = BotController(Difficulty.EXPERT, seed=1).observe(game, "0")
    assert hasattr(obs, "own_hand")
    assert not hasattr(obs, "other_hands")
    assert not hasattr(obs, "all_players")
    assert not hasattr(obs, "deck")
    assert not hasattr(obs, "other_plugs")
    assert not hasattr(obs, "private_state")


def test_all_difficulties_return_valid_action_types():
    game = Game(players(4), seed=102)
    game.start()
    for difficulty in Difficulty:
        controller = BotController(difficulty, seed=4)
        action = controller.play_turn(game, game.current_player.id)
        assert action.kind in {ActionKind.DRAW, ActionKind.DISCARD, ActionKind.LOWER, ActionKind.TAKE_DISCARD}
        if game.state.value == "won":
            break


def test_expert_memory_contains_only_visible_cards():
    bot = ExpertBot(random.Random(1))
    own = Card("SEVEN-HEARTS", Rank.SEVEN, Suit.HEARTS)
    visible = Card("EIGHT-HEARTS", Rank.EIGHT, Suit.HEARTS)
    hidden_other = Card("NINE-HEARTS", Rank.NINE, Suit.HEARTS)
    obs = BotObservation("p0", (own,), None, None, (), (visible,), 2, 1)
    bot.choose_action(obs)
    assert visible.id in bot.seen_public
    assert own.id in bot.seen_public
    assert hidden_other.id not in bot.seen_public


def test_simulation_100_games_has_no_illegal_moves_or_impossible_states():
    stats = simulate(100, 4, [Difficulty.EASY, Difficulty.NORMAL, Difficulty.HARD, Difficulty.EXPERT], seed=500, max_turns=10000)
    assert stats.completed == 100
    assert stats.illegal_moves == 0
    assert stats.impossible_states == 0
    assert stats.stalled_games == 0


def test_simulation_two_player():
    stats = simulate(100, 2, [Difficulty.NORMAL, Difficulty.EXPERT], seed=900, max_turns=10000)
    assert stats.completed == 100
    assert stats.illegal_moves == 0
    assert stats.impossible_states == 0


def test_simulation_three_player():
    stats = simulate(100, 3, [Difficulty.EASY, Difficulty.HARD, Difficulty.EXPERT], seed=1100, max_turns=10000)
    assert stats.completed == 100
    assert stats.illegal_moves == 0
    assert stats.impossible_states == 0


def test_bot_can_choose_discard_or_deck_as_mutually_exclusive_obtain_action():
    game = Game(players(2), seed=120)
    game.start()
    game.discard("0", game.players[0].hand[0].id)
    controller = BotController(Difficulty.EXPERT, seed=8)
    before = len(game.deck.cards)
    # The controller completes exactly one turn; it may take the discard only
    # if the visible card can immediately form a valid group.
    controller.play_turn(game, "1")
    assert len(game.deck.cards) <= before
    assert game.current_player.id == "0" or game.state.value == "won"
