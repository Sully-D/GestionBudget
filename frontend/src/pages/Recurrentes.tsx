import { useEffect, useMemo, useRef, useState } from 'react'
import {
  confirmRapprochement,
  confirmRecurring,
  createRecurringFromTransaction,
  deleteRecurring,
  getPendingRapprochements,
  getRecurringCandidates,
  getRecurringTransactions,
  rejectRapprochement,
  rejectRecurring,
  updateRecurring,
} from '../api/projections'
import type {
  Periodicity,
  RapprochementCandidate,
  RecurringCandidate,
  RecurringTransaction,
} from '../api/projections'
import { getTags } from '../api/tags'
import type { Tag } from '../api/tags'
import { getTransactions } from '../api/transactions'
import type { Transaction } from '../api/transactions'
import { useSelectableAccounts } from '../hooks/useSelectableAccounts'
import { existingTagId, formatMontant, tagBreadcrumb } from '../lib/format'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink focus:border-accent focus:outline-none'

const periodicityLabels: Record<Periodicity, string> = {
  hebdomadaire: 'Hebdomadaire',
  mensuelle: 'Mensuelle',
  trimestrielle: 'Trimestrielle',
  annuelle: 'Annuelle',
}

const periodicities = Object.keys(periodicityLabels) as Periodicity[]

