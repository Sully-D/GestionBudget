from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.schema import RevenueSalaireUpsert
from app.budget.service import get_repartition_commune, upsert_salaire
from app.core.db import Base
from app.tags.model import Tag
from app.transactions.model import Transaction

PERIOD_START = date(2026, 3, 1)
PERIOD_PRECEDENTE = date(2026, 2, 1)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_repartition_commune_service.db"
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


def _add_tag(db, name="Charges", parent_id=None, level=1) -> Tag:
    tag = Tag(name=name, parent_id=parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _add_transaction(db, account, tx_date, amount, label="Dépense", payee=None) -> Transaction:
    tx = Transaction(
        account_id=account.account_id, date=tx_date, amount=amount, label=label, payee=payee
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def _tag_transaction(db, tx, tag) -> None:
    from app.transactions.model import TransactionTag

    db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
    db.commit()


def _set_revenu(db, account, amount) -> None:
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=amount), db
    )


def test_repartition_proportionnelle_au_reste_a_vivre(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    tag = _add_tag(db)
    _set_revenu(db, lui, Decimal("2000.00"))
    _set_revenu(db, elle, Decimal("1000.00"))
    tx_lui = _add_transaction(db, lui, date(2026, 3, 5), Decimal("-500.00"))
    _tag_transaction(db, tx_lui, tag)
    tx_elle = _add_transaction(db, elle, date(2026, 3, 5), Decimal("-200.00"))
    _tag_transaction(db, tx_elle, tag)

    # RàV Lui = 2000 - 500 = 1500 ; RàV Elle = 1000 - 200 = 800 ; total = 2300
    result = get_repartition_commune(Decimal("1000.00"), tag.tag_id, PERIOD_START, db)

    parts_by_name = {p.account_name: p for p in result.parts}
    assert parts_by_name["Personnel-Lui"].reste_a_vivre == Decimal("1500.00")
    assert parts_by_name["Personnel-Elle"].reste_a_vivre == Decimal("800.00")
    part_lui = (Decimal("1000.00") * Decimal("1500.00") / Decimal("2300.00")).quantize(Decimal("0.01"))
    part_elle = (Decimal("1000.00") * Decimal("800.00") / Decimal("2300.00")).quantize(Decimal("0.01"))
    assert parts_by_name["Personnel-Lui"].part == part_lui
    assert parts_by_name["Personnel-Elle"].part == part_elle


def test_reste_a_vivre_reflete_un_remboursement_deduit_des_charges(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    tag = _add_tag(db)
    _set_revenu(db, lui, Decimal("2000.00"))
    _set_revenu(db, elle, Decimal("1000.00"))
    tx_lui = _add_transaction(db, lui, date(2026, 3, 5), Decimal("-500.00"))
    _tag_transaction(db, tx_lui, tag)
    tx_remboursement = _add_transaction(db, lui, date(2026, 3, 6), Decimal("50.00"))
    _tag_transaction(db, tx_remboursement, tag)
    tx_elle = _add_transaction(db, elle, date(2026, 3, 5), Decimal("-200.00"))
    _tag_transaction(db, tx_elle, tag)

    # Charges Lui nettées : 500 - 50 = 450 -> RàV Lui = 2000 - 450 = 1550
    result = get_repartition_commune(Decimal("1000.00"), tag.tag_id, PERIOD_START, db)

    parts_by_name = {p.account_name: p for p in result.parts}
    assert parts_by_name["Personnel-Lui"].reste_a_vivre == Decimal("1550.00")


def test_depenses_sur_sous_tag_remontent_au_tag_parent(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    charges = _add_tag(db, name="Charges")
    fixes = _add_tag(db, name="Fixes", parent_id=charges.tag_id, level=2)
    _set_revenu(db, lui, Decimal("2000.00"))
    _set_revenu(db, elle, Decimal("1000.00"))
    tx_lui = _add_transaction(db, lui, date(2026, 3, 5), Decimal("-300.00"))
    _tag_transaction(db, tx_lui, fixes)
    tx_elle = _add_transaction(db, elle, date(2026, 3, 5), Decimal("-100.00"))
    _tag_transaction(db, tx_elle, fixes)

    result = get_repartition_commune(Decimal("500.00"), charges.tag_id, PERIOD_START, db)

    parts_by_name = {p.account_name: p for p in result.parts}
    assert parts_by_name["Personnel-Lui"].charges == Decimal("300.00")
    assert parts_by_name["Personnel-Elle"].charges == Decimal("100.00")


def test_refus_si_reste_a_vivre_negatif(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    tag = _add_tag(db)
    _set_revenu(db, lui, Decimal("100.00"))
    _set_revenu(db, elle, Decimal("1000.00"))
    tx_lui = _add_transaction(db, lui, date(2026, 3, 5), Decimal("-500.00"))
    _tag_transaction(db, tx_lui, tag)

    with pytest.raises(HTTPException) as exc_info:
        get_repartition_commune(Decimal("1000.00"), tag.tag_id, PERIOD_START, db)
    assert exc_info.value.status_code == 422


def test_refus_si_reste_a_vivre_exactement_nul(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    tag = _add_tag(db)
    _set_revenu(db, lui, Decimal("500.00"))
    _set_revenu(db, elle, Decimal("1000.00"))
    tx_lui = _add_transaction(db, lui, date(2026, 3, 5), Decimal("-500.00"))
    _tag_transaction(db, tx_lui, tag)

    with pytest.raises(HTTPException) as exc_info:
        get_repartition_commune(Decimal("1000.00"), tag.tag_id, PERIOD_START, db)
    assert exc_info.value.status_code == 422


def test_changement_de_tag_recalcule_le_reste_a_vivre(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    charges = _add_tag(db, name="Charges")
    loisirs = _add_tag(db, name="Loisirs")
    _set_revenu(db, lui, Decimal("2000.00"))
    _set_revenu(db, elle, Decimal("1000.00"))
    tx_charges = _add_transaction(db, lui, date(2026, 3, 5), Decimal("-500.00"))
    _tag_transaction(db, tx_charges, charges)
    tx_loisirs = _add_transaction(db, lui, date(2026, 3, 6), Decimal("-100.00"))
    _tag_transaction(db, tx_loisirs, loisirs)

    result_charges = get_repartition_commune(Decimal("1000.00"), charges.tag_id, PERIOD_START, db)
    result_loisirs = get_repartition_commune(Decimal("1000.00"), loisirs.tag_id, PERIOD_START, db)

    lui_charges = next(p for p in result_charges.parts if p.account_name == "Personnel-Lui")
    lui_loisirs = next(p for p in result_loisirs.parts if p.account_name == "Personnel-Lui")
    assert lui_charges.reste_a_vivre == Decimal("1500.00")
    assert lui_loisirs.reste_a_vivre == Decimal("1900.00")


def test_periode_differente_donne_reste_a_vivre_different(db):
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, name="Personnel-Elle")
    tag = _add_tag(db)
    _set_revenu(db, lui, Decimal("2000.00"))
    _set_revenu(db, elle, Decimal("1000.00"))
    tx_courante = _add_transaction(db, lui, date(2026, 3, 5), Decimal("-500.00"))
    _tag_transaction(db, tx_courante, tag)
    tx_precedente = _add_transaction(db, lui, date(2026, 2, 5), Decimal("-100.00"))
    _tag_transaction(db, tx_precedente, tag)

    result_courante = get_repartition_commune(Decimal("1000.00"), tag.tag_id, PERIOD_START, db)
    result_precedente = get_repartition_commune(Decimal("1000.00"), tag.tag_id, PERIOD_PRECEDENTE, db)

    lui_courante = next(p for p in result_courante.parts if p.account_name == "Personnel-Lui")
    lui_precedente = next(p for p in result_precedente.parts if p.account_name == "Personnel-Lui")
    assert lui_courante.reste_a_vivre == Decimal("1500.00")
    assert lui_precedente.reste_a_vivre == Decimal("1900.00")


def test_unknown_tag_returns_404(db):
    _add_account(db, name="Personnel-Lui")
    _add_account(db, name="Personnel-Elle")
    with pytest.raises(HTTPException) as exc_info:
        get_repartition_commune(Decimal("1000.00"), 999, PERIOD_START, db)
    assert exc_info.value.status_code == 404
