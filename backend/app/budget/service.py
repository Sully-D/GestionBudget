from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.accounts.model import Account
from app.accounts.service import compute_period
from app.budget.model import BudgetTarget, Revenue
from app.budget.schema import (
    BudgetTargetUpsert,
    CoupleChargesPercentageUpdate,
    DisponibleRead,
    RecapCoupleAccountRow,
    RecapCoupleRead,
    RepartitionCommuneAccountPart,
    RepartitionCommuneRead,
    RevenueOneOffCreate,
    RevenuePeriodSummary,
    RevenueRead,
    RevenueSalaireUpsert,
    TagSpendingRead,
    TagTrackingRead,
)
from app.core.period import add_months, period_for
from app.projections.model import PlannedExpense, RecurringMatch, RecurringTransaction
from app.tags.model import Tag
from app.transactions.model import Transaction, TransactionTag

RECURRING_PERIODICITY_MONTHS: dict[str, int] = {
    "mensuelle": 1,
    "trimestrielle": 3,
    "annuelle": 12,
}


def _get_account_or_404(account_id: int, db: Session) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Compte {account_id} introuvable")
    return account


def _get_personal_account_or_404(account_id: int, db: Session) -> Account:
    account = _get_account_or_404(account_id, db)
    if account.is_common:
        raise HTTPException(
            status_code=422, detail="Le Compte Commun n'a pas de revenus propres"
        )
    return account


def _get_tag_or_404(tag_id: int, db: Session) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} introuvable")
    return tag


def upsert_salaire(payload: RevenueSalaireUpsert, db: Session) -> Revenue:
    _get_personal_account_or_404(payload.account_id, db)
    existing = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == payload.account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == payload.period_start,
        )
        .first()
    )
    if existing is not None:
        existing.amount = payload.amount
    else:
        existing = Revenue(
            account_id=payload.account_id,
            period_start=payload.period_start,
            kind="salaire",
            amount=payload.amount,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_effective_salary_for_period(account_id: int, period_start: date, db: Session) -> Decimal:
    _get_personal_account_or_404(account_id, db)
    correction = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == period_start,
        )
        .first()
    )
    if correction is not None:
        return correction.amount
    reference = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start.is_(None),
        )
        .first()
    )
    return reference.amount if reference is not None else Decimal("0.00")


def delete_salaire_correction(account_id: int, period_start: date, db: Session) -> None:
    _get_personal_account_or_404(account_id, db)
    correction = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == period_start,
        )
        .first()
    )
    if correction is None:
        raise HTTPException(
            status_code=404, detail="Aucune correction de salaire pour cette Période"
        )
    db.delete(correction)
    db.commit()


def add_one_off(payload: RevenueOneOffCreate, db: Session) -> Revenue:
    _get_personal_account_or_404(payload.account_id, db)
    revenue = Revenue(
        account_id=payload.account_id,
        period_start=payload.period_start,
        kind="ponctuel",
        amount=payload.amount,
        description=payload.description,
    )
    db.add(revenue)
    db.commit()
    db.refresh(revenue)
    return revenue


def delete_one_off(revenue_id: int, db: Session) -> None:
    revenue = db.get(Revenue, revenue_id)
    if revenue is None or revenue.kind != "ponctuel":
        raise HTTPException(status_code=404, detail=f"Rentrée ponctuelle {revenue_id} introuvable")
    db.delete(revenue)
    db.commit()


def get_period_summary(account_id: int, period_start: date, db: Session) -> RevenuePeriodSummary:
    _get_personal_account_or_404(account_id, db)

    reference = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start.is_(None),
        )
        .first()
    )
    correction = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "salaire",
            Revenue.period_start == period_start,
        )
        .first()
    )
    one_offs = (
        db.query(Revenue)
        .filter(
            Revenue.account_id == account_id,
            Revenue.kind == "ponctuel",
            Revenue.period_start == period_start,
        )
        .order_by(Revenue.revenue_id)
        .all()
    )

    reference_amount = reference.amount if reference is not None else None
    effective_salary = get_effective_salary_for_period(account_id, period_start, db)
    total = effective_salary + sum((r.amount for r in one_offs), Decimal("0.00"))

    return RevenuePeriodSummary(
        account_id=account_id,
        period_start=period_start,
        reference_amount=reference_amount,
        effective_salary=effective_salary,
        has_correction=correction is not None,
        one_off=[RevenueRead.model_validate(r) for r in one_offs],
        total=total,
    )