function Recurrentes() {
  const { accounts, accountsLoaded, accountsError, selectedAccountId, setSelectedAccountId } =
    useSelectableAccounts()

  const [tags, setTags] = useState<Tag[]>([])
  const tagById = useMemo(() => new Map(tags.map((t) => [t.tag_id, t])), [tags])

  const [candidates, setCandidates] = useState<RecurringCandidate[]>([])
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidatesError, setCandidatesError] = useState<string | null>(null)
  const [candidateTagChoice, setCandidateTagChoice] = useState<Record<string, string>>({})

  const [confirmedList, setConfirmedList] = useState<RecurringTransaction[]>([])
  const [confirmedLoading, setConfirmedLoading] = useState(false)
  const [confirmedError, setConfirmedError] = useState<string | null>(null)

  const [pendingRapprochements, setPendingRapprochements] = useState<RapprochementCandidate[]>([])
  const [pendingRapprochementsLoading, setPendingRapprochementsLoading] = useState(false)
  const [pendingRapprochementsError, setPendingRapprochementsError] = useState<string | null>(null)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editAmount, setEditAmount] = useState('')
  const [editPeriodicity, setEditPeriodicity] = useState<Periodicity>('mensuelle')
  const [editTagId, setEditTagId] = useState('')
  const [editError, setEditError] = useState<string | null>(null)
  const [editSubmitting, setEditSubmitting] = useState(false)

  const [deletingId, setDeletingId] = useState<number | null>(null)

  const [addFormOpen, setAddFormOpen] = useState(false)
  const [addTransactions, setAddTransactions] = useState<Transaction[]>([])
  const [addTransactionsLoading, setAddTransactionsLoading] = useState(false)
  const [addTransactionsError, setAddTransactionsError] = useState<string | null>(null)
  const [addTransactionId, setAddTransactionId] = useState('')
  const [addLabel, setAddLabel] = useState('')
  const [addAmount, setAddAmount] = useState('')
  const [addPeriodicity, setAddPeriodicity] = useState<Periodicity>('mensuelle')
  const [addTagId, setAddTagId] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [addSubmitting, setAddSubmitting] = useState(false)
  const addRequestIdRef = useRef(0)

  useEffect(() => {
    getTags().then(setTags).catch(() => undefined)
  }, [])

  function refetchCandidates(accountId: number, isStale?: () => boolean) {
    setCandidatesLoading(true)
    return getRecurringCandidates(accountId)
      .then((data) => {
        if (isStale?.()) return
        setCandidates(data)
        setCandidatesError(null)
      })
      .catch((err) => {
        if (isStale?.()) return
        setCandidatesError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (isStale?.()) return
        setCandidatesLoading(false)
      })
  }

  function refetchConfirmed(accountId: number, isStale?: () => boolean) {
    setConfirmedLoading(true)
    return getRecurringTransactions(accountId, 'confirmed')
      .then((data) => {
        if (isStale?.()) return
        setConfirmedList(data)
        setConfirmedError(null)
      })
      .catch((err) => {
        if (isStale?.()) return
        setConfirmedError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (isStale?.()) return
        setConfirmedLoading(false)
      })
  }

  function refetchPendingRapprochements(accountId: number, isStale?: () => boolean) {
    setPendingRapprochementsLoading(true)
    return getPendingRapprochements(accountId)
      .then((data) => {
        if (isStale?.()) return
        setPendingRapprochements(data)
        setPendingRapprochementsError(null)
      })
      .catch((err) => {
        if (isStale?.()) return
        setPendingRapprochementsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (isStale?.()) return
        setPendingRapprochementsLoading(false)
      })
  }

  useEffect(() => {
    // Le picker de la Transaction sélectionnée n'a plus de sens si le compte
    // change sous le formulaire ouvert : on referme plutôt que de risquer une
    // soumission avec un `transaction_id` d'un autre compte.
    setAddFormOpen(false)
    if (selectedAccountId === null) {
      setCandidates([])
      setConfirmedList([])
      setPendingRapprochements([])
      setPendingRapprochementsError(null)
      return
    }
    let cancelled = false
    const isStale = () => cancelled
    refetchCandidates(selectedAccountId, isStale)
    refetchConfirmed(selectedAccountId, isStale)
    refetchPendingRapprochements(selectedAccountId, isStale)
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccountId])

  async function handleConfirmCandidate(candidate: RecurringCandidate) {
    if (selectedAccountId === null) return
    const chosen = candidateTagChoice[candidate.signature]
    const tagId = chosen !== undefined ? (chosen === '' ? null : Number(chosen)) : candidate.suggested_tag_id
    try {
      await confirmRecurring({
        account_id: selectedAccountId,
        signature: candidate.signature,
        label: candidate.label,
        amount: candidate.amount,
        periodicity: candidate.periodicity,
        tag_id: tagId,
      })
    } catch (err) {
      setCandidatesError(err instanceof Error ? err.message : 'Erreur inattendue')
      return
    }
    await Promise.all([refetchCandidates(selectedAccountId), refetchConfirmed(selectedAccountId)])
  }

  async function handleRejectCandidate(candidate: RecurringCandidate) {
    if (selectedAccountId === null) return
    try {
      await rejectRecurring({
        account_id: selectedAccountId,
        signature: candidate.signature,
        label: candidate.label,
        amount: candidate.amount,
        periodicity: candidate.periodicity,
      })
    } catch (err) {
      setCandidatesError(err instanceof Error ? err.message : 'Erreur inattendue')
      return
    }
    await refetchCandidates(selectedAccountId)
  }

  async function handleConfirmRapprochement(match: RapprochementCandidate) {
    if (selectedAccountId === null) return
    try {
      await confirmRapprochement(match.match_id)
    } catch (err) {
      setPendingRapprochementsError(err instanceof Error ? err.message : 'Erreur inattendue')
      return
    }
    await Promise.all([
      refetchPendingRapprochements(selectedAccountId),
      refetchConfirmed(selectedAccountId),
    ])
  }

  async function handleRejectRapprochement(match: RapprochementCandidate) {
    if (selectedAccountId === null) return
    try {
      await rejectRapprochement(match.match_id)
    } catch (err) {
      setPendingRapprochementsError(err instanceof Error ? err.message : 'Erreur inattendue')
      return
    }
    await refetchPendingRapprochements(selectedAccountId)
  }

  function startEdit(recurring: RecurringTransaction) {
    setEditingId(recurring.recurring_id)
    setEditAmount(String(Math.abs(recurring.amount)))
    setEditPeriodicity(recurring.periodicity)
    const tagId = existingTagId(recurring.tag_id, tagById)
    setEditTagId(tagId !== null ? String(tagId) : '')
    setEditError(
      recurring.tag_id !== null && tagId === null
        ? "Le Tag d'origine a été supprimé — Aucun Tag a été sélectionné à la place."
        : null,
    )
  }

  async function submitEdit() {
    if (editingId === null || selectedAccountId === null) return
    const magnitude = Number(editAmount.replace(',', '.'))
    if (editAmount.trim() === '' || !Number.isFinite(magnitude) || magnitude <= 0) {
      setEditError('Le Montant doit être un nombre positif.')
      return
    }
    setEditSubmitting(true)
    try {
      await updateRecurring(editingId, {
        amount: -Math.abs(magnitude),
        periodicity: editPeriodicity,
        tag_id: editTagId === '' ? null : Number(editTagId),
      })
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Erreur inattendue')
      setEditSubmitting(false)
      return
    }
    setEditingId(null)
    setEditSubmitting(false)
    await refetchConfirmed(selectedAccountId)
  }

  async function handleDelete(recurring: RecurringTransaction) {
    if (selectedAccountId === null) return
    if (!window.confirm(`Supprimer la Récurrente « ${recurring.label} » ?`)) return
    setDeletingId(recurring.recurring_id)
    try {
      await deleteRecurring(recurring.recurring_id)
    } catch (err) {
      setConfirmedError(err instanceof Error ? err.message : 'Erreur inattendue')
      setDeletingId(null)
      return
    }
    setDeletingId(null)
    await refetchConfirmed(selectedAccountId)
  }

  function openAddForm() {
    if (selectedAccountId === null) return
    const requestId = ++addRequestIdRef.current
    setAddFormOpen(true)
    setAddError(null)
    setAddTransactionId('')
    setAddLabel('')
    setAddAmount('')
    setAddPeriodicity('mensuelle')
    setAddTagId('')
    setAddTransactionsError(null)
    setAddTransactionsLoading(true)
    // Picker = période courante du compte (`getTransactions(accountId)` sans
    // `referenceDate`), filtré côté client aux dépenses (amount < 0).
    getTransactions(selectedAccountId)
      .then((list) => {
        if (addRequestIdRef.current !== requestId) return
        setAddTransactions(list.transactions.filter((t) => t.amount < 0))
        setAddTransactionsError(null)
      })
      .catch((err) => {
        if (addRequestIdRef.current !== requestId) return
        setAddTransactionsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (addRequestIdRef.current !== requestId) return
        setAddTransactionsLoading(false)
      })
  }

  function closeAddForm() {
    addRequestIdRef.current += 1
    setAddFormOpen(false)
  }

  function selectAddTransaction(transactionId: string) {
    setAddTransactionId(transactionId)
    const transaction = addTransactions.find((t) => String(t.transaction_id) === transactionId)
    setAddLabel(transaction ? (transaction.payee ? transaction.payee : transaction.label) : '')
    setAddAmount(transaction ? Math.abs(transaction.amount).toFixed(2) : '')
    setAddError(null)
  }

  async function submitAdd() {
    if (selectedAccountId === null) return
    if (addTransactionId === '') {
      setAddError('Sélectionnez une Transaction.')
      return
    }
    const trimmedLabel = addLabel.trim()
    if (trimmedLabel === '') {
      setAddError('Le Libellé ne peut pas être composé uniquement d\'espaces.')
      return
    }
    const magnitude = Number(addAmount.replace(',', '.'))
    if (addAmount.trim() === '' || !Number.isFinite(magnitude) || magnitude <= 0) {
      setAddError('Le Montant doit être un nombre positif.')
      return
    }
    setAddSubmitting(true)
    try {
      await createRecurringFromTransaction({
        transaction_id: Number(addTransactionId),
        label: trimmedLabel,
        amount: -Math.abs(magnitude),
        periodicity: addPeriodicity,
        tag_id: addTagId === '' ? null : Number(addTagId),
      })
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Erreur inattendue')
      setAddSubmitting(false)
      return
    }
    addRequestIdRef.current += 1
    setAddSubmitting(false)
    setAddFormOpen(false)
    await Promise.all([
      refetchCandidates(selectedAccountId),
      refetchConfirmed(selectedAccountId),
      refetchPendingRapprochements(selectedAccountId),
    ])
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">Récurrentes</h1>

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
        <div className="border-b border-border bg-surface-panel px-4 py-3">
          <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
            Candidates détectées
          </span>
        </div>
        <div className="px-0 py-1">
          {candidatesError && <p className="px-4 py-3 text-body text-alert">{candidatesError}</p>}
          {candidatesLoading && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}
          {!candidatesLoading && !candidatesError && candidates.length === 0 && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">
              Aucune candidate détectée pour l'instant.
            </p>
          )}
          {candidates.map((candidate) => (
            <div
              key={candidate.signature}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-4 py-2"
            >
              <div>
                <p className="text-body-strong text-ink">{candidate.label}</p>
                <p className="text-caption text-ink-muted">
                  {formatMontant(candidate.amount)} · {periodicityLabels[candidate.periodicity]} ·{' '}
                  {candidate.occurrence_count} occurrences
                </p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={
                    candidateTagChoice[candidate.signature] ??
                    (candidate.suggested_tag_id !== null ? String(candidate.suggested_tag_id) : '')
                  }
                  onChange={(e) =>
                    setCandidateTagChoice((current) => ({
                      ...current,
                      [candidate.signature]: e.target.value,
                    }))
                  }
                  className={formFieldClass}
                >
                  <option value="">Aucun Tag</option>
                  {tags.map((t) => (
                    <option key={t.tag_id} value={t.tag_id}>
                      {tagBreadcrumb(t, tagById)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => handleConfirmCandidate(candidate)}
                  className="text-body-strong text-accent"
                >
                  Confirmer
                </button>
                <button
                  type="button"
                  onClick={() => handleRejectCandidate(candidate)}
                  className="text-body-strong text-alert"
                >
                  Rejeter
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded border border-border">
        <div className="border-b border-border bg-surface-panel px-4 py-3">
          <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
            Rapprochements en attente
          </span>
        </div>
        <div className="px-0 py-1">
          {pendingRapprochementsError && (
            <p className="px-4 py-3 text-body text-alert">{pendingRapprochementsError}</p>
          )}
          {pendingRapprochementsLoading && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}
          {!pendingRapprochementsLoading &&
            !pendingRapprochementsError &&
            pendingRapprochements.length === 0 && (
              <p className="px-4 py-8 text-center text-body text-ink-muted">
                Aucun Rapprochement en attente.
              </p>
            )}
          {pendingRapprochements.map((match) => (
            <div
              key={match.match_id}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-4 py-2"
            >
              <div>
                <p className="text-body-strong text-ink">{match.transaction_label}</p>
                <p className="text-caption text-ink-muted">
                  {formatMontant(match.transaction_amount)} · {match.transaction_date} ·{' '}
                  {match.recurring_label}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleConfirmRapprochement(match)}
                  className="text-body-strong text-accent"
                >
                  Confirmer
                </button>
                <button
                  type="button"
                  onClick={() => handleRejectRapprochement(match)}
                  className="text-body-strong text-alert"
                >
                  Ignorer
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded border border-border">
        <div className="border-b border-border bg-surface-panel px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
              Récurrentes confirmées
            </span>
            {!addFormOpen && (
              <button
                type="button"
                onClick={openAddForm}
                disabled={selectedAccountId === null}
                className="text-body-strong text-accent disabled:opacity-60"
              >
                Ajouter une Récurrente
              </button>
            )}
          </div>
        </div>
        {addFormOpen && (
          <div className="border-b border-border-subtle px-4 py-3">
            <div className="flex flex-col gap-2">
              {addTransactionsLoading && (
                <p className="text-body text-ink-muted">Chargement des Transactions…</p>
              )}
              {addTransactionsError && (
                <p className="text-body text-alert">{addTransactionsError}</p>
              )}
              {!addTransactionsLoading &&
                !addTransactionsError &&
                addTransactions.length === 0 && (
                  <p className="text-body text-ink-muted">
                    Aucune dépense disponible sur la période courante de ce compte.
                  </p>
                )}
              {!addTransactionsLoading && !addTransactionsError && addTransactions.length > 0 && (
                <>
                  <select
                    value={addTransactionId}
                    onChange={(e) => selectAddTransaction(e.target.value)}
                    disabled={addSubmitting}
                    className={formFieldClass}
                  >
                    <option value="">Choisir une Transaction…</option>
                    {addTransactions.map((t) => (
                      <option key={t.transaction_id} value={t.transaction_id}>
                        {t.date} · {t.payee ? t.payee : t.label} · {formatMontant(t.amount)}
                      </option>
                    ))}
                  </select>
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="text"
                      value={addLabel}
                      onChange={(e) => setAddLabel(e.target.value)}
                      disabled={addSubmitting}
                      placeholder="Libellé"
                      className={formFieldClass}
                    />
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={addAmount}
                      onChange={(e) => setAddAmount(e.target.value)}
                      disabled={addSubmitting}
                      className={formFieldClass}
                    />
                    <select
                      value={addPeriodicity}
                      onChange={(e) => setAddPeriodicity(e.target.value as Periodicity)}
                      disabled={addSubmitting}
                      className={formFieldClass}
                    >
                      {periodicities.map((p) => (
                        <option key={p} value={p}>
                          {periodicityLabels[p]}
                        </option>
                      ))}
                    </select>
                    <select
                      value={addTagId}
                      onChange={(e) => setAddTagId(e.target.value)}
                      disabled={addSubmitting}
                      className={formFieldClass}
                    >
                      <option value="">Aucun Tag</option>
                      {tags.map((t) => (
                        <option key={t.tag_id} value={t.tag_id}>
                          {tagBreadcrumb(t, tagById)}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={submitAdd}
                      disabled={addSubmitting || addTransactionId === ''}
                      className="text-body-strong text-accent disabled:opacity-60"
                    >
                      Enregistrer
                    </button>
                  </div>
                </>
              )}
              <div>
                <button
                  type="button"
                  onClick={closeAddForm}
                  disabled={addSubmitting}
                  className="text-body text-ink-muted disabled:opacity-60"
                >
                  Annuler
                </button>
              </div>
              {addError && <p className="text-caption text-alert">{addError}</p>}
            </div>
          </div>
        )}
        <div className="px-0 py-1">
          {confirmedError && <p className="px-4 py-3 text-body text-alert">{confirmedError}</p>}
          {confirmedLoading && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}
          {!confirmedLoading && !confirmedError && confirmedList.length === 0 && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">
              Aucune Récurrente confirmée pour l'instant.
            </p>
          )}
          {confirmedList.map((recurring) => (
            <div key={recurring.recurring_id} className="border-b border-border-subtle px-4 py-2">
              {editingId === recurring.recurring_id ? (
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
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
                      value={editPeriodicity}
                      onChange={(e) => setEditPeriodicity(e.target.value as Periodicity)}
                      disabled={editSubmitting}
                      className={formFieldClass}
                    >
                      {periodicities.map((p) => (
                        <option key={p} value={p}>
                          {periodicityLabels[p]}
                        </option>
                      ))}
                    </select>
                    <select
                      value={editTagId}
                      onChange={(e) => setEditTagId(e.target.value)}
                      disabled={editSubmitting}
                      className={formFieldClass}
                    >
                      <option value="">Aucun Tag</option>
                      {tags.map((t) => (
                        <option key={t.tag_id} value={t.tag_id}>
                          {tagBreadcrumb(t, tagById)}
                        </option>
                      ))}
                    </select>
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
                    <p className="text-body-strong text-ink">{recurring.label}</p>
                    <p className="text-caption text-ink-muted">
                      {formatMontant(recurring.amount)} · {periodicityLabels[recurring.periodicity]}
                      {recurring.tag_id !== null && tagById.has(recurring.tag_id)
                        ? ` · ${tagBreadcrumb(tagById.get(recurring.tag_id) as Tag, tagById)}`
                        : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => startEdit(recurring)}
                      className="text-body-strong text-accent"
                    >
                      Éditer
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(recurring)}
                      disabled={deletingId === recurring.recurring_id}
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
    </main>
  )
}

export default Recurrentes
