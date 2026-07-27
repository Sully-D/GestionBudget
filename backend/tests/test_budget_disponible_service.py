from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.model import Account
from app.budget.schema import RevenueSalaireUpsert
from app.budget.service import get_disponible, upsert_salaire
from app.core.db import Base
from app.projections.model import PlannedExpense, RecurringMatch, RecurringTransaction
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag

PERIOD_START = date(2026, 3, 1)
PERIOD_END = date(2026, 3, 31)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_budget_disponible_service.db"
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


def _add_tag(db, name="Alimentation") -> Tag:
    tag = Tag(name=name, parent_id=None, level=1)
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


def _add_recurring(
    db, account, signature, amount=Decimal("-50.00"), periodicity="mensuelle", status="confirmed"
) -> RecurringTransaction:
    recurring = RecurringTransaction(
        account_id=account.account_id,
        tag_id=None,
        signature=signature,
        label=signature,
        amount=amount,
        periodicity=periodicity,
        status=status,
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def _add_match(db, recurring, transaction, status="pending") -> RecurringMatch:
    match = RecurringMatch(
        recurring_id=recurring.recurring_id, transaction_id=transaction.transaction_id, status=status
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def _add_planned_expense(
    db, account, tag, amount, expense_date, series_id=None, period_index=None, total_periods=None
) -> PlannedExpense:
    planned_expense = PlannedExpense(
        account_id=account.account_id,
        tag_id=tag.tag_id,
        series_id=series_id,
        period_index=period_index,
        total_periods=total_periods,
        amount=amount,
        date=expense_date,
        description="Dépense planifiée",
    )
    db.add(planned_expense)
    db.commit()
    db.refresh(planned_expense)
    return planned_expense


def _add_transaction_tagged(db, account, tx_date, amount, tag, label="Dépense") -> Transaction:
    tx = _add_transaction(db, account, tx_date, amount, label=label)
    db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=tag.tag_id))
    db.commit()
    return tx


def _current_period_start(today: date) -> date:
    return date(today.year, today.month, 1)


def _set_revenu(db, account, amount) -> None:
    upsert_salaire(
        RevenueSalaireUpsert(account_id=account.account_id, period_start=None, amount=amount), db
    )


def test_revenu_seul_disponible_egale_revenus(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.revenus == Decimal("1000.00")
    assert result.charges_recurrentes == Decimal("0.00")
    assert result.depenses_planifiees == Decimal("0.00")
    assert result.depenses_courantes == Decimal("0.00")
    assert result.disponible == Decimal("1000.00")


def test_depense_courante_seule_reduit_le_disponible(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 3, 10), Decimal("-42.00"))

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_courantes == Decimal("42.00")
    assert result.disponible == Decimal("958.00")


def test_recurrente_confirmee_due_sans_match_compte_montant_projete(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 2, 5), Decimal("-50.00"), label="Salle de sport")
    _add_recurring(db, account, signature="salle de sport", amount=Decimal("-50.00"))

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("50.00")
    assert result.disponible == Decimal("950.00")


def test_recurrente_avec_match_confirme_compte_montant_reel_sans_double_comptage(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 1, 5), Decimal("-50.00"), label="Loyer")
    recurring = _add_recurring(db, account, signature="loyer", amount=Decimal("-50.00"))
    realized_tx = _add_transaction(db, account, date(2026, 3, 5), Decimal("-52.00"), label="Loyer")
    _add_match(db, recurring, realized_tx, status="confirmed")

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("52.00")
    assert result.depenses_courantes == Decimal("0.00")


def test_recurrente_avec_match_pending_reste_en_depenses_courantes_sans_charge_projetee(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 1, 5), Decimal("-800.00"), label="Loyer")
    recurring = _add_recurring(db, account, signature="loyer", amount=Decimal("-800.00"))
    pending_tx = _add_transaction(db, account, date(2026, 3, 5), Decimal("-800.00"), label="Loyer")
    _add_match(db, recurring, pending_tx, status="pending")

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_courantes == Decimal("800.00")
    assert result.charges_recurrentes == Decimal("0.00")