def upsert_budget_target(payload: BudgetTargetUpsert, db: Session) -> BudgetTarget:
    _get_personal_account_or_404(payload.account_id, db)
    _get_tag_or_404(payload.tag_id, db)
    existing = (
        db.query(BudgetTarget)
        .filter(
            BudgetTarget.account_id == payload.account_id,
            BudgetTarget.tag_id == payload.tag_id,
        )
        .first()
    )
    if existing is not None:
        existing.percentage = payload.percentage
    else:
        existing = BudgetTarget(
            account_id=payload.account_id,
            tag_id=payload.tag_id,
            percentage=payload.percentage,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_budget_targets(account_id: int, db: Session) -> list[BudgetTarget]:
    _get_personal_account_or_404(account_id, db)
    return (
        db.query(BudgetTarget)
        .filter(BudgetTarget.account_id == account_id)
        .order_by(BudgetTarget.target_id)
        .all()
    )


def delete_budget_target(target_id: int, db: Session) -> None:
    target = db.get(BudgetTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Cible {target_id} introuvable")
    db.delete(target)
    db.commit()


def _amount_by_tag_for_period(
    account_id: int, period_start: date, period_end: date, db: Session, *, positive: bool
) -> tuple[dict[int, Decimal], dict[int, Tag]]:
    # Logique commune à `_spent_by_tag_for_period` (dépenses, `positive=False`) et
    # `_revenus_by_exact_tag_for_calendar_months` (revenus, `positive=True`) : seule la
    # clause de signe diffère entre les deux usages. Remonte chaque transaction vers
    # tous ses ancêtres/elle-même pour la déduplication (cf. commentaire ci-dessous).
    amount_filter = Transaction.amount > 0 if positive else Transaction.amount < 0
    rows = (
        db.query(TransactionTag.transaction_id, TransactionTag.tag_id, Transaction.amount)
        .join(Transaction, Transaction.transaction_id == TransactionTag.transaction_id)
        .filter(
            Transaction.account_id == account_id,
            Transaction.date >= period_start,
            Transaction.date <= period_end,
            amount_filter,
        )
        .all()
    )
    txn_tag_ids: dict[int, set[int]] = {}
    txn_amount: dict[int, Decimal] = {}
    for transaction_id, tag_id, amount in rows:
        txn_tag_ids.setdefault(transaction_id, set()).add(tag_id)
        txn_amount[transaction_id] = amount if positive else abs(amount)

    tags = db.query(Tag).all()
    tag_by_id = {tag.tag_id: tag for tag in tags}

    # Auto-tagué ou remonté par un enfant, une même transaction ne doit compter
    # qu'une fois par ancêtre (évite le double comptage si elle porte à la fois
    # un tag et l'un de ses ancêtres/descendants).
    ancestors_or_self: dict[int, list[int]] = {}
    for tag in tags:
        chain = []
        current: Tag | None = tag
        while current is not None:
            chain.append(current.tag_id)
            current = tag_by_id.get(current.parent_id) if current.parent_id is not None else None
        ancestors_or_self[tag.tag_id] = chain

    total: dict[int, Decimal] = {tag.tag_id: Decimal("0.00") for tag in tags}
    for transaction_id, tag_ids in txn_tag_ids.items():
        amount = txn_amount[transaction_id]
        affected_tag_ids: set[int] = set()
        for tag_id in tag_ids:
            affected_tag_ids.update(ancestors_or_self.get(tag_id, ()))
        for tag_id in affected_tag_ids:
            if tag_id in total:
                total[tag_id] += amount

    return total, tag_by_id


def _spent_by_tag_for_period(
    account_id: int, period_start: date, period_end: date, db: Session
) -> tuple[dict[int, Decimal], dict[int, Tag]]:
    # Toute transaction à montant positif taguée X (remboursement, retrait...)
    # vient en déduction du total du tag X et de ses ancêtres (rollup déjà
    # appliqué par `_amount_by_tag_for_period`), quel que soit X -- aucune
    # restriction à un arbre de tags particulier ("Charges"/"Investissements"
    # n'ont plus de traitement spécifique). Aucun plancher : le net peut
    # devenir négatif si les montants positifs dépassent les dépenses, pour
    # n'importe quel tag.
    gross, tag_by_id = _amount_by_tag_for_period(
        account_id, period_start, period_end, db, positive=False
    )
    reimbursed, _ = _amount_by_tag_for_period(
        account_id, period_start, period_end, db, positive=True
    )
    net = {
        tag_id: amount - reimbursed.get(tag_id, Decimal("0.00"))
        for tag_id, amount in gross.items()
    }
    return net, tag_by_id


def _hierarchical_tag_order(tag_ids: set[int], tag_by_id: dict[int, Tag]) -> list[int]:
    # Même algorithme que `buildTargetBlocks` (frontend/src/pages/Budget.tsx) pour les
    # Cibles : un tag est une racine de groupe si son parent n'est pas lui-même inclus
    # dans `tag_ids` (parent absent de la Répartition, ou pas de parent du tout). Chaque
    # groupe de frères est trié par tag_id croissant (ordre de création, ordre stable
    # inchangé) puis parcouru en profondeur pour qu'un parent soit toujours immédiatement
    # suivi de tous ses descendants.
    # Précondition non vérifiée à l'exécution (jamais violée par les deux appelants
    # actuels, `get_tag_tracking`/`get_tag_spending`, qui construisent toujours `tag_ids`
    # comme un sous-ensemble des clés de `tag_by_id`) : `tag_ids ⊆ tag_by_id.keys()`.
    # La récursion de `visit()` n'a pas de garde de profondeur propre — sa terminaison
    # s'appuie sur `MAX_LEVEL=3` (`app/tags/model.py`, contrainte DB `ck_tags_level_range`),
    # qui borne la hauteur de toute chaîne de parenté à 3.
    children_by_group_parent: dict[int | None, list[int]] = {}
    for tag_id in tag_ids:
        parent_id = tag_by_id[tag_id].parent_id
        group_parent = parent_id if parent_id in tag_ids else None
        children_by_group_parent.setdefault(group_parent, []).append(tag_id)
    for siblings in children_by_group_parent.values():
        siblings.sort()

    ordered: list[int] = []

    def visit(tag_id: int) -> None:
        ordered.append(tag_id)
        for child_id in children_by_group_parent.get(tag_id, []):
            visit(child_id)

    for root_id in children_by_group_parent.get(None, []):
        visit(root_id)

    return ordered


def get_tag_tracking(account_id: int, period_start: date, db: Session) -> list[TagTrackingRead]:
    account = _get_personal_account_or_404(account_id, db)
    today = date.today()
    period_start, period_end = period_for(account.start_day, period_start)
    is_current_period = period_start == compute_period(account, today)[0]

    total_spent, tag_by_id = _spent_by_tag_for_period(account_id, period_start, period_end, db)

    targets = db.query(BudgetTarget).filter(BudgetTarget.account_id == account_id).all()
    target_by_tag = {
        target.tag_id: target for target in targets if target.tag_id in tag_by_id
    }

    total_revenue = get_period_summary(account_id, period_start, db).total
    jours_totaux = (period_end - period_start).days + 1
    jours_ecoules = (today - period_start).days + 1

    included_tag_ids = {
        tag_id for tag_id, spent in total_spent.items() if spent != 0
    } | set(target_by_tag.keys())

    result: list[TagTrackingRead] = []
    for tag_id in _hierarchical_tag_order(included_tag_ids, tag_by_id):
        tag = tag_by_id[tag_id]
        spent = total_spent.get(tag_id, Decimal("0.00"))
        target = target_by_tag.get(tag_id)

        target_percentage: Decimal | None = None
        target_amount: Decimal | None = None
        gap: Decimal | None = None
        projection: Decimal | None = None

        if target is not None:
            target_percentage = target.percentage
            target_amount = (target.percentage / Decimal(100) * total_revenue).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            gap = target_amount - spent
            projection = (
                ((spent / jours_ecoules) * jours_totaux).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if is_current_period
                else None
            )

        result.append(
            TagTrackingRead(
                tag_id=tag.tag_id,
                tag_name=tag.name,
                parent_id=tag.parent_id,
                level=tag.level,
                spent=spent,
                target_percentage=target_percentage,
                target_amount=target_amount,
                gap=gap,
                projection=projection,
            )
        )

    return result


def get_tag_spending(account_id: int, period_start: date, db: Session) -> list[TagSpendingRead]:
    account = _get_account_or_404(account_id, db)

    period_start, period_end = period_for(account.start_day, period_start)
    total_spent, tag_by_id = _spent_by_tag_for_period(account_id, period_start, period_end, db)

    included_tag_ids = {tag_id for tag_id, spent in total_spent.items() if spent != 0}

    result: list[TagSpendingRead] = []
    for tag_id in _hierarchical_tag_order(included_tag_ids, tag_by_id):
        tag = tag_by_id[tag_id]
        result.append(
            TagSpendingRead(
                tag_id=tag.tag_id,
                tag_name=tag.name,
                parent_id=tag.parent_id,
                level=tag.level,
                spent=total_spent[tag_id],
            )
        )

    return result


def _signature_for_transaction(transaction: Transaction) -> str:
    return (
        transaction.payee.strip().lower()
        if transaction.payee and transaction.payee.strip()
        else transaction.label.strip().lower()
    )


def _advance_recurring_date(current: date, periodicity: str) -> date:
    if periodicity == "hebdomadaire":
        return current + timedelta(days=7)
    return add_months(current, RECURRING_PERIODICITY_MONTHS[periodicity])


def _recurring_anchor_dates_by_signature(account_id: int, db: Session) -> dict[str, date]:
    # Un seul scan des Transactions + un seul scan des Rapprochements exclus pour
    # calculer l'ancre de toutes les signatures d'un coup, au lieu d'un scan complet
    # par Récurrente confirmée (N+1, cf. spec-recurring-anchor-n-plus-one.md). Une
    # Transaction `pending` n'est pas encore décidée par l'utilisateur, une Transaction
    # `rejected` a été explicitement écartée comme n'étant pas cette Récurrente : ni
    # l'une ni l'autre ne doit servir d'ancre (cf. projections/service.py).
    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id, Transaction.amount < 0)
        .all()
    )
    excluded_transaction_ids = {
        row.transaction_id
        for row in db.query(RecurringMatch.transaction_id)
        .filter(RecurringMatch.status.in_(["pending", "rejected"]))
        .all()
    }
    anchors: dict[str, date] = {}
    for transaction in transactions:
        if transaction.transaction_id in excluded_transaction_ids:
            continue
        signature = _signature_for_transaction(transaction)
        if signature not in anchors or transaction.date > anchors[signature]:
            anchors[signature] = transaction.date
    return anchors


