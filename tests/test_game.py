import pytest

from golpeado.game import Game, GameOver, GameState, InvalidMove, TurnPhase
from golpeado.models import Card, Group, Player, PlayerType, Rank, Suit, Plug


def players(n=2):
    return [Player(str(i), f"P{i}") for i in range(n)]


def C(value, suit):
    rank = Rank.ACE if value == 1 else Rank(value)
    return Card(f"{rank.name}-{suit.name}", rank, suit)



def install_cards(g, player, cards):
    ids = {c.id for c in cards}
    g.deck.cards = type(g.deck.cards)(c for c in g.deck.cards if c.id not in ids)
    g.discard_pile = [c for c in g.discard_pile if c.id not in ids]
    for other in g.players:
        other.hand[:] = [c for c in other.hand if c.id not in ids]
        if other.lowered_group is not None and any(c.id in ids for c in other.lowered_group.cards):
            other.lowered_group = None
        if other.plug is not None and other.plug.card.id in ids:
            other.plug = None
    player.hand.clear()
    player.hand.extend(cards)

def test_player_count_must_be_2_to_4():
    with pytest.raises(ValueError): Game(players(1))
    with pytest.raises(ValueError): Game(players(5))


def test_deal_is_8_to_first_and_7_to_everyone_else():
    g = Game(players(4), seed=1)
    g.start()
    assert [len(p.hand) for p in g.players] == [8, 7, 7, 7]
    assert g.current_player.id == "0"
    assert g.phase == TurnPhase.ACTION
    assert len(g.deck) == 23


def test_clockwise_turn_order():
    g = Game(players(4), seed=2)
    g.start()
    g.discard("0", g.players[0].hand[0].id)
    assert g.current_player.id == "1"
    g.draw("1"); g.discard("1", g.players[1].hand[0].id)
    assert g.current_player.id == "2"
    g.draw("2"); g.discard("2", g.players[2].hand[0].id)
    assert g.current_player.id == "3"
    g.draw("3"); g.discard("3", g.players[3].hand[0].id)
    assert g.current_player.id == "0"



def test_first_player_can_discard_without_drawing_because_they_started_with_8():
    g = Game(players(), seed=3)
    g.start()
    card = g.players[0].hand[0]
    g.discard("0", card.id)
    assert len(g.players[0].hand) == 7
    assert g.current_player.id == "1"


def test_normal_turn_requires_draw_then_mandatory_discard():
    g = Game(players(), seed=4)
    g.start()
    g.discard("0", g.current_player.hand[0].id)
    with pytest.raises(InvalidMove):
        g.discard("1", g.current_player.hand[0].id)
    g.draw("1")
    assert len(g.players[1].hand) == 8
    g.discard("1", g.current_player.hand[0].id)
    assert len(g.players[1].hand) == 7


def test_cannot_draw_twice_or_discard_non_owned_card():
    g = Game(players(), seed=5)
    g.start()
    g.discard("0", g.current_player.hand[0].id)
    g.draw("1")
    with pytest.raises(InvalidMove): g.draw("1")
    with pytest.raises(InvalidMove): g.discard("1", "not-my-card")


def test_only_last_discard_can_be_collected():
    g = Game(players(), seed=6)
    g.start()
    first = g.players[0].hand[0]
    g.discard("0", first.id)
    g.draw("1")
    second = g.players[1].hand[0]
    g.discard("1", second.id)
    g.draw("0")
    with pytest.raises(InvalidMove):
        g.take_last_discard("0", [first.id])


def test_collecting_last_discard_requires_immediate_group_and_uses_it():
    g = Game(players(), seed=7)
    g.start()
    p = g.current_player
    last = C(7, Suit.HEARTS)
    b = C(7, Suit.SPADES)
    c = C(7, Suit.DIAMONDS)
    filler = [C(2, Suit.HEARTS), C(3, Suit.HEARTS), C(4, Suit.HEARTS), C(9, Suit.DIAMONDS), C(10, Suit.DIAMONDS)]
    install_cards(g, p, [b, c, last] + filler)
    p.remove_card(last.id)
    g.discard_pile = [last]
    g.phase = TurnPhase.ACTION
    group = g.take_last_discard("0", [last.id, b.id, c.id])
    assert group.size == 3
    assert p.lowered_group == group
    assert g.last_discard is None
    assert len(p.hand) == 5
    assert g.phase == TurnPhase.DISCARD


def test_collecting_last_discard_cannot_be_used_only_as_a_card_to_keep():
    g = Game(players(), seed=8)
    g.start()
    p = g.current_player
    last = C(7, Suit.HEARTS)
    install_cards(g, p, [C(7, Suit.SPADES), C(9, Suit.DIAMONDS)])
    g.discard_pile = [last]
    g.phase = TurnPhase.ACTION
    with pytest.raises(InvalidMove):
        g.take_last_discard("0", [last.id])


