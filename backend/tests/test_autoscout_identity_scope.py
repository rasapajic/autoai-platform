import pytest
from bs4 import BeautifulSoup

from app.scrapers.autoscout24 import _extract_make_model, _parse_card


def card(headline):
    soup = BeautifulSoup('<article data-guid="regression-sample" data-price="12000"><h2></h2></article>', "html.parser")
    soup.h2.string = headline
    return soup.article


@pytest.mark.parametrize("headline", [
    "Trucks-Lkw Iveco Laadklep aanwezig!",
    "Caravans-Wohnm Elnagh P250 Fiat 2.8 JTD",
    "Caravans-Wohnm Knaus Van I 650 Meg VAN I 650 MEG",
    "Trailer-Anhänger Brian James Transporter",
])
def test_non_car_source_categories_never_become_car_listings(headline):
    assert _parse_card(card(headline)) is None


def test_oldtimer_category_is_not_a_manufacturer():
    row = _parse_card(card("Oldtimer Panther Kallista 2.8 V6 **NL-AUTO**LHD**"))
    assert (row["make"], row["model"]) == ("Panther Westwinds", "Kallista")
    assert row["description"].startswith("Oldtimer Panther")


def test_microcar_manufacturer_does_not_become_the_other_brand_in_title():
    row = _parse_card(card("Microcar M.Go Aixam GTi ABS Brommobiel"))
    assert (row["make"], row["model"]) == ("Microcar", "M.Go")


def test_unknown_oldtimer_is_not_guessed_from_a_later_brand_mention():
    assert _extract_make_model("Oldtimer Unknowncar met BMW motor") == (None, None)


def test_ordinary_and_classic_cars_keep_their_identity():
    for headline in ["BMW X5 3.0 Diesel", "Oldtimer BMW X5 3.0 Diesel"]:
        row = _parse_card(card(headline))
        assert (row["make"], row["model"]) == ("BMW", "X5")


def test_category_words_inside_a_regular_car_headline_do_not_exclude_it():
    row = _parse_card(card("Fiat 500 Caravans-Wohnm onderdelen"))
    assert (row["make"], row["model"]) == ("Fiat", "500")