def _is_recurring_due_in_period(
    anchor: date, periodicity: str, period_start: date, period_end: date
) -> bool:
    current = _advance_recurring_date(anchor, periodicity)
    while current < period_start:
        current = _advance_recurring_date(current, periodicity)
    return current <= period_end


def _charges_recurrentes_for_period(
    account_id: int, period_start: date, period_end: date, db: Session
) -> Decimal:
    confirmed_recurring = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringTransaction.status == "confirmed",
        )
        .all()
    )
    if not confirmed_recurring:
        return Decimal("0.00")

    total = Decimal("0.00")
    realized_ids: set[int] = set()
    realized_rows = (
        db.query(RecurringMatch.recurring_id, Transaction.amount)
        .join(Transaction, Transaction.transaction_id == RecurringMatch.transaction_id)
        .join(
            RecurringTransaction,
            RecurringTransaction.recurring_id == RecurringMatch.recurring_id,
        )
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringTransaction.status == "confirmed",
            RecurringMatch.status == "confirmed",
            Transaction.date >= period_start,
            Transaction.date <= period_end,
        )
        .order_by(RecurringMatch.match_id)
        .all()
    )
    # Une Récurrente compte au plus une fois par Période (cf. Dev Notes Story 5.4,
    # §Une Récurrente compte au plus une fois par Période) : si plusieurs Transactions
    # distinctes sont confirmées contre la même Récurrente dans la Période, ne compter
    # que la première pour éviter un double comptage du même montant récurrent.
    for recurring_id, amount in realized_rows:
        if recurring_id in realized_ids:
            continue
        total += abs(amount)
        realized_ids.add(recurring_id)

    # Une Récurrente déjà liée à une Transaction de la Période (même via un
    # Rapprochement `pending`, pas encore confirmé) ne doit pas recevoir de
    # charge projetée en plus : la Transaction reste comptée dans les Dépenses
    # courantes tant que non confirmée, ajouter la charge projetée compterait
    # la même dépense deux fois.
    matched_ids_in_period = {
        row.recurring_id
        for row in db.query(RecurringMatch.recurring_id)
        .join(Transaction, Transaction.transaction_id == RecurringMatch.transaction_id)
        .join(
            RecurringTransaction,
            RecurringTransaction.recurring_id == RecurringMatch.recurring_id,
        )
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringTransaction.status == "confirmed",
            RecurringMatch.status.in_(["pending", "confirmed"]),
            Transaction.date >= period_start,
            Transaction.date <= period_end,
        )
        .all()
    }

    anchors = _recurring_anchor_dates_by_signature(account_id, db)
    for recurring in confirmed_recurring:
        if recurring.recurring_id in matched_ids_in_period:
            continue
        anchor = anchors.get(recurring.signature)
        if anchor is None:
            continue
        if _is_recurring_due_in_period(anchor, recurring.periodicity, period_start, period_end):
            total += abs(recurring.amount)

    return total


