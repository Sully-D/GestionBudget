from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.import_pipeline.ofx_parser import OfxParseError, parse_ofx

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_parse_ofx_sample_returns_two_transactions():
    raw = (FIXTURES_DIR / "sample.ofx").read_bytes()
    parsed = parse_ofx(raw)
    assert len(parsed) == 2

    first, second = parsed
    assert first.fitid == "2026061500001"
    assert first.date == date(2026, 6, 15)
    assert first.amount == Decimal("-45.90")
    assert first.label == "CARREFOUR MARKET"
    assert first.payee == "CARREFOUR MARKET"

    assert second.fitid == "2026060100002"
    assert second.date == date(2026, 6, 1)
    assert second.amount == Decimal("3200.00")
    assert second.label == "SAL JUILLET SASU X"
    assert second.payee == "SAL JUILLET SASU X"


def test_parse_ofx_empty_bytes_raises_ofx_parse_error():
    with pytest.raises(OfxParseError):
        parse_ofx(b"")


def test_parse_ofx_random_bytes_raises_ofx_parse_error():
    with pytest.raises(OfxParseError):
        parse_ofx(b"this is not an ofx file at all")


def test_parse_ofx_valid_but_no_transactions_returns_empty_list():
    # Fixture statique dédiée (pas de découpage à l'exécution de sample.ofx) :
    # un changement de structure de sample.ofx ne doit pas pouvoir casser ce
    # test sans rapport avec son contenu.
    raw = (FIXTURES_DIR / "empty_statement.ofx").read_bytes()
    parsed = parse_ofx(raw)
    assert parsed == []
