
import pytest
from golpeado.game import Game, GameState, TurnPhase, InvalidMove
from golpeado.models import Card, Player, Suit, Rank, Plug, Group
from golpeado.groups import is_valid_group, completing_cards_for_group

def C(v,s=Suit.HEARTS):
    r=Rank.ACE if v==1 else Rank(v)
    return Card(f"{r.name}-{s.name}",r,s)
def players(n=2): return [Player(str(i),f"P{i}") for i in range(n)]
def install(g,p,cards):
    ids={c.id for c in cards}
    g.deck.cards=type(g.deck.cards)(c for c in g.deck.cards if c.id not in ids)
    g.discard_pile=[c for c in g.discard_pile if c.id not in ids]
    for q in g.players:
        q.hand[:]=[c for c in q.hand if c.id not in ids]
    p.hand[:]=cards
def test_distribution_and_52_card_conservation():
    g=Game(players(4),seed=1);g.start()
    assert [len(p.hand) for p in g.players]==[8,7,7,7]
    assert len(g.deck)+sum(map(lambda p:len(p.hand),g.players))+len(g.discard_pile)+len(g.out_of_play)==52
def test_group_rules():
    assert is_valid_group([C(1),C(2),C(3),C(4)])
    assert is_valid_group([C(11),C(12),C(13),C(1)])
    assert is_valid_group([C(7),C(8),C(9)])
    assert is_valid_group([C(7),C(7,Suit.CLUBS),C(7,Suit.SPADES),C(7,Suit.DIAMONDS)])
    assert not is_valid_group([C(13),C(1),C(2)])
    assert not is_valid_group([C(8),C(9),C(11)])
def test_ace_plug_endpoints():
    assert C(4) in completing_cards_for_group([C(1),C(2),C(3)])
    assert C(1) in completing_cards_for_group([C(11),C(12),C(13)])
    assert C(11) in completing_cards_for_group([C(12),C(13),C(1)])
def test_take_discard_must_lower_and_is_only_last_and_replaces_draw():
    g=Game(players(),seed=2);g.start();p=g.players[0]
    g.discard("0",p.hand[0].id);p=g.players[1]
    last=C(7); a=C(5); b=C(6); fill=[C(2,Suit.CLUBS),C(3,Suit.CLUBS),C(9,Suit.DIAMONDS),C(10,Suit.DIAMONDS),C(12,Suit.CLUBS)]
    install(g,p,[a,b,last]+fill); p.remove_card(last.id); g.discard_pile=[last]; g.phase=TurnPhase.DRAW
    before=len(g.deck)
    g.take_last_discard("1",[last.id,a.id,b.id])
    assert len(g.deck)==before and p.lowered_group is not None and g.phase==TurnPhase.DISCARD
    with pytest.raises(InvalidMove): g.take_last_discard("1",[last.id,a.id,b.id])
def test_four_group_no_plug_and_three_group_exact_plug():
    g=Game(players(3),seed=3);g.start();p0,p1,p2=g.players
    group4=[C(7,s) for s in Suit]; install(g,p0,group4); install(g,p1,[C(8),C(9),C(10)]);g.phase=TurnPhase.ACTION
    g.lower_group("0",[c.id for c in group4]); assert p1.plug is None
    # fresh game for exact plug
    g=Game(players(2),seed=4);g.start();p0,p1=g.players
    group=[C(5),C(6),C(7)]; install(g,p0,group); install(g,p1,[C(8),C(2),C(3),C(4)]);g.phase=TurnPhase.ACTION
    g.lower_group("0",[c.id for c in group])
    assert p1.plug and p1.plug.card==C(8) and p1.plug.target_group_id==p0.lowered_group.id
def test_plug_can_be_acquired_later_and_only_one_is_kept():
    g=Game(players(3),seed=5);g.start();p0,p1,p2=g.players
    group=[C(5),C(6),C(7)]; install(g,p0,group); install(g,p1,[C(2),C(3),C(9)]); install(g,p2,[C(8),C(10),C(11)]);g.phase=TurnPhase.ACTION
    g.lower_group("0",[c.id for c in group]); assert p1.plug is None and p2.plug is not None
    # Give p1 8H later, then refresh; one plug only.
    p1.hand.append(C(8)); g._refresh_plug_for_player(p1); assert p1.plug is not None
    old=p1.plug
    p1.hand.append(C(4)); g._refresh_plug_for_player(p1); assert p1.plug==old
def test_take_discard_four_has_no_plug():
    g=Game(players(2),seed=6);g.start();p=g.players[0];q=g.players[1]
    g.discard("0",p.hand[0].id); last=C(8); group=[C(5),C(6),last,C(7)]
    install(g,q,group); # make last only on discard
    q.remove_card(last.id); g.discard_pile=[last];g.phase=TurnPhase.DRAW
    g.take_last_discard("1",[C(5).id,C(6).id,C(7).id,last.id])
    assert q.plug is None
def test_one_lowered_group_per_game_and_four_plus_three_victory():
    g=Game(players(),seed=7);g.start();p=g.players[0]
    four=[C(7,s) for s in Suit]; three=[C(9,Suit.CLUBS),C(10,Suit.CLUBS),C(11,Suit.CLUBS)]
    install(g,p,four+three);g.phase=TurnPhase.ACTION
    g.lower_group("0",[c.id for c in four]);assert g.state==GameState.WON
def test_two_fours_require_discard_then_win():
    g=Game(players(),seed=8);g.start();p=g.players[0]
    a=[C(7,s) for s in Suit];b=[C(9,s) for s in Suit]
    install(g,p,a+b);g.phase=TurnPhase.ACTION;g.lower_group("0",[c.id for c in a])
    assert g.state==GameState.PLAYING and g.can_win("0")=="two_group4_before_discard"
    g.discard("0",b[0].id);assert g.state==GameState.WON and g.winner.reason=="group4_plus_group3"
def test_actual_3_3_plug_victory():
    g=Game(players(2),seed=9);g.start();p0,p1=g.players
    public=[C(5),C(6),C(7)]
    p1cards=[C(8),C(9,Suit.SPADES),C(10,Suit.SPADES),C(11,Suit.SPADES),C(2,Suit.CLUBS),C(3,Suit.CLUBS),C(4,Suit.CLUBS)]
    install(g,p0,public);install(g,p1,p1cards);g.phase=TurnPhase.ACTION
    g.lower_group("0",[c.id for c in public])
    assert p1.plug and p1.plug.card==C(8)
    g.current_index=1;g.phase=TurnPhase.ACTION;g._turn_card_obtained=True
    g.lower_group("1",[C(9,Suit.SPADES).id,C(10,Suit.SPADES).id,C(11,Suit.SPADES).id])
    assert g.state==GameState.WON and g.winner.player_id=="1"
def test_abandonment_and_recycle():
    g=Game(players(4),seed=10);g.start();cur=g.current_player;cards=list(cur.hand);g.abandon(cur.id)
    assert cur.id not in g.active_player_ids and g.current_player.id=="1"
    assert all(c.id not in [x.id for x in list(g.deck.cards)+g.discard_pile] for c in cards)
    g2=Game(players(),seed=11);cards=list(g2.deck.cards);g2.discard_pile=cards[:10];g2.deck.cards.clear();g2.force_recycle_for_test()
    assert len(g2.deck)==9 and g2.last_discard==cards[9] and cards[9] not in g2.deck.cards