def _depenses_courantes_for_period(
    account_id: int, period_start: date, period_end: date, db: Session
) -> Decimal:
    matched_transaction_ids = {
        row.transaction_id
        for row in db.query(RecurringMatch.transaction_id)
        .join(
            RecurringTransaction,
            RecurringTransaction.recurring_id == RecurringMatch.recurring_id,
        )
        .filter(
            RecurringTransaction.account_id == account_id,
            RecurringMatch.status == "confirmed",
        )
        .all()
    }

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.account_id == account_id,
            Transaction.date >= period_start,
            Transaction.date <= period_end,
            Transaction.amount < 0,
        )
        .all()
    )
    return sum(
        (abs(t.amount) for t in transactions if t.transaction_id not in matched_transaction_ids),
        Decimal("0.00"),
    )


def _depenses_planifiees_for_period(
    account_id: int, period_start: date, period_end: date, db: Session
) -> Decimal:
    total = (
        db.query(func.sum(PlannedExpense.amount))
        .filter(
            PlannedExpense.account_id == account_id,
            PlannedExpense.date >= period_start,
            PlannedExpense.date <= period_end,
        )
        .scalar()
        or Decimal("0.00")
    )
    return abs(total)


def get_disponible(account_id: int, period_start: date, db: Session) -> DisponibleRead:
    account = _get_personal_account_or_404(account_id, db)
    period_start, period_end = period_for(account.start_day, period_start)

    revenus = get_period_summary(account_id, period_start, db).total
    charges_recurrentes = _charges_recurrentes_for_period(account_id, period_start, period_end, db)
    depenses_planifiees = _depenses_planifiees_for_period(account_id, period_start, period_end, db)
    depenses_courantes = _depenses_courantes_for_period(account_id, period_start, period_end, db)
    disponible = revenus - charges_recurrentes - depenses_planifiees - depenses_courantes

    return DisponibleRead(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        revenus=revenus,
        charges_recurrentes=charges_recurrentes,
        depenses_planifiees=depenses_planifiees,
        depenses_courantes=depenses_courantes,
        disponible=disponible,
    )