def test_collecting_last_discard_rejects_invalid_group():
    g = Game(players(), seed=9)
    g.start()
    p = g.current_player
    last = C(5, Suit.HEARTS)
    b = C(8, Suit.HEARTS)
    c = C(13, Suit.HEARTS)
    install_cards(g, p, [b, c])
    g.discard_pile = [last]
    g.phase = TurnPhase.ACTION
    with pytest.raises(InvalidMove):
        g.take_last_discard("0", [last.id, b.id, c.id])


def test_only_one_lowered_group_per_player():
    g = Game(players(), seed=10)
    g.start()
    p = g.current_player
    first = [C(7, s) for s in Suit]
    second = [C(9, s) for s in Suit]
    install_cards(g, p, first + second)
    g.lower_group("0", [c.id for c in first])
    with pytest.raises(InvalidMove):
        g.lower_group("0", [c.id for c in second])


def test_lowered_four_requires_discard_before_turn_ends():
    g = Game(players(), seed=11)
    g.start()
    p = g.current_player
    four = [C(7, s) for s in Suit]
    install_cards(g, p, four + [C(9, Suit.HEARTS)])
    g.lower_group("0", [c.id for c in four])
    assert g.phase == TurnPhase.DISCARD
    g.discard("0", p.hand[0].id)
    assert g.current_player.id == "1"


def test_anticipatory_plug_is_assigned_when_three_group_is_lowered():
    g = Game(players(3), seed=12)
    g.start()
    p0, p1, p2 = g.players
    group = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS)]
    install_cards(g, p0, group)
    install_cards(g, p1, [C(4, Suit.HEARTS)])
    install_cards(g, p2, [C(12, Suit.CLUBS)])
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in group])
    assert p1.plug is not None
    assert p1.plug.card == C(4, Suit.HEARTS)
    assert p1.plug.target_group_id == p0.lowered_group.id
    assert p2.plug is None


def test_other_end_of_straight_is_also_valid_plug():
    g = Game(players(3), seed=13)
    g.start()
    p0, p1, _ = g.players
    group = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS)]
    install_cards(g, p0, group)
    install_cards(g, p1, [C(8, Suit.HEARTS)])
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in group])
    assert p1.plug is not None
    assert p1.plug.card == C(8, Suit.HEARTS)


def test_equal_rank_group_has_fourth_card_as_plug():
    g = Game(players(2), seed=14)
    g.start()
    p0, p1 = g.players
    group = [C(7, Suit.HEARTS), C(7, Suit.DIAMONDS), C(7, Suit.SPADES)]
    install_cards(g, p0, group)
    install_cards(g, p1, [C(7, Suit.CLUBS)])
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in group])
    assert p1.plug.card == C(7, Suit.CLUBS)


def test_four_card_group_creates_no_plug():
    g = Game(players(2), seed=15)
    g.start()
    p0, p1 = g.players
    group = [C(7, s) for s in Suit]
    install_cards(g, p0, group)
    install_cards(g, p1, [C(8, Suit.HEARTS)])
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in group])
    assert p1.plug is None


def test_one_plug_maximum_per_player_even_if_later_group_has_another_candidate():
    g = Game(players(3), seed=16)
    g.start()
    p0, p1, p2 = g.players
    g.phase = TurnPhase.ACTION
    first = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS)]
    install_cards(g, p0, first)
    install_cards(g, p1, [C(8, Suit.HEARTS)])
    install_cards(g, p2, [C(4, Suit.HEARTS)])
    g.lower_group("0", [c.id for c in first])
    assert p1.plug is not None and p2.plug is not None

    second = Group("G999", (C(9, Suit.DIAMONDS), C(10, Suit.DIAMONDS), C(11, Suit.DIAMONDS)), "2")
    p1.hand.append(C(12, Suit.DIAMONDS))
    g._assign_plugs(second)
    assert p1.plug.card == C(8, Suit.HEARTS)


def test_different_players_can_have_different_plugs_for_different_groups():
    g = Game(players(4), seed=17)
    g.start()
    p0, p1, p2, p3 = g.players
    g.phase = TurnPhase.ACTION
    first = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS)]
    install_cards(g, p0, first)
    install_cards(g, p1, [C(8, Suit.HEARTS)])
    install_cards(g, p2, [C(8, Suit.SPADES)])
    g.lower_group("0", [c.id for c in first])
    assert p1.plug is not None
    assert p2.plug is None  # Different suit: not a completion of the hearts group.

    second = Group("G1000", (C(9, Suit.SPADES), C(10, Suit.SPADES), C(11, Suit.SPADES)), "3")
    g._assign_plugs(second)
    assert p2.plug is not None
    assert p2.plug.card == C(8, Suit.SPADES)


