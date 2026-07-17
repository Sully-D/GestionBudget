from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.schema import BudgetTargetUpsert, RevenueSalaireUpsert
from app.budget.service import get_tag_tracking, upsert_budget_target, upsert_salaire
from app.core.db import Base
from app.tags.model import Tag
from app.tags.service import delete_tag
from app.transactions.model import Transaction, TransactionTag


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_tracking_service.db"
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


def _add_tag(db, name="Alimentation", parent_id=None, level=1) -> Tag:
    tag = Tag(name=name, parent_id=parent_id, level=level)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _add_expense(db, account, tag, amount, tx_date) -> Transaction:
    tx = Transaction(
        account_id=account.account_id,
        date=tx_date,
        amount=amount,
        label="Dépense",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
    db.commit()
    return tx


def _add_expense_multi_tag(db, account, tags, amount, tx_date) -> Transaction:
    tx = Transaction(
        account_id=account.account_id,
        date=tx_date,
        amount=amount,
        label="Dépense",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    for tag in tags:
        db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
    db.commit()
    return tx


def _current_period_start(today: date) -> date:
    return date(today.year, today.month, 1)


def test_tag_with_target_and_spending_below_target_has_positive_gap(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    _add_expense(db, account, tag, Decimal("-150.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("150.00")
    assert row.target_amount == Decimal("200.00")
    assert row.gap == Decimal("50.00")
    assert row.projection is not None


def test_tag_with_target_and_overspend_has_negative_gap(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    _add_expense(db, account, tag, Decimal("-300.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.target_amount == Decimal("200.00")
    assert row.gap == Decimal("-100.00")


def test_tag_without_target_has_only_spent(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    _add_expense(db, account, tag, Decimal("-42.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("42.00")
    assert row.target_percentage is None
    assert row.target_amount is None
    assert row.gap is None
    assert row.projection is None


def test_parent_aggregates_direct_plus_children_three_levels(db):
    account = _add_account(db)
    grandparent = _add_tag(db, name="Vie quotidienne", level=1)
    parent = _add_tag(db, name="Alimentation", parent_id=grandparent.tag_id, level=2)
    child = _add_tag(db, name="Restaurant", parent_id=parent.tag_id, level=3)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, grandparent, Decimal("-5.00"), today)
    _add_expense(db, account, parent, Decimal("-20.00"), today)
    _add_expense(db, account, child, Decimal("-10.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[child.tag_id].spent == Decimal("10.00")
    assert by_id[parent.tag_id].spent == Decimal("30.00")
    assert by_id[grandparent.tag_id].spent == Decimal("35.00")


def test_hierarchy_two_levels_parent_immediately_followed_by_children(db):
    account = _add_account(db)
    parent = _add_tag(db, name="Charges", level=1)
    fixes = _add_tag(db, name="Fixes", parent_id=parent.tag_id, level=2)
    variables = _add_tag(db, name="Variables", parent_id=parent.tag_id, level=2)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, fixes, Decimal("-10.00"), today)
    _add_expense(db, account, variables, Decimal("-5.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    order = [r.tag_id for r in result]

    parent_index = order.index(parent.tag_id)
    # Ordre exact (pas seulement l'ensemble) : les frères sont triés par tag_id
    # croissant, ordre de création ici puisque `fixes` a été créé avant `variables`.
    assert order[parent_index + 1 : parent_index + 3] == [fixes.tag_id, variables.tag_id]


def test_two_independent_root_groups_keep_stable_order(db):
    account = _add_account(db)
    alimentation = _add_tag(db, name="Alimentation", level=1)
    loisirs = _add_tag(db, name="Loisirs", level=1)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, alimentation, Decimal("-10.00"), today)
    _add_expense(db, account, loisirs, Decimal("-20.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    order = [r.tag_id for r in result]

    assert order.index(alimentation.tag_id) < order.index(loisirs.tag_id)


def test_child_with_target_but_parent_without_spend_or_target_is_its_own_root(db):
    account = _add_account(db)
    parent = _add_tag(db, name="Charges", level=1)
    child = _add_tag(db, name="Fixes", parent_id=parent.tag_id, level=2)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=child.tag_id, percentage=Decimal("20.00")),
        db,
    )

    result = get_tag_tracking(account.account_id, period_start, db)
    order = [r.tag_id for r in result]

    # Le parent n'a ni dépense (propre ou remontée) ni Cible propre : il est absent
    # de `included_tag_ids`, donc absent du résultat. L'enfant apparaît seul, comme
    # sa propre racine de groupe (même règle que `buildTargetBlocks` pour les Cibles).
    assert parent.tag_id not in order
    assert child.tag_id in order


def test_three_level_hierarchy_order_is_depth_first(db):
    account = _add_account(db)
    grandparent = _add_tag(db, name="Vie quotidienne", level=1)
    parent = _add_tag(db, name="Alimentation", parent_id=grandparent.tag_id, level=2)
    child = _add_tag(db, name="Restaurant", parent_id=parent.tag_id, level=3)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, grandparent, Decimal("-5.00"), today)
    _add_expense(db, account, parent, Decimal("-20.00"), today)
    _add_expense(db, account, child, Decimal("-10.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    order = [r.tag_id for r in result]

    assert order == [grandparent.tag_id, parent.tag_id, child.tag_id]


def test_past_period_has_no_projection_even_with_target(db):
    account = _add_account(db)
    tag = _add_tag(db)
    past_period_start = date(1999, 1, 1)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )
    _add_expense(db, account, tag, Decimal("-150.00"), date(1999, 1, 10))

    result = get_tag_tracking(account.account_id, past_period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("150.00")
    assert row.target_amount == Decimal("200.00")
    assert row.gap == Decimal("50.00")
    assert row.projection is None


def test_tag_with_target_and_zero_spend_is_visible(db):
    account = _add_account(db)
    tag = _add_tag(db)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=Decimal("1000.00")),
        db,
    )
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )

    result = get_tag_tracking(account.account_id, period_start, db)

    row = next(r for r in result if r.tag_id == tag.tag_id)
    assert row.spent == Decimal("0.00")
    assert row.target_amount == Decimal("200.00")
    assert row.projection == Decimal("0.00")


def test_transaction_tagged_with_both_ancestor_and_descendant_counts_once(db):
    account = _add_account(db)
    parent = _add_tag(db, name="Alimentation", level=1)
    child = _add_tag(db, name="Restaurant", parent_id=parent.tag_id, level=2)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense_multi_tag(db, account, [parent, child], Decimal("-40.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[parent.tag_id].spent == Decimal("40.00")
    assert by_id[child.tag_id].spent == Decimal("40.00")


def test_reimbursement_on_charges_child_tag_nets_against_spent(db):
    account = _add_account(db)
    charges = _add_tag(db, name="Charges", level=1)
    charges_fixes = _add_tag(db, name="Charges fixes", parent_id=charges.tag_id, level=2)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, charges_fixes, Decimal("-30.00"), today)
    _add_expense(db, account, charges_fixes, Decimal("20.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[charges_fixes.tag_id].spent == Decimal("10.00")
    assert by_id[charges.tag_id].spent == Decimal("10.00")


def test_reimbursement_on_any_tag_nets_against_spent(db):
    account = _add_account(db)
    loisirs = _add_tag(db, name="Loisirs", level=1)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, loisirs, Decimal("-20.00"), today)
    _add_expense(db, account, loisirs, Decimal("15.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[loisirs.tag_id].spent == Decimal("5.00")


def test_reimbursement_exceeding_charges_becomes_negative(db):
    account = _add_account(db)
    charges = _add_tag(db, name="Charges", level=1)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, charges, Decimal("-30.00"), today)
    _add_expense(db, account, charges, Decimal("50.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    # Aucun plancher, y compris pour "Charges" : un remboursement excédentaire
    # rend le total négatif.
    assert by_id[charges.tag_id].spent == Decimal("-20.00")


def test_reimbursement_tagged_on_two_tags_nets_both(db):
    account = _add_account(db)
    charges = _add_tag(db, name="Charges", level=1)
    loisirs = _add_tag(db, name="Loisirs", level=1)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, charges, Decimal("-30.00"), today)
    _add_expense(db, account, loisirs, Decimal("-30.00"), today)
    # Un même remboursement taggé à la fois sur Charges et sur Loisirs :
    # les deux totaux sont nettés indépendamment.
    _add_expense_multi_tag(db, account, [charges, loisirs], Decimal("20.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[charges.tag_id].spent == Decimal("10.00")
    assert by_id[loisirs.tag_id].spent == Decimal("10.00")


def test_retrait_partiel_investissements_nette_sans_plancher(db):
    account = _add_account(db)
    investissements = _add_tag(db, name="Investissements", level=1)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, investissements, Decimal("-400.00"), today)
    _add_expense(db, account, investissements, Decimal("100.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[investissements.tag_id].spent == Decimal("300.00")


def test_retrait_excedentaire_investissements_devient_negatif(db):
    account = _add_account(db)
    investissements = _add_tag(db, name="Investissements", level=1)
    today = date.today()
    period_start = _current_period_start(today)
    # Cible ajoutée pour garder le tag visible même si `spent` finit à 0€ ;
    # ici surtout pour rester cohérent avec le pattern des tests Charges.
    upsert_budget_target(
        BudgetTargetUpsert(
            account_id=account.account_id, tag_id=investissements.tag_id, percentage=Decimal("10.00")
        ),
        db,
    )

    _add_expense(db, account, investissements, Decimal("-400.00"), today)
    _add_expense(db, account, investissements, Decimal("500.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    # Contrairement à Charges, pas de plancher à 0€ : le retrait excédentaire
    # se traduit par un total négatif.
    assert by_id[investissements.tag_id].spent == Decimal("-100.00")


def test_remboursement_charges_et_retrait_investissements_sans_interference(db):
    account = _add_account(db)
    charges = _add_tag(db, name="Charges", level=1)
    investissements = _add_tag(db, name="Investissements", level=1)
    today = date.today()
    period_start = _current_period_start(today)
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=charges.tag_id, percentage=Decimal("10.00")),
        db,
    )

    _add_expense(db, account, charges, Decimal("-30.00"), today)
    _add_expense(db, account, charges, Decimal("50.00"), today)
    _add_expense(db, account, investissements, Decimal("-400.00"), today)
    _add_expense(db, account, investissements, Decimal("500.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    # Charges et Investissements nettés indépendamment, tous deux sans
    # plancher : les deux excédents deviennent négatifs sans s'interférer.
    assert by_id[charges.tag_id].spent == Decimal("-20.00")
    assert by_id[investissements.tag_id].spent == Decimal("-100.00")


def test_retrait_egal_au_versement_investissements_donne_zero_exact(db):
    account = _add_account(db)
    investissements = _add_tag(db, name="Investissements", level=1)
    today = date.today()
    period_start = _current_period_start(today)
    # Cible ajoutée pour garder le tag visible dans le résultat même à 0€ net
    # (sans Cible, un tag à `spent == 0` est exclu de `included_tag_ids`).
    upsert_budget_target(
        BudgetTargetUpsert(
            account_id=account.account_id, tag_id=investissements.tag_id, percentage=Decimal("10.00")
        ),
        db,
    )

    _add_expense(db, account, investissements, Decimal("-400.00"), today)
    _add_expense(db, account, investissements, Decimal("400.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    assert by_id[investissements.tag_id].spent == Decimal("0.00")


def test_retrait_sur_sous_tag_investissements_niveau_3_nette_sans_plancher(db):
    account = _add_account(db)
    investissements = _add_tag(db, name="Investissements", level=1)
    epargne = _add_tag(db, name="Épargne", parent_id=investissements.tag_id, level=2)
    livret_a = _add_tag(db, name="Livret A", parent_id=epargne.tag_id, level=3)
    today = date.today()
    period_start = _current_period_start(today)

    _add_expense(db, account, livret_a, Decimal("-400.00"), today)
    _add_expense(db, account, livret_a, Decimal("500.00"), today)

    result = get_tag_tracking(account.account_id, period_start, db)
    by_id = {r.tag_id: r for r in result}

    # Le netting sans plancher remonte correctement jusqu'à la racine
    # "Investissements" (niveau 1) en passant par le sous-tag intermédiaire
    # (niveau 2), à la profondeur maximale autorisée (MAX_LEVEL=3).
    assert by_id[livret_a.tag_id].spent == Decimal("-100.00")
    assert by_id[epargne.tag_id].spent == Decimal("-100.00")
    assert by_id[investissements.tag_id].spent == Decimal("-100.00")


def test_deleting_tag_referenced_by_target_raises_422(db):
    account = _add_account(db)
    tag = _add_tag(db)
    upsert_budget_target(
        BudgetTargetUpsert(account_id=account.account_id, tag_id=tag.tag_id, percentage=Decimal("20.00")),
        db,
    )

    with pytest.raises(HTTPException) as exc_info:
        delete_tag(tag.tag_id, db)

    assert exc_info.value.status_code == 422
    assert db.get(Tag, tag.tag_id) is not None


def test_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    with pytest.raises(HTTPException) as exc_info:
        get_tag_tracking(account.account_id, date.today(), db)
    assert exc_info.value.status_code == 422


def test_unknown_account_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        get_tag_tracking(999, date.today(), db)
    assert exc_info.value.status_code == 404