def get_repartition_commune(
    montant_total: Decimal, tag_id: int, period_start: date, db: Session
) -> RepartitionCommuneRead:
    tag = _get_tag_or_404(tag_id, db)

    personal_accounts = (
        db.query(Account)
        .filter(Account.is_common.is_(False))
        .order_by(Account.account_id)
        .all()
    )

    parts: list[RepartitionCommuneAccountPart] = []
    for account in personal_accounts:
        account_period_start, account_period_end = period_for(account.start_day, period_start)
        revenus = get_period_summary(account.account_id, account_period_start, db).total
        total_spent, _ = _spent_by_tag_for_period(
            account.account_id, account_period_start, account_period_end, db
        )
        charges = total_spent.get(tag_id, Decimal("0.00"))
        reste_a_vivre = revenus - charges
        parts.append(
            RepartitionCommuneAccountPart(
                account_id=account.account_id,
                account_name=account.name,
                period_start=account_period_start,
                period_end=account_period_end,
                revenus=revenus,
                charges=charges,
                reste_a_vivre=reste_a_vivre,
                part=Decimal("0.00"),
            )
        )

    if not parts:
        raise HTTPException(
            status_code=422,
            detail="Aucun Compte Personnel : la répartition ne peut pas être calculée.",
        )
    for p in parts:
        if p.reste_a_vivre <= 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Le Reste à vivre de {p.account_name} est négatif ou nul "
                    f"({p.reste_a_vivre} €) : la répartition ne peut pas être calculée."
                ),
            )

    total_rav = sum((p.reste_a_vivre for p in parts), Decimal("0.00"))
    for p in parts:
        p.part = (montant_total * p.reste_a_vivre / total_rav).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    return RepartitionCommuneRead(
        tag_id=tag.tag_id,
        tag_name=tag.name,
        montant_total=montant_total,
        parts=parts,
    )