def test_four_plus_three_victory():
    g = Game(players(), seed=18)
    g.start()
    p = g.players[0]
    four = [C(7, s) for s in Suit]
    three = [C(9, Suit.CLUBS), C(10, Suit.CLUBS), C(11, Suit.CLUBS)]
    install_cards(g, p, four + three)
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in four])
    assert g.can_win("0") == "group4_plus_group3"
    assert g.state == GameState.WON
    assert g.winner.player_id == "0"
    assert g.winner.reason == "group4_plus_group3"


def test_two_fours_require_discard_and_then_become_four_plus_three():
    g = Game(players(), seed=19)
    g.start()
    p = g.players[0]
    first = [C(7, s) for s in Suit]
    second = [C(9, s) for s in Suit]
    install_cards(g, p, first + second)
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in first])
    assert g.can_win("0") == "two_group4_before_discard"
    assert g.state == GameState.PLAYING
    g.discard("0", second[0].id)
    assert g.state == GameState.WON
    assert g.winner.reason == "group4_plus_group3"


def test_three_three_plus_plug_victory():
    g = Game(players(), seed=20)
    g.start()
    p = g.players[0]
    lowered = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS)]
    hidden = [C(9, Suit.SPADES), C(10, Suit.SPADES), C(11, Suit.SPADES)]
    plug = C(8, Suit.HEARTS)
    extra = C(13, Suit.CLUBS)
    install_cards(g, p, lowered + hidden + [plug, extra])
    for card in lowered:
        p.remove_card(card.id)
    p.lowered_group = Group("G1", tuple(lowered), "0")
    p.plug = Plug(plug, "0", "GOTHER")
    g.state = GameState.PLAYING
    g.phase = TurnPhase.DISCARD
    g.discard("0", extra.id)
    assert g.state == GameState.WON
    assert g.winner.reason == "group3_plus_group3_plus_plug"


def test_invalid_king_ace_two_three_cannot_be_lowered():
    g = Game(players(), seed=21)
    g.start()
    p = g.players[0]
    cards = [C(13, Suit.HEARTS), C(1, Suit.HEARTS), C(2, Suit.HEARTS), C(3, Suit.HEARTS)]
    install_cards(g, p, cards)
    with pytest.raises(InvalidMove):
        g.lower_group("0", [c.id for c in cards])


def test_deck_recycling_keeps_last_discard_out_of_new_deck():
    g = Game(players(), seed=22)
    cards = list(g.deck.cards)
    old = cards[:4]
    last = cards[4]
    g.discard_pile = old + [last]
    g.deck.cards.clear()
    g.force_recycle_for_test()
    assert g.last_discard == last
    assert set(g.deck.cards) == set(old)
    assert last not in g.deck.cards


def test_recycling_preserves_physical_card_uniqueness():
    g = Game(players(), seed=23)
    cards = list(g.deck.cards)
    g.discard_pile = cards[:10]
    g.deck.cards.clear()
    g.force_recycle_for_test()
    assert len({c.id for c in g.deck.cards}) == 9
    assert len(g.deck.cards) == 9
    assert g.last_discard not in g.deck.cards


def test_recycle_fails_if_only_last_discard_exists():
    g = Game(players(), seed=24)
    g.discard_pile = [g.deck.draw()]
    g.deck.cards.clear()
    with pytest.raises(InvalidMove):
        g.force_recycle_for_test()


def test_game_ends_immediately_and_rejects_future_actions():
    g = Game(players(), seed=25)
    g.start()
    p = g.players[0]
    four = [C(7, s) for s in Suit]
    three = [C(9, Suit.CLUBS), C(10, Suit.CLUBS), C(11, Suit.CLUBS)]
    install_cards(g, p, four + three)
    g.lower_group("0", [c.id for c in four])
    assert g.state == GameState.WON
    with pytest.raises(GameOver):
        g.discard("0", p.hand[0].id)


def test_two_fours_are_not_misread_as_four_plus_three():
    g = Game(players(), seed=26)
    g.start()
    p = g.players[0]
    first = [C(7, s) for s in Suit]
    second = [C(9, s) for s in Suit]
    install_cards(g, p, first + second)
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in first])
    assert g.state == GameState.PLAYING
    assert g.can_win("0") == "two_group4_before_discard"



