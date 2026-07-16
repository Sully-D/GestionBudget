from datetime import date
from decimal import Decimal

import pydantic
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.schema import CoupleChargesPercentageUpdate
from app.budget.service import get_recap_couple, update_couple_charges_percentage
from app.core.db import Base
from app.core.period import add_months
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_recap_couple_service.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    yield session
    session.close()


def _add_account(db, is_common=False, name="Personnel-Lui", start_day=1) -> Account:
    account = Account(name=name, is_common=is_common, start_day=start_day)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _add_tag(db, name="Revenus", parent_id=None, level=1) -> Tag:
    tag = Tag(name=name, parent_id=parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _add_transaction(db, account, tx_date, amount, label="Mouvement", payee=None) -> Transaction:
    tx = Transaction(
        account_id=account.account_id, date=tx_date, amount=amount, label=label, payee=payee
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def _tag_transaction(db, tx, tag) -> None:
    db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
    db.commit()


def _add_4_tags(db):
    return {
        "Revenus": _add_tag(db, name="Revenus"),
        "Charges": _add_tag(db, name="Charges"),
        "Virements compte commun": _add_tag(db, name="Virements compte commun"),
        "Investissements": _add_tag(db, name="Investissements"),
    }


def _month_start_before(reference_month_start: date, count: int) -> date:
    year = reference_month_start.year
    month = reference_month_start.month - count
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


def _last_n_month_starts(n: int) -> list[date]:
    today = date.today()
    current_month_start = today.replace(day=1)
    last_included = _month_start_before(current_month_start, 1)
    first_included = _month_start_before(last_included, n - 1)
    return [add_months(first_included, i) for i in range(n)]


def test_happy_path_averages_over_calendar_months(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    tags = _add_4_tags(db)

    month1, month2 = _last_n_month_starts(2)

    tx = _add_transaction(db, lui, month1, Decimal("1000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, lui, month1, Decimal("-200.00"))
    _tag_transaction(db, tx, tags["Charges"])
    tx = _add_transaction(db, lui, month2, Decimal("1000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, lui, month2, Decimal("-400.00"))
    _tag_transaction(db, tx, tags["Charges"])
    tx = _add_transaction(db, lui, month2, Decimal("-100.00"))
    _tag_transaction(db, tx, tags["Virements compte commun"])

    tx = _add_transaction(db, elle, month1, Decimal("800.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, elle, month2, Decimal("800.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, elle, month2, Decimal("-100.00"))
    _tag_transaction(db, tx, tags["Investissements"])

    result = get_recap_couple(commun.account_id, 2, db)

    rows_by_name = {r.account_name: r for r in result.rows}
    assert rows_by_name["Personnel-Lui"].revenus == Decimal("1000.00")
    assert rows_by_name["Personnel-Lui"].charges == Decimal("300.00")
    assert rows_by_name["Personnel-Lui"].virements == Decimal("50.00")
    assert rows_by_name["Personnel-Lui"].investissements == Decimal("0.00")
    assert rows_by_name["Personnel-Lui"].charges_plus_virements == Decimal("350.00")
    assert rows_by_name["Personnel-Lui"].reste_a_vivre == Decimal("650.00")

    assert rows_by_name["Personnel-Elle"].revenus == Decimal("800.00")
    assert rows_by_name["Personnel-Elle"].investissements == Decimal("50.00")
    assert rows_by_name["Personnel-Elle"].reste_a_vivre == Decimal("750.00")

    assert result.total_revenus == Decimal("1800.00")
    assert result.total_charges == Decimal("300.00")
    assert result.total_virements == Decimal("50.00")
    assert result.total_investissements == Decimal("50.00")
    assert result.total_reste_a_vivre == Decimal("1400.00")

    # NB% jamais enregistré : Tableau 2 non calculable, mais aucune erreur.
    assert result.couple_charges_percentage is None
    assert result.budget_charges_convenu is None
    assert result.reste_disponible is None


def test_month_without_transaction_counts_as_zero_in_average(db):
    lui = _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    tags = _add_4_tags(db)

    # N=3 : seul le mois du milieu porte une transaction, les 2 autres sont vides.
    month1, month2, month3 = _last_n_month_starts(3)
    tx = _add_transaction(db, lui, month2, Decimal("900.00"))
    _tag_transaction(db, tx, tags["Revenus"])

    result = get_recap_couple(commun.account_id, 3, db)

    lui_row = next(r for r in result.rows if r.account_name == "Personnel-Lui")
    assert lui_row.revenus == Decimal("300.00")  # 900 / 3, division toujours par N


def test_missing_tag_raises_422_naming_the_tag(db):
    _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    _add_tag(db, name="Revenus")
    _add_tag(db, name="Charges")
    _add_tag(db, name="Virements compte commun")
    # "Investissements" volontairement absent.

    with pytest.raises(HTTPException) as exc_info:
        get_recap_couple(commun.account_id, 1, db)
    assert exc_info.value.status_code == 422
    assert "Investissements" in exc_info.value.detail


def test_ambiguous_tag_raises_422(db):
    _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    _add_tag(db, name="Revenus")
    _add_tag(db, name="Charges")
    _add_tag(db, name="Charges")  # doublon : Tag.name n'est pas unique en base
    _add_tag(db, name="Virements compte commun")
    _add_tag(db, name="Investissements")

    with pytest.raises(HTTPException) as exc_info:
        get_recap_couple(commun.account_id, 1, db)
    assert exc_info.value.status_code == 422


def test_months_below_one_raises_422(db):
    commun = _add_account(db, name="Commun", is_common=True)
    with pytest.raises(HTTPException) as exc_info:
        get_recap_couple(commun.account_id, 0, db)
    assert exc_info.value.status_code == 422


def test_months_above_120_raises_422_not_500(db):
    commun = _add_account(db, name="Commun", is_common=True)
    with pytest.raises(HTTPException) as exc_info:
        get_recap_couple(commun.account_id, 100000, db)
    assert exc_info.value.status_code == 422


def test_hierarchical_collision_between_the_4_tags_raises_422(db):
    _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    _add_tag(db, name="Revenus")
    charges = _add_tag(db, name="Charges")
    _add_tag(db, name="Virements compte commun", parent_id=charges.tag_id, level=2)
    _add_tag(db, name="Investissements")

    with pytest.raises(HTTPException) as exc_info:
        get_recap_couple(commun.account_id, 1, db)
    assert exc_info.value.status_code == 422
    assert "Virements compte commun" in exc_info.value.detail
    assert "Charges" in exc_info.value.detail


def test_non_common_account_raises_422(db):
    lui = _add_account(db, name="Personnel-Lui")
    with pytest.raises(HTTPException) as exc_info:
        get_recap_couple(lui.account_id, 1, db)
    assert exc_info.value.status_code == 422


def test_unknown_account_raises_404(db):
    with pytest.raises(HTTPException) as exc_info:
        get_recap_couple(999, 1, db)
    assert exc_info.value.status_code == 404


def test_couple_charges_percentage_persists_and_recomputes_table_2(db):
    lui = _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    tags = _add_4_tags(db)
    month1, = _last_n_month_starts(1)
    tx = _add_transaction(db, lui, month1, Decimal("2000.00"))
    _tag_transaction(db, tx, tags["Revenus"])

    update_couple_charges_percentage(
        CoupleChargesPercentageUpdate(account_id=commun.account_id, percentage=Decimal("40")), db
    )

    result = get_recap_couple(commun.account_id, 1, db)
    assert result.couple_charges_percentage == Decimal("40.00")
    assert result.budget_charges_convenu == Decimal("800.00")  # 40% de 2000
    assert result.reste_disponible == Decimal("1200.00")


def test_couple_charges_percentage_reloaded_unchanged_across_calls(db):
    _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    _add_4_tags(db)

    update_couple_charges_percentage(
        CoupleChargesPercentageUpdate(account_id=commun.account_id, percentage=Decimal("55.5")), db
    )

    first_call = get_recap_couple(commun.account_id, 1, db)
    second_call = get_recap_couple(commun.account_id, 1, db)
    assert first_call.couple_charges_percentage == Decimal("55.50")
    assert second_call.couple_charges_percentage == Decimal("55.50")


def test_update_percentage_on_non_common_account_raises_422(db):
    lui = _add_account(db, name="Personnel-Lui")
    with pytest.raises(HTTPException) as exc_info:
        update_couple_charges_percentage(
            CoupleChargesPercentageUpdate(account_id=lui.account_id, percentage=Decimal("10")), db
        )
    assert exc_info.value.status_code == 422


def test_percentage_over_100_rejected_by_schema_validation():
    with pytest.raises(pydantic.ValidationError):
        CoupleChargesPercentageUpdate(account_id=1, percentage=Decimal("150"))


def test_percentage_negative_rejected_by_schema_validation():
    with pytest.raises(pydantic.ValidationError):
        CoupleChargesPercentageUpdate(account_id=1, percentage=Decimal("-5"))


def test_virement_happy_path_matches_design_notes_example(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    commun.reference_balance = Decimal("500.00")
    db.commit()
    tags = _add_4_tags(db)
    month1, = _last_n_month_starts(1)

    tx = _add_transaction(db, lui, month1, Decimal("3000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, lui, month1, Decimal("-800.00"))
    _tag_transaction(db, tx, tags["Charges"])

    tx = _add_transaction(db, elle, month1, Decimal("2000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, elle, month1, Decimal("-600.00"))
    _tag_transaction(db, tx, tags["Charges"])

    result = get_recap_couple(commun.account_id, 1, db)

    assert result.virement_error is None
    rows_by_name = {r.account_name: r for r in result.rows}
    # Exemple numérique des Design Notes de la spec :
    # besoin_total = 1400 + 500 = 1900 ; part Lui = 3000/5000 * 1900 = 1140 -> virement 340
    # part Elle = 2000/5000 * 1900 = 760 -> virement 160
    assert rows_by_name["Personnel-Lui"].virement == Decimal("340.00")
    assert rows_by_name["Personnel-Elle"].virement == Decimal("160.00")


def test_virement_reflects_reimbursement_deducted_from_charges(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    commun.reference_balance = Decimal("500.00")
    db.commit()
    tags = _add_4_tags(db)
    month1, = _last_n_month_starts(1)

    tx = _add_transaction(db, lui, month1, Decimal("3000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, lui, month1, Decimal("-800.00"))
    _tag_transaction(db, tx, tags["Charges"])
    # Remboursement (mutuelle, etc.) taggé "Charges" : déduit du total, jamais ignoré.
    tx = _add_transaction(db, lui, month1, Decimal("100.00"))
    _tag_transaction(db, tx, tags["Charges"])

    tx = _add_transaction(db, elle, month1, Decimal("2000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, elle, month1, Decimal("-600.00"))
    _tag_transaction(db, tx, tags["Charges"])

    result = get_recap_couple(commun.account_id, 1, db)

    assert result.virement_error is None
    rows_by_name = {r.account_name: r for r in result.rows}
    # Charges Lui nettées : 800 - 100 = 700. total_charges = 700 + 600 = 1300.
    # besoin_total = 1300 + 500 = 1800 ; part Lui = 3000/5000 * 1800 = 1080 -> virement 380
    # part Elle = 2000/5000 * 1800 = 720 -> virement 120
    assert rows_by_name["Personnel-Lui"].charges == Decimal("700.00")
    assert result.total_charges == Decimal("1300.00")
    assert rows_by_name["Personnel-Lui"].virement == Decimal("380.00")
    assert rows_by_name["Personnel-Elle"].virement == Decimal("120.00")


def test_virement_recalculates_with_selected_months_window(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    commun.reference_balance = Decimal("1000.00")
    db.commit()
    tags = _add_4_tags(db)
    month1, month2 = _last_n_month_starts(2)

    for month in (month1, month2):
        tx = _add_transaction(db, lui, month, Decimal("3000.00"))
        _tag_transaction(db, tx, tags["Revenus"])
        tx = _add_transaction(db, lui, month, Decimal("-800.00"))
        _tag_transaction(db, tx, tags["Charges"])
        tx = _add_transaction(db, elle, month, Decimal("2000.00"))
        _tag_transaction(db, tx, tags["Revenus"])
        tx = _add_transaction(db, elle, month, Decimal("-600.00"))
        _tag_transaction(db, tx, tags["Charges"])

    result = get_recap_couple(commun.account_id, 2, db)

    assert result.virement_error is None
    rows_by_name = {r.account_name: r for r in result.rows}
    # Moyennes identiques au cas N=1 (les 2 mois sont identiques) mais Solde de référence
    # différent (1000 au lieu de 500) : besoin_total = 1400 + 1000 = 2400.
    # Part Lui = 3000/5000 * 2400 = 1440 -> virement 640 ; Elle = 960 -> virement 360.
    assert rows_by_name["Personnel-Lui"].virement == Decimal("640.00")
    assert rows_by_name["Personnel-Elle"].virement == Decimal("360.00")


def test_virement_error_when_reference_balance_not_set(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    tags = _add_4_tags(db)
    month1, = _last_n_month_starts(1)

    tx = _add_transaction(db, lui, month1, Decimal("3000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, elle, month1, Decimal("2000.00"))
    _tag_transaction(db, tx, tags["Revenus"])

    result = get_recap_couple(commun.account_id, 1, db)

    assert result.virement_error is not None
    assert all(r.virement is None for r in result.rows)
    # Tableaux 1/2 non affectés par l'échec soft du calcul de virement.
    assert result.total_revenus == Decimal("5000.00")


def test_virement_error_when_total_revenus_zero(db):
    _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    commun.reference_balance = Decimal("500.00")
    db.commit()
    _add_4_tags(db)

    result = get_recap_couple(commun.account_id, 1, db)

    assert result.virement_error is not None
    assert all(r.virement is None for r in result.rows)
    assert result.total_revenus == Decimal("0.00")


def test_virement_error_when_a_computed_virement_is_negative(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    commun = _add_account(db, name="Commun", is_common=True)
    commun.reference_balance = Decimal("0.00")
    db.commit()
    tags = _add_4_tags(db)
    month1, = _last_n_month_starts(1)

    # Lui a déjà payé bien plus que sa part théorique proportionnelle à son revenu.
    tx = _add_transaction(db, lui, month1, Decimal("1000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, lui, month1, Decimal("-900.00"))
    _tag_transaction(db, tx, tags["Charges"])

    tx = _add_transaction(db, elle, month1, Decimal("1000.00"))
    _tag_transaction(db, tx, tags["Revenus"])
    tx = _add_transaction(db, elle, month1, Decimal("-100.00"))
    _tag_transaction(db, tx, tags["Charges"])

    result = get_recap_couple(commun.account_id, 1, db)

    assert result.virement_error is not None
    assert all(r.virement is None for r in result.rows)
    # Aucune régression sur les Tableaux 1/2 malgré l'échec soft du calcul de virement.
    assert result.total_charges == Decimal("1000.00")