def test_recurrente_avec_deux_matches_confirmes_meme_recurrente_ne_double_compte_pas(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 1, 5), Decimal("-50.00"), label="Loyer")
    recurring = _add_recurring(db, account, signature="loyer", amount=Decimal("-50.00"))
    tx1 = _add_transaction(db, account, date(2026, 3, 5), Decimal("-52.00"), label="Loyer")
    tx2 = _add_transaction(db, account, date(2026, 3, 20), Decimal("-53.00"), label="Loyer")
    _add_match(db, recurring, tx1, status="confirmed")
    _add_match(db, recurring, tx2, status="confirmed")

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("52.00")


def test_recurrente_avec_match_rejete_reste_due_et_transaction_reste_en_depenses_courantes(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 1, 5), Decimal("-800.00"), label="Loyer")
    recurring = _add_recurring(db, account, signature="loyer", amount=Decimal("-800.00"))
    rejected_tx = _add_transaction(db, account, date(2026, 3, 5), Decimal("-800.00"), label="Loyer")
    _add_match(db, recurring, rejected_tx, status="rejected")

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("800.00")
    assert result.depenses_courantes == Decimal("800.00")


def test_recurrente_confirmee_non_due_ne_contribue_pas(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 1, 5), Decimal("-300.00"), label="Assurance")
    _add_recurring(
        db, account, signature="assurance", amount=Decimal("-300.00"), periodicity="trimestrielle"
    )

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("0.00")
    assert result.disponible == Decimal("1000.00")


def test_recurrente_confirmee_sans_transaction_historique_est_ignoree(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_recurring(db, account, signature="salle de sport", amount=Decimal("-50.00"))

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("0.00")


def test_depenses_planifiees_simple_et_fraction_de_serie_dans_la_periode(db):
    account = _add_account(db)
    tag = _add_tag(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_planned_expense(db, account, tag, Decimal("-100.00"), date(2026, 3, 15))

    series_id = str(uuid4())
    _add_planned_expense(
        db, account, tag, Decimal("-30.00"), date(2026, 3, 1),
        series_id=series_id, period_index=1, total_periods=2,
    )
    _add_planned_expense(
        db, account, tag, Decimal("-30.00"), date(2026, 4, 1),
        series_id=series_id, period_index=2, total_periods=2,
    )

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_planifiees == Decimal("130.00")


def test_transaction_positive_hors_revenu_nest_ni_charge_ni_depense_courante(db):
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 3, 10), Decimal("75.00"), label="Remboursement")

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("0.00")
    assert result.depenses_courantes == Decimal("0.00")
    assert result.disponible == Decimal("1000.00")


def test_periode_passee_arbitraire_avec_composantes_non_nulles(db):
    account = _add_account(db)
    tag = _add_tag(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, date(2026, 3, 10), Decimal("-42.00"))
    _add_planned_expense(db, account, tag, Decimal("-15.00"), date(2026, 3, 20))

    result = get_disponible(account.account_id, date(2026, 3, 17), db)

    assert result.period_start == PERIOD_START
    assert result.period_end == PERIOD_END
    assert result.depenses_courantes == Decimal("42.00")
    assert result.depenses_planifiees == Decimal("15.00")
    assert result.disponible == Decimal("943.00")


def test_common_account_returns_422(db):
    account = _add_account(db, is_common=True, name="Commun")
    with pytest.raises(HTTPException) as exc_info:
        get_disponible(account.account_id, PERIOD_START, db)
    assert exc_info.value.status_code == 422


def test_unknown_account_returns_404(db):
    with pytest.raises(HTTPException) as exc_info:
        get_disponible(999, PERIOD_START, db)
    assert exc_info.value.status_code == 404


def test_virement_lui_elle_taggue_exclu_des_depenses_courantes(db):
    account = _add_account(db)
    virement_tag = _add_tag(db, name="Virement Lui/Elle")
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction_tagged(db, account, date(2026, 3, 10), Decimal("-600.00"), virement_tag)

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_courantes == Decimal("0.00")
    assert result.disponible == Decimal("1000.00")


def test_virement_lui_elle_taggue_exclu_des_charges_recurrentes(db):
    account = _add_account(db)
    virement_tag = _add_tag(db, name="Virement Lui/Elle")
    _set_revenu(db, account, Decimal("1000.00"))
    recurring = _add_recurring(db, account, signature="virement mensuel", amount=Decimal("-600.00"))
    tx = _add_transaction(db, account, date(2026, 3, 10), Decimal("-600.00"), label="Virement mensuel")
    db.add(TransactionTag(transaction_id=tx.transaction_id, tag_id=virement_tag.tag_id))
    db.commit()
    _add_match(db, recurring, tx, status="confirmed")

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.charges_recurrentes == Decimal("0.00")
    assert result.disponible == Decimal("1000.00")