def test_take_last_discard_replaces_draw_on_normal_turn():
    g = Game(players(), seed=31)
    g.start()
    # Finish the starting player's turn without lowering.
    g.discard("0", g.players[0].hand[0].id)
    assert g.current_player.id == "1"
    p = g.players[1]
    last = C(7, Suit.HEARTS)
    b = C(5, Suit.HEARTS)
    c = C(6, Suit.HEARTS)
    fillers = [C(2, Suit.CLUBS), C(3, Suit.CLUBS), C(4, Suit.CLUBS), C(9, Suit.DIAMONDS), C(10, Suit.DIAMONDS)]
    install_cards(g, p, [b, c, last] + fillers)
    p.remove_card(last.id)
    g.discard_pile = [last]
    before_deck = len(g.deck.cards)
    g.phase = TurnPhase.DRAW
    group = g.take_last_discard("1", [last.id, b.id, c.id])
    assert group.size == 3
    assert len(g.deck.cards) == before_deck
    assert len(p.hand) == 5
    assert g.phase == TurnPhase.DISCARD


def test_cannot_draw_after_taking_last_discard():
    g = Game(players(), seed=32)
    g.start()
    g.discard("0", g.players[0].hand[0].id)
    p = g.players[1]
    last = C(7, Suit.HEARTS)
    b = C(5, Suit.HEARTS)
    c = C(6, Suit.HEARTS)
    install_cards(g, p, [b, c, last])
    p.remove_card(last.id)
    g.discard_pile = [last]
    g.phase = TurnPhase.DRAW
    g.take_last_discard("1", [last.id, b.id, c.id])
    with pytest.raises(InvalidMove):
        g.draw("1")


def test_cannot_take_discard_after_drawing():
    g = Game(players(), seed=33)
    g.start()
    g.discard("0", g.players[0].hand[0].id)
    p = g.players[1]
    last = C(7, Suit.HEARTS)
    b = C(5, Suit.HEARTS)
    c = C(6, Suit.HEARTS)
    install_cards(g, p, [b, c, last])
    p.remove_card(last.id)
    g.discard_pile = [last]
    g.phase = TurnPhase.DRAW
    g.draw("1")
    with pytest.raises(InvalidMove):
        g.take_last_discard("1", [last.id, b.id, c.id])


def test_later_drawn_completion_becomes_plug_if_player_has_no_plug():
    g = Game(players(3), seed=34)
    g.start()
    p0, p1, p2 = g.players
    group = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS)]
    p1_fillers = [C(2, Suit.CLUBS), C(3, Suit.CLUBS), C(9, Suit.DIAMONDS), C(10, Suit.DIAMONDS), C(12, Suit.CLUBS), C(13, Suit.DIAMONDS), C(2, Suit.SPADES)]
    p2_fillers = [C(3, Suit.SPADES), C(4, Suit.SPADES), C(9, Suit.CLUBS), C(10, Suit.CLUBS), C(12, Suit.SPADES), C(13, Suit.SPADES), C(2, Suit.DIAMONDS)]
    install_cards(g, p0, group)
    install_cards(g, p1, p1_fillers)
    install_cards(g, p2, p2_fillers)
    g.phase = TurnPhase.ACTION
    g.lower_group("0", [c.id for c in group])
    assert p1.plug is None
    # Put 8♥ in the deck as the card p1 will draw; remove it from anywhere else.
    target = C(8, Suit.HEARTS)
    fillers = [C(2, Suit.CLUBS), C(3, Suit.CLUBS), C(9, Suit.DIAMONDS), C(10, Suit.DIAMONDS), C(12, Suit.CLUBS), C(13, Suit.DIAMONDS)]
    install_cards(g, p1, fillers + [target])
    p1.remove_card(target.id)
    g.deck.cards.appendleft(target)
    g.current_index = 1
    g.phase = TurnPhase.DRAW
    g._turn_card_obtained = False
    g.draw("1")
    assert p1.plug is not None
    assert p1.plug.card == target
    assert p1.plug.target_group_id == p0.lowered_group.id


def test_cannot_lower_group_before_obtaining_turn_card():
    players = [Player("0", "A", PlayerType.HUMAN), Player("1", "B", PlayerType.HUMAN)]
    game = Game(players, seed=8080)
    game.start()
    game.discard("0", players[0].hand[0].id)
    # Build a guaranteed legal triple from cards removed from the undealt deck.
    players[1].hand.clear()
    triple = [
        Card("TEST-5H", Rank.FIVE, Suit.HEARTS),
        Card("TEST-6H", Rank.SIX, Suit.HEARTS),
        Card("TEST-7H", Rank.SEVEN, Suit.HEARTS),
    ]
    # Replace the player's hand and keep the test cards outside the engine's
    # normal physical-deck accounting; this test targets only phase gating.
    players[1].hand.extend(triple)
    with pytest.raises(InvalidMove, match="obtener una carta"):
        game.lower_group("1", [c.id for c in triple])
