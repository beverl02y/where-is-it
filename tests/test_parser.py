import pytest

from app.query_parser import QueryParser


@pytest.fixture
def parser(settings):
    return QueryParser(settings.objects, settings.ambiguous_terms)


@pytest.mark.parametrize("q,expected", [
    ("Where are my glasses?", "glasses"),
    ("Where is my wallet?", "wallet"),
    ("where's my phone", "phone"),
    ("I can't find my AirPods!!", "earphones"),
    ("where did i leave my phone charger", "charger"),   # not 'phone'
    ("where are my earphones", "earphones"),             # not 'phone'
    ("Where is my student ID card?", "card"),
    ("where is my scrunchie", "hairtie"),
    ("where is my hair tie", "hairtie"),
    ("where is my phone case", "phone"),
    ("WHERE ARE MY SPECS", "glasses"),
    ("where are my chargers", "charger"),
])
def test_recognises_objects(parser, q, expected):
    r = parser.parse(q)
    assert r.status == "ok" and r.object == expected, r


def test_two_objects_is_ambiguous(parser):
    r = parser.parse("where are my wallet and phone")
    assert r.status == "ambiguous" and set(r.candidates) == {"wallet", "phone"}


def test_ambiguous_term(parser):
    r = parser.parse("where is my cable")
    assert r.status == "ambiguous" and set(r.candidates) == {"charger", "earphones"}


def test_unsupported(parser):
    r = parser.parse("where are my keys")
    assert r.status == "unsupported" and r.term == "keys"


def test_empty(parser):
    assert parser.parse("where is it?").status == "empty"