def test_remboursement_partage_entre_deux_tags_deduit_une_seule_fois_du_total(db):
    # Un Tag n'est pas une partition (FR-13, tags multiples) : le remboursement de
    # 30€ est UNE seule Transaction, elle ne doit être déduite qu'une fois du total
    # global (100€ de dépenses - 30€ = 70€), même si elle est taguée sous deux Tags
    # racines distincts. La déduire par tag (20€ + 20€ = 40€) compterait à tort les
    # mêmes 30€ réels deux fois (spec-virements-internes-depenses-courantes, CAP-2).
    account = _add_account(db)
    sante = _add_tag(db, name="Santé")
    loisirs = _add_tag(db, name="Loisirs")
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction_tagged(db, account, date(2026, 3, 5), Decimal("-50.00"), sante)
    _add_transaction_tagged(db, account, date(2026, 3, 6), Decimal("-50.00"), loisirs)
    remboursement = _add_transaction(db, account, date(2026, 3, 7), Decimal("30.00"), label="Remboursement")
    db.add(TransactionTag(transaction_id=remboursement.transaction_id, tag_id=sante.tag_id))
    db.add(TransactionTag(transaction_id=remboursement.transaction_id, tag_id=loisirs.tag_id))
    db.commit()

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_courantes == Decimal("70.00")


def test_depense_unique_taguee_avec_deux_tags_racines_distincts_nest_comptee_quune_fois(db):
    # Bug confirmé par 2 reviewers indépendants (Blind Hunter + Edge Case Hunter,
    # itération 2) : une seule Transaction de -50€ taguée à la fois « Santé » et
    # « Loisirs » (FR-13, tags multiples) ne représente qu'une seule dépense réelle.
    account = _add_account(db)
    sante = _add_tag(db, name="Santé")
    loisirs = _add_tag(db, name="Loisirs")
    _set_revenu(db, account, Decimal("1000.00"))
    depense = _add_transaction(db, account, date(2026, 3, 5), Decimal("-50.00"), label="Dépense mixte")
    db.add(TransactionTag(transaction_id=depense.transaction_id, tag_id=sante.tag_id))
    db.add(TransactionTag(transaction_id=depense.transaction_id, tag_id=loisirs.tag_id))
    db.commit()

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_courantes == Decimal("50.00")
    assert result.disponible == Decimal("950.00")


def test_virement_lui_elle_equilibre_sur_periode_en_cours_ecart_nul(db):
    today = date.today()
    period_start = _current_period_start(today)
    lui = _add_account(db, name="Personnel-Lui")
    elle = _add_account(db, is_common=False, name="Personnel-Elle")
    virement_tag = _add_tag(db, name="Virement Lui/Elle")
    _set_revenu(db, lui, Decimal("1000.00"))
    _add_transaction_tagged(db, lui, today, Decimal("-600.00"), virement_tag)
    _add_transaction_tagged(db, elle, today, Decimal("600.00"), virement_tag)

    result = get_disponible(lui.account_id, period_start, db)

    assert result.virement_lui_elle_ecart == Decimal("0.00")
    assert result.depenses_courantes == Decimal("0.00")


def test_virement_lui_elle_desequilibre_sur_periode_en_cours_ecart_signale(db):
    today = date.today()
    period_start = _current_period_start(today)
    lui = _add_account(db, name="Personnel-Lui")
    _add_account(db, is_common=False, name="Personnel-Elle")
    virement_tag = _add_tag(db, name="Virement Lui/Elle")
    _set_revenu(db, lui, Decimal("1000.00"))
    _add_transaction_tagged(db, lui, today, Decimal("-600.00"), virement_tag)

    result = get_disponible(lui.account_id, period_start, db)

    assert result.virement_lui_elle_ecart == Decimal("-600.00")


def test_virement_lui_elle_sur_periode_passee_aucun_controle(db):
    account = _add_account(db)
    virement_tag = _add_tag(db, name="Virement Lui/Elle")
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction_tagged(db, account, date(2026, 3, 10), Decimal("-600.00"), virement_tag)

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.virement_lui_elle_ecart is None