def _month_start_before(reference_month_start: date, count: int) -> date:
    # `add_months` (core/period.py) n'avance que vers l'avant : `range(months)` avec un
    # argument négatif est une boucle vide, donc `add_months(x, -1)` renvoie `x`
    # inchangé plutôt que le mois précédent. Arithmétique calendaire directe pour la
    # seule direction manquante ; `add_months` reste utilisé pour toutes les
    # opérations vers l'avant (bornes de fin de mois, énumération de la fenêtre).
    year = reference_month_start.year
    month = reference_month_start.month - count
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


def _assert_tags_mutually_exclusive(tags: list[Tag], db: Session) -> None:
    # Les 4 Tags exacts du Récap Budget Couple (Revenus/Charges/Virements compte
    # commun/Investissements) doivent être mutuellement exclusifs : si l'un est
    # ancêtre d'un autre, `_spent_by_tag_for_period`/
    # `_revenus_by_exact_tag_for_calendar_months` remontent une même transaction vers
    # TOUS ses ancêtres inclus dans l'ensemble de Tags considéré — un montant serait
    # alors compté deux fois (ex. dans Charges ET dans Virements). `Tag.level` va de 1
    # à `MAX_LEVEL=3` (contrainte DB `ck_tags_level_range`), donc toute chaîne
    # d'ancêtres est bornée.
    tag_by_id = {tag.tag_id: tag for tag in db.query(Tag).all()}

    def ancestor_ids(tag: Tag) -> set[int]:
        chain: set[int] = set()
        current = tag_by_id.get(tag.parent_id) if tag.parent_id is not None else None
        while current is not None:
            chain.add(current.tag_id)
            current = tag_by_id.get(current.parent_id) if current.parent_id is not None else None
        return chain

    ancestors_by_tag_id = {tag.tag_id: ancestor_ids(tag) for tag in tags}

    for i, tag_a in enumerate(tags):
        for tag_b in tags[i + 1 :]:
            if tag_b.tag_id in ancestors_by_tag_id[tag_a.tag_id]:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Le Tag « {tag_a.name} » est un descendant du Tag « {tag_b.name} » : "
                        "ambigu pour le Récap Budget Couple, ces 4 Tags doivent être "
                        "mutuellement exclusifs."
                    ),
                )
            if tag_a.tag_id in ancestors_by_tag_id[tag_b.tag_id]:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Le Tag « {tag_b.name} » est un descendant du Tag « {tag_a.name} » : "
                        "ambigu pour le Récap Budget Couple, ces 4 Tags doivent être "
                        "mutuellement exclusifs."
                    ),
                )


