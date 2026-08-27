from golpeado.deck import Deck
from golpeado.models import Rank, Suit


def test_standard_deck_has_52_unique_physical_cards():
    deck = Deck.standard(seed=1)
    assert len(deck) == 52
    assert len({card.id for card in deck.cards}) == 52
    assert len({card.rank for card in deck.cards}) == 13
    assert len({card.suit for card in deck.cards}) == 4


def test_exactly_four_cards_per_rank_and_thirteen_per_suit():
    deck = Deck.standard(seed=2)
    for rank in Rank:
        assert sum(card.rank == rank for card in deck.cards) == 4
    for suit in Suit:
        assert sum(card.suit == suit for card in deck.cards) == 13


def test_seeded_shuffle_is_reproducible():
    a = Deck.standard(seed=123)
    b = Deck.standard(seed=123)
    assert [c.id for c in a.cards] == [c.id for c in b.cards]


def test_different_seed_changes_order():
    a = Deck.standard(seed=123)
    b = Deck.standard(seed=124)
    assert [c.id for c in a.cards] != [c.id for c in b.cards]