def test_tag_virement_lui_elle_absent_ne_leve_pas_derreur(db):
    today = date.today()
    period_start = _current_period_start(today)
    account = _add_account(db)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction(db, account, today, Decimal("-42.00"))

    result = get_disponible(account.account_id, period_start, db)

    assert result.virement_lui_elle_ecart == Decimal("0.00")
    assert result.depenses_courantes == Decimal("42.00")


def test_depenses_courantes_reproductible_avec_hierarchie_de_tags(db):
    # Charges (racine) est plafond/rollup de Charges > Fixes (cf. FR-16/AD-9) : un
    # remboursement tagué directement sur le parent ne doit netter QUE le parent, la
    # dépense taguée sur l'enfant reste pleine dans son propre total. Seule la somme
    # des Tags RACINES doit être reproductible dans le total global Dépenses courantes
    # (spec-virements-internes-depenses-courantes, CAP-2).
    account = _add_account(db)
    charges = _add_tag(db, name="Charges")
    fixes = Tag(name="Charges > Fixes", parent_id=charges.tag_id, level=2)
    db.add(fixes)
    db.commit()
    db.refresh(fixes)
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction_tagged(db, account, date(2026, 3, 5), Decimal("-100.00"), fixes)
    remboursement = _add_transaction(db, account, date(2026, 3, 6), Decimal("40.00"), label="Remboursement")
    db.add(TransactionTag(transaction_id=remboursement.transaction_id, tag_id=charges.tag_id))
    db.commit()

    result = get_disponible(account.account_id, PERIOD_START, db)

    # Charges (racine, via rollup de Fixes) : 100 - 40 = 60€ ; Fixes (non racine,
    # déjà inclus dans Charges via rollup) n'est pas resommé séparément.
    assert result.depenses_courantes == Decimal("60.00")


def test_positif_taggue_virement_lui_elle_et_tag_de_depense_nest_pas_compte_en_remboursement(db):
    # Bug confirmé par 2 reviewers indépendants (Blind Hunter + Edge Case Hunter) :
    # une Transaction positive taguée à la fois « Virement Lui/Elle » et un Tag de
    # dépense doit rester totalement exclue (CAP-1, "quel que soit son signe"), pas
    # comptée comme remboursement du Tag de dépense qu'elle partage aussi.
    account = _add_account(db)
    virement_tag = _add_tag(db, name="Virement Lui/Elle")
    loisirs = _add_tag(db, name="Loisirs")
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction_tagged(db, account, date(2026, 3, 5), Decimal("-50.00"), loisirs)
    ambigu = _add_transaction(db, account, date(2026, 3, 6), Decimal("50.00"), label="Virement + Loisirs ?")
    db.add(TransactionTag(transaction_id=ambigu.transaction_id, tag_id=virement_tag.tag_id))
    db.add(TransactionTag(transaction_id=ambigu.transaction_id, tag_id=loisirs.tag_id))
    db.commit()

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_courantes == Decimal("50.00")


def test_positif_deja_rapproche_dune_recurrente_nest_pas_compte_en_remboursement(db):
    # Edge case signalé par l'Edge Case Hunter : une Transaction positive déjà liée à
    # un RecurringMatch confirmé (donc déjà comptée, le cas échéant, dans Charges
    # récurrentes) ne doit pas en plus netter une dépense courante du même Tag.
    account = _add_account(db)
    loisirs = _add_tag(db, name="Loisirs")
    _set_revenu(db, account, Decimal("1000.00"))
    _add_transaction_tagged(db, account, date(2026, 3, 5), Decimal("-50.00"), loisirs)
    recurring = _add_recurring(db, account, signature="rentrée récurrente", amount=Decimal("50.00"))
    matched = _add_transaction(db, account, date(2026, 3, 6), Decimal("50.00"), label="Rentrée")
    db.add(TransactionTag(transaction_id=matched.transaction_id, tag_id=loisirs.tag_id))
    db.commit()
    _add_match(db, recurring, matched, status="confirmed")

    result = get_disponible(account.account_id, PERIOD_START, db)

    assert result.depenses_courantes == Decimal("50.00")
