from decimal import Decimal
from pathlib import Path

import pytest

from app.import_pipeline.csv_parser import (
    ColumnMapping,
    CsvParseError,
    _parse_amount,
    _parse_date,
    compute_header_signature,
    parse_csv,
    preview_csv,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_csv_bytes():
    return (FIXTURES_DIR / "sample.csv").read_bytes()


@pytest.fixture
def sample_comma_delim_csv_bytes():
    return (FIXTURES_DIR / "sample_comma_delim.csv").read_bytes()


def test_preview_csv_detects_semicolon_columns_and_three_rows(sample_csv_bytes):
    preview = preview_csv(sample_csv_bytes)
    assert preview.columns == [
        "Date_Operation",
        "Montant_EUR",
        "Libelle_Complet",
        "Beneficiaire",
    ]
    assert len(preview.preview_rows) == 3
    assert preview.preview_rows[0] == [
        "01/07/2026",
        "-42,90",
        "CB CARREFOUR MARKET REIMS",
        "CARREFOUR",
    ]


def test_preview_csv_detects_comma_delimiter(sample_comma_delim_csv_bytes):
    preview = preview_csv(sample_comma_delim_csv_bytes)
    assert preview.columns == ["Date", "Montant", "Libelle", "Tiers"]
    assert len(preview.preview_rows) == 2


def test_preview_csv_empty_file_raises_csv_parse_error():
    with pytest.raises(CsvParseError):
        preview_csv(b"")


def test_preview_csv_header_only_raises_csv_parse_error():
    with pytest.raises(CsvParseError):
        preview_csv(b"Date;Montant;Libelle;Tiers\n")


def test_preview_csv_duplicate_headers_raises_csv_parse_error():
    with pytest.raises(CsvParseError):
        preview_csv(b"Date;Montant;Montant;Tiers\n01/07/2026;-1;2;X\n")


def test_parse_csv_skips_invalid_row_and_counts_it(sample_csv_bytes):
    mapping = ColumnMapping(
        date_column="Date_Operation",
        montant_column="Montant_EUR",
        libelle_column="Libelle_Complet",
        tiers_column="Beneficiaire",
    )
    parsed, skipped_count = parse_csv(sample_csv_bytes, mapping)
    assert len(parsed) == 3
    assert skipped_count == 1
    assert parsed[0].amount == Decimal("-42.90")
    assert parsed[0].label == "CB CARREFOUR MARKET REIMS"
    assert parsed[0].payee == "CARREFOUR"
    assert parsed[2].amount == Decimal("3200.00")


def test_parse_csv_unknown_mapped_column_raises_csv_parse_error(sample_csv_bytes):
    mapping = ColumnMapping(
        date_column="Colonne_Inexistante",
        montant_column="Montant_EUR",
        libelle_column="Libelle_Complet",
        tiers_column=None,
    )
    with pytest.raises(CsvParseError):
        parse_csv(sample_csv_bytes, mapping)


def test_parse_csv_duplicate_mapped_column_raises_csv_parse_error(sample_csv_bytes):
    mapping = ColumnMapping(
        date_column="Date_Operation",
        montant_column="Date_Operation",
        libelle_column="Libelle_Complet",
        tiers_column=None,
    )
    with pytest.raises(CsvParseError):
        parse_csv(sample_csv_bytes, mapping)


def test_parse_csv_without_tiers_column_sets_payee_none(sample_comma_delim_csv_bytes):
    mapping = ColumnMapping(
        date_column="Date",
        montant_column="Montant",
        libelle_column="Libelle",
        tiers_column=None,
    )
    parsed, skipped_count = parse_csv(sample_comma_delim_csv_bytes, mapping)
    assert skipped_count == 0
    assert len(parsed) == 2
    assert parsed[0].payee is None
    assert parsed[0].amount == Decimal("-42.90")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("-42,90", Decimal("-42.90")),
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("3200,00", Decimal("3200.00")),
        ("3 200,00", Decimal("3200.00")),
        ("", None),
        ("abc", None),
    ],
)
def test_parse_amount(raw, expected):
    assert _parse_amount(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["01/07/2026", "2026-07-01", "01-07-2026", "01.07.2026"],
)
def test_parse_date_accepted_formats(raw):
    from datetime import date

    assert _parse_date(raw) == date(2026, 7, 1)


def test_parse_date_unsupported_format_returns_none():
    assert _parse_date("July 1 2026") is None


def test_compute_header_signature_ignores_column_order():
    assert compute_header_signature(["Date", "Montant", "Libelle"]) == compute_header_signature(
        ["Libelle", "Date", "Montant"]
    )


def test_compute_header_signature_is_case_sensitive():
    assert compute_header_signature(["Date", "Montant"]) != compute_header_signature(
        ["date", "montant"]
    )


def test_compute_header_signature_differs_for_different_column_sets():
    assert compute_header_signature(["Date", "Montant", "Libelle"]) != compute_header_signature(
        ["Date", "Montant", "Libelle", "Tiers"]
    )
