import { useEffect, useMemo, useState } from 'react'
import {
  createPlannedExpense,
  createPlannedExpenseSplit,
  deletePlannedExpense,
  getPlannedExpenses,
  getProjection,
  updatePlannedExpense,
} from '../api/projections'
import type { PlannedExpense, ProjectionItem } from '../api/projections'
import { getTags } from '../api/tags'
import type { Tag } from '../api/tags'
import { useSelectableAccounts } from '../hooks/useSelectableAccounts'
import { existingTagId, formatDate, formatMontant, tagBreadcrumb } from '../lib/format'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink focus:border-accent focus:outline-none'

const horizons = [1, 3, 6] as const
type Horizon = (typeof horizons)[number]

const typeLabels: Record<ProjectionItem['type'], string> = {
  recurrente: 'Récurrente',
  planifiee: 'Planifiée',
}

function Projection() {
  const { accounts, accountsLoaded, accountsError, selectedAccountId, setSelectedAccountId } =
    useSelectableAccounts()

  const [tags, setTags] = useState<Tag[]>([])
  const tagById = useMemo(() => new Map(tags.map((t) => [t.tag_id, t])), [tags])

  const [plannedExpenses, setPlannedExpenses] = useState<PlannedExpense[]>([])
  const [plannedExpensesLoading, setPlannedExpensesLoading] = useState(false)
  const [plannedExpensesError, setPlannedExpensesError] = useState<string | null>(null)

  const [isAddingSimple, setIsAddingSimple] = useState(false)
  const [simpleDate, setSimpleDate] = useState('')
  const [simpleAmount, setSimpleAmount] = useState('')
  const [simpleTagId, setSimpleTagId] = useState('')
  const [simpleDescription, setSimpleDescription] = useState('')
  const [simpleError, setSimpleError] = useState<string | null>(null)
  const [simpleSubmitting, setSimpleSubmitting] = useState(false)

  const [isAddingSplit, setIsAddingSplit] = useState(false)
  const [splitStartDate, setSplitStartDate] = useState('')
  const [splitTotalAmount, setSplitTotalAmount] = useState('')
  const [splitTotalPeriods, setSplitTotalPeriods] = useState('')
  const [splitTagId, setSplitTagId] = useState('')
  const [splitDescription, setSplitDescription] = useState('')
  const [splitError, setSplitError] = useState<string | null>(null)
  const [splitSubmitting, setSplitSubmitting] = useState(false)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editDate, setEditDate] = useState('')
  const [editAmount, setEditAmount] = useState('')
  const [editTagId, setEditTagId] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editError, setEditError] = useState<string | null>(null)
  const [editSubmitting, setEditSubmitting] = useState(false)

  const [deletingId, setDeletingId] = useState<number | null>(null)

  const [horizon, setHorizon] = useState<Horizon>(3)
  const [projectionItems, setProjectionItems] = useState<ProjectionItem[]>([])
  const [projectionLoading, setProjectionLoading] = useState(false)
  const [projectionError, setProjectionError] = useState<string | null>(null)

  useEffect(() => {
    getTags().then(setTags).catch(() => undefined)
  }, [])

  function refetchPlannedExpenses(accountId: number, isStale?: () => boolean) {
    setPlannedExpensesLoading(true)
    return getPlannedExpenses(accountId)
      .then((data) => {
        if (isStale?.()) return
        setPlannedExpenses(data)
        setPlannedExpensesError(null)
      })
      .catch((err) => {
        if (isStale?.()) return
        setPlannedExpensesError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (isStale?.()) return
        setPlannedExpensesLoading(false)
      })
  }

  function refetchProjection(accountId: number, horizonMonths: Horizon, isStale?: () => boolean) {
    setProjectionLoading(true)
    return getProjection(accountId, horizonMonths)
      .then((data) => {
        if (isStale?.()) return
        setProjectionItems(data)
        setProjectionError(null)
      })
      .catch((err) => {
        if (isStale?.()) return
        setProjectionError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (isStale?.()) return
        setProjectionLoading(false)
      })
  }

  useEffect(() => {
    if (selectedAccountId === null) {
      setPlannedExpenses([])
      setProjectionItems([])
      return
    }
    let cancelled = false
    const isStale = () => cancelled
    refetchPlannedExpenses(selectedAccountId, isStale)
    refetchProjection(selectedAccountId, horizon, isStale)
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccountId])

  useEffect(() => {
    if (selectedAccountId === null) return
    let cancelled = false
    refetchProjection(selectedAccountId, horizon, () => cancelled)
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [horizon])

  function startAddingSimple() {
    setSimpleDate('')
    setSimpleAmount('')
    setSimpleTagId('')
    setSimpleDescription('')
    setSimpleError(null)
    setIsAddingSimple(true)
  }

  async function submitSimple() {
    if (selectedAccountId === null) return
    const magnitude = Number(simpleAmount.replace(',', '.'))
    if (simpleDate === '') {
      setSimpleError('La date est requise.')
      return
    }
    if (simpleAmount.trim() === '' || !Number.isFinite(magnitude) || magnitude <= 0) {
      setSimpleError('Le Montant doit être un nombre positif.')
      return
    }
    if (simpleTagId === '') {
      setSimpleError('Choisissez un Tag.')
      return
    }
    if (simpleDescription.trim() === '') {
      setSimpleError('La description ne peut pas être vide.')
      return
    }
    setSimpleSubmitting(true)
    try {
      await createPlannedExpense({
        account_id: selectedAccountId,
        tag_id: Number(simpleTagId),
        date: simpleDate,
        amount: -Math.abs(magnitude),
        description: simpleDescription,
      })
    } catch (err) {
      setSimpleError(err instanceof Error ? err.message : 'Erreur inattendue')
      setSimpleSubmitting(false)
      return
    }
    setIsAddingSimple(false)
    setSimpleSubmitting(false)
    await Promise.all([
      refetchPlannedExpenses(selectedAccountId),
      refetchProjection(selectedAccountId, horizon),
    ])
  }

  function startAddingSplit() {
    setSplitStartDate('')
    setSplitTotalAmount('')
    setSplitTotalPeriods('')
    setSplitTagId('')
    setSplitDescription('')
    setSplitError(null)
    setIsAddingSplit(true)
  }

  async function submitSplit() {
    if (selectedAccountId === null) return
    const totalAmount = Number(splitTotalAmount.replace(',', '.'))
    const totalPeriods = Number(splitTotalPeriods)
    if (splitStartDate === '') {
      setSplitError('La date de début est requise.')
      return
    }
    if (splitTotalAmount.trim() === '' || !Number.isFinite(totalAmount) || totalAmount <= 0) {
      setSplitError('Le Montant total doit être un nombre positif.')
      return
    }
    if (!Number.isInteger(totalPeriods) || totalPeriods < 2 || totalPeriods > 60) {
      setSplitError('Le nombre de périodes doit être un entier entre 2 et 60.')
      return
    }
    if (splitTagId === '') {
      setSplitError('Choisissez un Tag.')
      return
    }
    if (splitDescription.trim() === '') {
      setSplitError('La description ne peut pas être vide.')
      return
    }
    setSplitSubmitting(true)
    try {
      await createPlannedExpenseSplit({
        account_id: selectedAccountId,
        tag_id: Number(splitTagId),
        start_date: splitStartDate,
        total_amount: totalAmount,
        total_periods: totalPeriods,
        description: splitDescription,
      })
    } catch (err) {
      setSplitError(err instanceof Error ? err.message : 'Erreur inattendue')
      setSplitSubmitting(false)
      return
    }
    setIsAddingSplit(false)
    setSplitSubmitting(false)
    await Promise.all([
      refetchPlannedExpenses(selectedAccountId),
      refetchProjection(selectedAccountId, horizon),
    ])
  }

  function startEdit(expense: PlannedExpense) {
    setEditingId(expense.expense_id)
    setEditDate(expense.date)
    setEditAmount(String(Math.abs(expense.amount)))
    const tagId = existingTagId(expense.tag_id, tagById)
    setEditTagId(tagId !== null ? String(tagId) : '')
    setEditDescription(expense.description)
    setEditError(tagId === null ? "Le Tag d'origine a été supprimé — veuillez en choisir un nouveau." : null)
  }

  async function submitEdit() {
    if (editingId === null || selectedAccountId === null) return
    const magnitude = Number(editAmount.replace(',', '.'))
    if (editAmount.trim() === '' || !Number.isFinite(magnitude) || magnitude <= 0) {
      setEditError('Le Montant doit être un nombre positif.')
      return
    }
    if (editTagId === '') {
      setEditError('Choisissez un Tag.')
      return
    }
    if (editDescription.trim() === '') {
      setEditError('La description ne peut pas être vide.')
      return
    }
    setEditSubmitting(true)
    try {
      await updatePlannedExpense(editingId, {
        date: editDate,
        amount: -Math.abs(magnitude),
        tag_id: Number(editTagId),
        description: editDescription,
      })
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Erreur inattendue')
      setEditSubmitting(false)
      return
    }
    setEditingId(null)
    setEditSubmitting(false)
    await Promise.all([
      refetchPlannedExpenses(selectedAccountId),
      refetchProjection(selectedAccountId, horizon),
    ])
  }

  async function handleDelete(expense: PlannedExpense) {
    if (selectedAccountId === null) return
    const message =
      expense.series_id !== null
        ? `Cette dépense fait partie d'une série de ${expense.total_periods} — supprimer toute la série ?`
        : `Supprimer la Dépense planifiée « ${expense.description} » ?`
    if (!window.confirm(message)) return
    setDeletingId(expense.expense_id)
    try {
      await deletePlannedExpense(expense.expense_id)
    } catch (err) {
      setPlannedExpensesError(err instanceof Error ? err.message : 'Erreur inattendue')
      setDeletingId(null)
      return
    }
    setDeletingId(null)
    await Promise.all([
      refetchPlannedExpenses(selectedAccountId),
      refetchProjection(selectedAccountId, horizon),
    ])
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">Projection</h1>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {accountsError && <p className="text-body text-alert">{accountsError}</p>}
        {accountsLoaded && accounts.length > 0 && (
          <select
            value={selectedAccountId ?? ''}
            onChange={(e) => setSelectedAccountId(Number(e.target.value))}
            className={formFieldClass}
          >
            {accounts.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                {a.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="mt-6 overflow-hidden rounded border border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-panel px-4 py-3">
          <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
            Dépenses planifiées
          </span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={startAddingSimple}
              className="text-body-strong text-accent"
            >
              + Simple
            </button>
            <button
              type="button"
              onClick={startAddingSplit}
              className="text-body-strong text-accent"
            >
              + Ventilée
            </button>
          </div>
        </div>

        <div className="px-0 py-1">
          {plannedExpensesError && (
            <p className="px-4 py-3 text-body text-alert">{plannedExpensesError}</p>
          )}

          {isAddingSimple && (
            <div className="flex flex-col gap-2 border-b border-border-subtle px-4 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="date"
                  value={simpleDate}
                  onChange={(e) => setSimpleDate(e.target.value)}
                  disabled={simpleSubmitting}
                  className={formFieldClass}
                />
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="Montant"
                  value={simpleAmount}
                  onChange={(e) => setSimpleAmount(e.target.value)}
                  disabled={simpleSubmitting}
                  className={formFieldClass}
                />
                <select
                  value={simpleTagId}
                  onChange={(e) => setSimpleTagId(e.target.value)}
                  disabled={simpleSubmitting}
                  className={formFieldClass}
                >
                  <option value="">Choisir un Tag…</option>
                  {tags.map((t) => (
                    <option key={t.tag_id} value={t.tag_id}>
                      {tagBreadcrumb(t, tagById)}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  placeholder="Description"
                  value={simpleDescription}
                  onChange={(e) => setSimpleDescription(e.target.value)}
                  disabled={simpleSubmitting}
                  className={formFieldClass}
                />
                <button
                  type="button"
                  onClick={submitSimple}
                  disabled={simpleSubmitting}
                  className="text-body-strong text-accent disabled:opacity-60"
                >
                  Enregistrer
                </button>
                <button
                  type="button"
                  onClick={() => setIsAddingSimple(false)}
                  disabled={simpleSubmitting}
                  className="text-body text-ink-muted disabled:opacity-60"
                >
                  Annuler
                </button>
              </div>
              {simpleError && <p className="text-caption text-alert">{simpleError}</p>}
            </div>
          )}

          {isAddingSplit && (
            <div className="flex flex-col gap-2 border-b border-border-subtle px-4 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="date"
                  value={splitStartDate}
                  onChange={(e) => setSplitStartDate(e.target.value)}
                  disabled={splitSubmitting}
                  className={formFieldClass}
                />
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="Montant total"
                  value={splitTotalAmount}
                  onChange={(e) => setSplitTotalAmount(e.target.value)}
                  disabled={splitSubmitting}
                  className={formFieldClass}
                />
                <input
                  type="number"
                  step="1"
                  min="2"
                  max="60"
                  placeholder="Nb périodes"
                  value={splitTotalPeriods}
                  onChange={(e) => setSplitTotalPeriods(e.target.value)}
                  disabled={splitSubmitting}
                  className={formFieldClass}
                />
                <select
                  value={splitTagId}
                  onChange={(e) => setSplitTagId(e.target.value)}
                  disabled={splitSubmitting}
                  className={formFieldClass}
                >
                  <option value="">Choisir un Tag…</option>
                  {tags.map((t) => (
                    <option key={t.tag_id} value={t.tag_id}>
                      {tagBreadcrumb(t, tagById)}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  placeholder="Description"
                  value={splitDescription}
                  onChange={(e) => setSplitDescription(e.target.value)}
                  disabled={splitSubmitting}
                  className={formFieldClass}
                />
                <button
                  type="button"
                  onClick={submitSplit}
                  disabled={splitSubmitting}
                  className="text-body-strong text-accent disabled:opacity-60"
                >
                  Enregistrer
                </button>
                <button
                  type="button"
                  onClick={() => setIsAddingSplit(false)}
                  disabled={splitSubmitting}
                  className="text-body text-ink-muted disabled:opacity-60"
                >
                  Annuler
                </button>
              </div>
              <p className="text-caption text-ink-muted">
                La 1ère échéance est ramenée au début de la Période du Compte contenant cette
                date.
              </p>
              {splitError && <p className="text-caption text-alert">{splitError}</p>}
            </div>
          )}

          {plannedExpensesLoading && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}
          {!plannedExpensesLoading &&
            !plannedExpensesError &&
            plannedExpenses.length === 0 &&
            !isAddingSimple &&
            !isAddingSplit && (
              <p className="px-4 py-8 text-center text-body text-ink-muted">
                Aucune Dépense planifiée pour l'instant.
              </p>
            )}

          {plannedExpenses.map((expense) => (
            <div key={expense.expense_id} className="border-b border-border-subtle px-4 py-2">
              {editingId === expense.expense_id ? (
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="date"
                      value={editDate}
                      onChange={(e) => setEditDate(e.target.value)}
                      disabled={editSubmitting}
                      className={formFieldClass}
                    />
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={editAmount}
                      onChange={(e) => setEditAmount(e.target.value)}
                      disabled={editSubmitting}
                      className={formFieldClass}
                    />
                    <select
                      value={editTagId}
                      onChange={(e) => setEditTagId(e.target.value)}
                      disabled={editSubmitting}
                      className={formFieldClass}
                    >
                      <option value="">Choisir un Tag…</option>
                      {tags.map((t) => (
                        <option key={t.tag_id} value={t.tag_id}>
                          {tagBreadcrumb(t, tagById)}
                        </option>
                      ))}
                    </select>
                    <input
                      type="text"
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      disabled={editSubmitting}
                      className={formFieldClass}
                    />
                    <button
                      type="button"
                      onClick={submitEdit}
                      disabled={editSubmitting}
                      className="text-body-strong text-accent disabled:opacity-60"
                    >
                      Enregistrer
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      disabled={editSubmitting}
                      className="text-body text-ink-muted disabled:opacity-60"
                    >
                      Annuler
                    </button>
                  </div>
                  {editError && <p className="text-caption text-alert">{editError}</p>}
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-body-strong text-ink">
                      {expense.description}
                      {expense.series_id !== null && (
                        <span className="ml-2 text-caption text-ink-muted">
                          {expense.period_index}/{expense.total_periods}
                        </span>
                      )}
                    </p>
                    <p className="text-caption text-ink-muted">
                      {formatDate(expense.date)} · {formatMontant(expense.amount)}
                      {tagById.has(expense.tag_id)
                        ? ` · ${tagBreadcrumb(tagById.get(expense.tag_id) as Tag, tagById)}`
                        : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => startEdit(expense)}
                      className="text-body-strong text-accent"
                    >
                      Éditer
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(expense)}
                      disabled={deletingId === expense.expense_id}
                      className="text-body-strong text-alert disabled:opacity-60"
                    >
                      Supprimer
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded border border-border">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-panel px-4 py-3">
          <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
            Projection
          </span>
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value) as Horizon)}
            className={formFieldClass}
          >
            {horizons.map((h) => (
              <option key={h} value={h}>
                {h} mois
              </option>
            ))}
          </select>
        </div>

        <div className="px-0 py-1">
          {projectionError && <p className="px-4 py-3 text-body text-alert">{projectionError}</p>}
          {projectionLoading && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}
          {!projectionLoading && !projectionError && projectionItems.length === 0 && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">
              Aucun élément dans cet horizon.
            </p>
          )}
          {projectionItems.map((item, index) => (
            <div
              key={`${item.date}-${item.type}-${item.label}-${index}`}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-4 py-2"
            >
              <div>
                <p className="text-body-strong text-ink">{item.label}</p>
                <p className="text-caption text-ink-muted">
                  {formatDate(item.date)} · {typeLabels[item.type]}
                  {item.tag_name !== null ? ` · ${item.tag_name}` : ''}
                </p>
              </div>
              <p className="text-body-strong text-ink">{formatMontant(item.amount)}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}

export default Projection