def _get_tag_by_exact_name(name: str, db: Session) -> Tag:
    matches = db.query(Tag).filter(Tag.name == name).all()
    if not matches:
        raise HTTPException(
            status_code=422,
            detail=f"Le Tag « {name} » est introuvable : requis pour le Récap Budget Couple.",
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Plusieurs Tags nommés « {name} » existent : ambigu, impossible de "
                "calculer le Récap Budget Couple."
            ),
        )
    return matches[0]


def _revenus_by_exact_tag_for_calendar_months(
    account_id: int, period_start: date, period_end: date, db: Session
) -> tuple[dict[int, Decimal], dict[int, Tag]]:
    # Miroir positif de `_spent_by_tag_for_period` (montants > 0, pas de abs() nécessaire
    # puisque déjà positifs) — même logique de remontée « Tag + descendants » et même
    # déduplication par transaction (une transaction ne compte qu'une fois par ancêtre),
    # factorisée dans `_amount_by_tag_for_period`.
    return _amount_by_tag_for_period(account_id, period_start, period_end, db, positive=True)


def get_recap_couple(account_id: int, months: int, db: Session) -> RecapCoupleRead:
    account = _get_account_or_404(account_id, db)
    if not account.is_common:
        raise HTTPException(
            status_code=422,
            detail="Le Récap Budget Couple n'est disponible que pour le Compte Commun.",
        )
    if months < 1:
        raise HTTPException(status_code=422, detail="Le nombre de mois doit être un entier >= 1.")
    if months > 120:
        raise HTTPException(
            status_code=422, detail="Le nombre de mois doit être un entier <= 120."
        )

    revenus_tag = _get_tag_by_exact_name("Revenus", db)
    charges_tag = _get_tag_by_exact_name("Charges", db)
    virements_tag = _get_tag_by_exact_name("Virements compte commun", db)
    investissements_tag = _get_tag_by_exact_name("Investissements", db)
    _assert_tags_mutually_exclusive(
        [revenus_tag, charges_tag, virements_tag, investissements_tag], db
    )

    # Fenêtre de N mois calendaires stricts, se terminant au mois calendaire précédent
    # le mois en cours — indépendante de la Période budgétaire (`start_day`) de tout
    # Compte (cf. Design Notes, jamais `period_for`/`start_day`). Les mois étant
    # contigus, sommer sur l'intervalle continu [period_start, period_end] équivaut à
    # sommer mois par mois puis diviser par N : un mois sans transaction contribue
    # naturellement 0 à la somme totale (division toujours par N, inchangée).
    today = date.today()
    current_month_start = today.replace(day=1)
    last_included_month_start = _month_start_before(current_month_start, 1)
    first_included_month_start = _month_start_before(last_included_month_start, months - 1)
    period_start = first_included_month_start
    next_month_after_last = add_months(last_included_month_start, 1)
    period_end = next_month_after_last - timedelta(days=1)

    personal_accounts = (
        db.query(Account)
        .filter(Account.is_common.is_(False))
        .order_by(Account.account_id)
        .all()
    )

    rows: list[RecapCoupleAccountRow] = []
    for personal_account in personal_accounts:
        spent, _ = _spent_by_tag_for_period(
            personal_account.account_id, period_start, period_end, db
        )
        revenu, _ = _revenus_by_exact_tag_for_calendar_months(
            personal_account.account_id, period_start, period_end, db
        )

        months_decimal = Decimal(months)
        revenus_avg = (revenu.get(revenus_tag.tag_id, Decimal("0.00")) / months_decimal).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        charges_avg = (spent.get(charges_tag.tag_id, Decimal("0.00")) / months_decimal).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        virements_avg = (spent.get(virements_tag.tag_id, Decimal("0.00")) / months_decimal).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        investissements_avg = (
            spent.get(investissements_tag.tag_id, Decimal("0.00")) / months_decimal
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        rows.append(
            RecapCoupleAccountRow(
                account_id=personal_account.account_id,
                account_name=personal_account.name,
                revenus=revenus_avg,
                charges=charges_avg,
                virements=virements_avg,
                investissements=investissements_avg,
                charges_plus_virements=charges_avg + virements_avg,
                reste_a_vivre=revenus_avg - charges_avg - virements_avg - investissements_avg,
            )
        )

    total_revenus = sum((r.revenus for r in rows), Decimal("0.00"))
    total_charges = sum((r.charges for r in rows), Decimal("0.00"))
    total_virements = sum((r.virements for r in rows), Decimal("0.00"))
    total_investissements = sum((r.investissements for r in rows), Decimal("0.00"))
    total_charges_plus_virements = sum((r.charges_plus_virements for r in rows), Decimal("0.00"))
    total_reste_a_vivre = sum((r.reste_a_vivre for r in rows), Decimal("0.00"))

    # Virement Lui/Elle par Compte Personnel vers le Commun (calcul dérivé, non bloquant :
    # cf. spec-virement-lui-elle-budget-couple.md). Échecs "soft" -> `virement_error` renseigné,
    # jamais de HTTPException : Tableaux 1/2 doivent continuer de s'afficher normalement.
    virement_error: str | None = None
    if account.reference_balance is None:
        virement_error = (
            "Virement non calculable : le solde de référence du Compte Commun n'est pas défini."
        )
    elif total_revenus == 0:
        virement_error = (
            "Virement non calculable : aucun revenu constaté sur la fenêtre sélectionnée."
        )
    else:
        besoin_total = total_charges + account.reference_balance
        computed_virements: list[Decimal] = []
        for row in rows:
            part_theorique = (row.revenus / total_revenus) * besoin_total
            virement_montant = (part_theorique - row.charges).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            computed_virements.append(virement_montant)

        negative_accounts = [
            row.account_name for row, v in zip(rows, computed_virements) if v < 0
        ]
        if negative_accounts:
            noms = ", ".join(negative_accounts)
            virement_error = (
                f"Virement non calculable : {noms} a/ont déjà payé plus que sa/leur part "
                "théorique."
            )
        else:
            for row, virement_montant in zip(rows, computed_virements):
                row.virement = virement_montant

    percentage = account.couple_charges_percentage
    budget_charges_convenu = (
        (percentage / Decimal(100) * total_revenus).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if percentage is not None
        else None
    )
    reste_disponible = (
        total_revenus - budget_charges_convenu if budget_charges_convenu is not None else None
    )

    return RecapCoupleRead(
        account_id=account.account_id,
        months=months,
        period_start=period_start,
        period_end=period_end,
        rows=rows,
        total_revenus=total_revenus,
        total_charges=total_charges,
        total_virements=total_virements,
        total_investissements=total_investissements,
        total_charges_plus_virements=total_charges_plus_virements,
        total_reste_a_vivre=total_reste_a_vivre,
        couple_charges_percentage=percentage,
        budget_charges_convenu=budget_charges_convenu,
        reste_disponible=reste_disponible,
        virement_error=virement_error,
    )


def update_couple_charges_percentage(payload: CoupleChargesPercentageUpdate, db: Session) -> Account:
    account = _get_account_or_404(payload.account_id, db)
    if not account.is_common:
        raise HTTPException(
            status_code=422,
            detail="Le NB% de charges convenu n'est modifiable que pour le Compte Commun.",
        )
    account.couple_charges_percentage = payload.percentage
    db.commit()
    db.refresh(account)
    return account
