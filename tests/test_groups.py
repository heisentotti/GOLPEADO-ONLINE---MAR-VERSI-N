import pytest

from golpeado.groups import completing_cards_for_group, group_type, is_valid_group
from golpeado.models import Card, Rank, Suit


def C(value, suit=Suit.HEARTS):
    rank = Rank.ACE if value == 1 else Rank(value)
    return Card(f"{rank.name}-{suit.name}", rank, suit)


def ranks(values, suit=Suit.HEARTS):
    return [C(value, suit) for value in values]


def test_standard_deck_card_identity_is_physical():
    assert C(7, Suit.HEARTS).id != C(7, Suit.SPADES).id


def test_equal_rank_groups_of_3_and_4_are_valid():
    assert is_valid_group([C(7, Suit.SPADES), C(7, Suit.HEARTS), C(7, Suit.DIAMONDS)])
    assert is_valid_group([C(7, Suit.SPADES), C(7, Suit.HEARTS), C(7, Suit.DIAMONDS), C(7, Suit.CLUBS)])
    assert group_type([C(7, Suit.SPADES), C(7, Suit.HEARTS), C(7, Suit.DIAMONDS)]) == "same_rank"


def test_equal_rank_invalid_sizes_and_duplicate_physical_card():
    assert not is_valid_group([C(7, Suit.SPADES), C(7, Suit.HEARTS)])
    assert not is_valid_group([C(7, s) for s in Suit] + [C(7, Suit.SPADES)])
    duplicate = C(7, Suit.HEARTS)
    assert not is_valid_group([duplicate, duplicate, C(7, Suit.SPADES)])


def test_straights_same_suit_3_and_4():
    assert is_valid_group(ranks([5, 6, 7]))
    assert is_valid_group(ranks([5, 6, 7, 8]))
    assert group_type(ranks([5, 6, 7])) == "straight"


def test_straight_must_use_same_suit():
    assert not is_valid_group([C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.SPADES)])


def test_ace_low_and_high_are_valid():
    assert is_valid_group(ranks([1, 2, 3, 4]))
    assert is_valid_group(ranks([1, 2, 3]))
    assert is_valid_group(ranks([11, 12, 13, 1]))
    assert is_valid_group(ranks([11, 12, 13]))


def test_king_ace_two_three_is_invalid():
    assert not is_valid_group(ranks([13, 1, 2, 3]))
    assert not is_valid_group(ranks([13, 1, 2]))


def test_all_normal_four_card_straight_boundaries():
    for start in range(2, 11):
        assert is_valid_group(ranks([start, start + 1, start + 2, start + 3]))


def test_three_card_straights_are_any_three_inside_a_legal_four_window():
    assert is_valid_group(ranks([4, 5, 6]))
    assert is_valid_group(ranks([6, 7, 8]))
    assert is_valid_group(ranks([10, 11, 12]))
    assert is_valid_group(ranks([12, 13, 1]))


def test_invalid_nonconsecutive_three_card_straight():
    assert not is_valid_group(ranks([5, 7, 8]))
    assert not is_valid_group(ranks([1, 3, 4]))


def test_5_6_7_has_both_4_and_8_as_plug_candidates():
    result = completing_cards_for_group(ranks([5, 6, 7]))
    assert {(card.rank, card.suit) for card in result} == {
        (Rank.FOUR, Suit.HEARTS),
        (Rank.EIGHT, Suit.HEARTS),
    }


def test_6_7_8_has_both_5_and_9():
    result = completing_cards_for_group(ranks([6, 7, 8]))
    assert {(card.rank, card.suit) for card in result} == {
        (Rank.FIVE, Suit.HEARTS),
        (Rank.NINE, Suit.HEARTS),
    }


def test_7_8_9_has_both_6_and_10():
    result = completing_cards_for_group(ranks([7, 8, 9]))
    assert {(card.rank, card.suit) for card in result} == {
        (Rank.SIX, Suit.HEARTS),
        (Rank.TEN, Suit.HEARTS),
    }


def test_10_j_q_has_9_and_k():
    result = completing_cards_for_group(ranks([10, 11, 12]))
    assert {(card.rank, card.suit) for card in result} == {
        (Rank.NINE, Suit.HEARTS),
        (Rank.KING, Suit.HEARTS),
    }


def test_j_q_k_has_ten_and_ace_as_plug_candidates():
    result = completing_cards_for_group(ranks([11, 12, 13]))
    assert {(card.rank, card.suit) for card in result} == {(Rank.TEN, Suit.HEARTS), (Rank.ACE, Suit.HEARTS)}


def test_2_3_4_has_ace_and_5_as_plug_candidates():
    result = completing_cards_for_group(ranks([2, 3, 4]))
    assert {(card.rank, card.suit) for card in result} == {
        (Rank.ACE, Suit.HEARTS), (Rank.FIVE, Suit.HEARTS)
    }


def test_q_k_a_has_only_jack_as_plug_candidate():
    result = completing_cards_for_group(ranks([12, 13, 1]))
    assert {(card.rank, card.suit) for card in result} == {(Rank.JACK, Suit.HEARTS)}


def test_a_2_3_has_only_4_as_plug():
    result = completing_cards_for_group(ranks([1, 2, 3]))
    assert {(card.rank, card.suit) for card in result} == {(Rank.FOUR, Suit.HEARTS)}


def test_equal_rank_three_has_only_fourth_suit():
    result = completing_cards_for_group([
        C(7, Suit.SPADES), C(7, Suit.HEARTS), C(7, Suit.DIAMONDS)
    ])
    assert {(card.rank, card.suit) for card in result} == {(Rank.SEVEN, Suit.CLUBS)}


def test_four_card_group_has_no_completion_candidates():
    assert completing_cards_for_group(ranks([5, 6, 7, 8])) == set()
