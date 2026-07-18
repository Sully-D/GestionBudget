import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, MouseEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { deleteTransaction, getTransactions, searchTransactions } from '../api/transactions'
import type { Transaction, TransactionSearchFilters } from '../api/transactions'
import { getTags } from '../api/tags'
import type { Tag } from '../api/tags'
import { formatDate, formatMontant, shiftDate, sortTagsByCategoryAndName, tagBreadcrumb } from '../lib/format'

function Transactions() {
  const navigate = useNavigate()
  // La période affichée vit dans l'URL (`?date=...`), pas dans un état local :
  // ainsi elle survit à un démontage/remontage de ce composant (ex. retour
  // d'historique après édition d'une Transaction sur une route distincte).
  const [searchParams, setSearchParams] = useSearchParams()
  const rawReferenceDate = searchParams.get('date')
  // Contrairement à l'ancien état local (toujours une sortie de `shiftDate`
  // ou `undefined`), cette valeur vient désormais d'une URL modifiable à la
  // main : on ignore silencieusement toute valeur qui n'a pas la forme
  // ISO `YYYY-MM-DD` plutôt que de la transmettre telle quelle au backend.
  const referenceDate =
    rawReferenceDate && /^\d{4}-\d{2}-\d{2}$/.test(rawReferenceDate) ? rawReferenceDate : undefined
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountId, setAccountId] = useState<number | null>(null)
  const [periodStart, setPeriodStart] = useState<string | null>(null)
  const [periodEnd, setPeriodEnd] = useState<string | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleteTarget, setDeleteTarget] = useState<Transaction | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)

  // Panneau de recherche : tant qu'au moins un filtre est actif, la page
  // bascule hors navigation par Période (recherche non bornée dans le temps
  // sur le Compte sélectionné, cf. spec-recherche-transactions).
  const [tags, setTags] = useState<Tag[]>([])
  const [labelFilter, setLabelFilter] = useState('')
  const [payeeFilter, setPayeeFilter] = useState('')
  const [amountFilter, setAmountFilter] = useState('')
  const [amountMinFilter, setAmountMinFilter] = useState('')
  const [amountMaxFilter, setAmountMaxFilter] = useState('')
  const [dateExactFilter, setDateExactFilter] = useState('')
  const [dateFromFilter, setDateFromFilter] = useState('')
  const [dateToFilter, setDateToFilter] = useState('')
  const [tagIdsFilter, setTagIdsFilter] = useState<number[]>([])

  const filtersActive =
    labelFilter.trim() !== '' ||
    payeeFilter.trim() !== '' ||
    amountFilter.trim() !== '' ||
    amountMinFilter.trim() !== '' ||
    amountMaxFilter.trim() !== '' ||
    dateExactFilter !== '' ||
    dateFromFilter !== '' ||
    dateToFilter !== '' ||
    tagIdsFilter.length > 0

  const tagsById = useMemo(() => new Map(tags.map((tag) => [tag.tag_id, tag])), [tags])
  const sortedTags = useMemo(() => sortTagsByCategoryAndName(tags, tagsById), [tags, tagsById])

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        setAccountId((current) => current ?? data[0]?.account_id ?? null)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
    // Échec silencieux : dégrade juste le panneau de filtres (case Tags
    // absente), n'empêche pas le reste de la page de fonctionner.
    getTags()
      .then((data) => setTags(data))
      .catch(() => {})
  }, [])

  const buildSearchFilters = useCallback(
    (): TransactionSearchFilters => ({
      label: labelFilter.trim() || undefined,
      payee: payeeFilter.trim() || undefined,
      amount: amountFilter.trim() ? Number(amountFilter.replace(',', '.')) : undefined,
      amountMin: amountMinFilter.trim() ? Number(amountMinFilter.replace(',', '.')) : undefined,
      amountMax: amountMaxFilter.trim() ? Number(amountMaxFilter.replace(',', '.')) : undefined,
      dateExact: dateExactFilter || undefined,
      dateFrom: dateFromFilter || undefined,
      dateTo: dateToFilter || undefined,
      tagIds: tagIdsFilter.length > 0 ? tagIdsFilter : undefined,
    }),
    [
      labelFilter,
      payeeFilter,
      amountFilter,
      amountMinFilter,
      amountMaxFilter,
      dateExactFilter,
      dateFromFilter,
      dateToFilter,
      tagIdsFilter,
    ],
  )

  const fetchList = useCallback(
    (currentAccountId: number) =>
      filtersActive
        ? searchTransactions(currentAccountId, buildSearchFilters())
        : getTransactions(currentAccountId, referenceDate),
    [filtersActive, referenceDate, buildSearchFilters],
  )

  useEffect(() => {
    if (accountId === null) return
    let cancelled = false
    setLoading(true)
    fetchList(accountId)
      .then((result) => {
        if (cancelled) return
        setPeriodStart(result.period_start)
        setPeriodEnd(result.period_end)
        setTransactions(result.transactions)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Erreur inattendue')
        // Éviter d'afficher le bandeau d'erreur en même temps qu'une liste
        // de transactions obsolète issue d'un compte/Période précédent.
        setTransactions([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [accountId, fetchList])

  function toggleTagFilter(tagId: number) {
    setTagIdsFilter((current) =>
      current.includes(tagId) ? current.filter((id) => id !== tagId) : [...current, tagId],
    )
  }

  function resetFilters() {
    setLabelFilter('')
    setPayeeFilter('')
    setAmountFilter('')
    setAmountMinFilter('')
    setAmountMaxFilter('')
    setDateExactFilter('')
    setDateFromFilter('')
    setDateToFilter('')
    setTagIdsFilter([])
  }

  // Escape ferme la confirmation-modal sans effet — n'agit que sur la modale,
  // ne navigue jamais en arrière (contrairement au raccourci Échap du
  // formulaire de saisie/édition, qui vit sur une page différente).
  useEffect(() => {
    if (deleteTarget === null) return
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        setDeleteTarget(null)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [deleteTarget])

  // Focus initial sur "Annuler" à l'ouverture de la modale (convention :
  // l'action non destructive reçoit le focus par défaut).
  useEffect(() => {
    if (deleteTarget !== null) {
      cancelButtonRef.current?.focus()
    }
  }, [deleteTarget])

  function goToPreviousPeriod() {
    if (periodStart) {
      // `replace: true` : la navigation entre périodes ne doit pas empiler
      // d'entrées d'historique, sinon "retour navigateur" devrait être pressé
      // une fois par période au lieu de quitter directement la page.
      // Updater fonctionnel (pas un objet littéral) : préserve tout autre
      // paramètre de recherche déjà présent au lieu de remplacer l'URL entière.
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('date', shiftDate(periodStart, -1))
          return next
        },
        { replace: true },
      )
    }
  }

  function goToNextPeriod() {
    if (periodEnd) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('date', shiftDate(periodEnd, 1))
          return next
        },
        { replace: true },
      )
    }
  }

  function openEdit(transaction: Transaction) {
    navigate(`/transactions/${transaction.transaction_id}/modifier`)
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLElement>, transaction: Transaction) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openEdit(transaction)
    }
  }

  function requestDelete(event: MouseEvent, transaction: Transaction) {
    event.stopPropagation()
    setDeleteError(null)
    setDeleteTarget(transaction)
  }

  // Le bouton de suppression vit à l'intérieur d'une ligne elle-même
  // activable au clavier (role="button") : sans ce stopPropagation dédié,
  // Entrée/Espace pressés sur le bouton remontent aussi au onKeyDown de la
  // ligne et déclenchent l'ouverture de l'édition en même temps que la
  // demande de suppression.
  function stopKeyPropagation(event: KeyboardEvent) {
    event.stopPropagation()
  }

  // Piège de focus minimal : seuls "Annuler" et "Supprimer" sont focusables
  // dans la modale (le reste de la page est rendu `inert`), donc un cycle à
  // deux éléments suffit à empêcher Tab d'en sortir.
  function handleModalKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return
    const first = cancelButtonRef.current
    const last = confirmButtonRef.current
    if (!first || !last) return
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  async function confirmDelete() {
    if (deleteTarget === null || accountId === null) return
    setDeleting(true)
    try {
      await deleteTransaction(deleteTarget.transaction_id)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Erreur inattendue')
      setDeleting(false)
      return
    }
    // La suppression a réussi côté serveur : fermer la modale immédiatement,
    // indépendamment du succès du re-fetch qui suit (AD-2 — re-fetch après
    // mutation, jamais de retrait optimiste local, mais un échec du re-fetch
    // ne doit pas laisser croire que la suppression elle-même a échoué).
    setDeleteTarget(null)
    setDeleting(false)
    try {
      const result = await fetchList(accountId)
      setPeriodStart(result.period_start)
      setPeriodEnd(result.period_end)
      setTransactions(result.transactions)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      <div inert={deleteTarget !== null}>
        <h1 className="text-page-title font-bold text-ink">Transactions</h1>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <select
            value={accountId ?? ''}
            onChange={(e) => {
              setAccountId(Number(e.target.value))
              setSearchParams(
                (prev) => {
                  const next = new URLSearchParams(prev)
                  next.delete('date')
                  return next
                },
                { replace: true },
              )
            }}
            className="rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink"
          >
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.name}
              </option>
            ))}
          </select>

          {filtersActive ? (
            <button
              type="button"
              onClick={resetFilters}
              className="rounded border border-border px-3 py-2 text-body text-accent"
            >
              Réinitialiser les filtres
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={goToPreviousPeriod}
                aria-label="Période précédente"
                className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
              >
                ‹
              </button>
              <span className="text-body text-ink">
                {periodStart && periodEnd
                  ? `${formatDate(periodStart)} – ${formatDate(periodEnd)}`
                  : ''}
              </span>
              <button
                type="button"
                onClick={goToNextPeriod}
                aria-label="Période suivante"
                className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
              >
                ›
              </button>
            </div>
          )}

          <Link to="/transactions/import" className="text-body text-accent underline">
            Importer un relevé
          </Link>
          <Link to="/transactions/nouvelle" className="text-body text-accent underline">
            Saisir manuellement
          </Link>
        </div>

        <div className="mt-3 flex flex-wrap items-end gap-3 rounded border border-border-subtle bg-surface p-3">
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Libellé
            <input
              type="text"
              value={labelFilter}
              onChange={(e) => setLabelFilter(e.target.value)}
              className="rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Tiers
            <input
              type="text"
              value={payeeFilter}
              onChange={(e) => setPayeeFilter(e.target.value)}
              className="rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Montant exact
            <input
              type="text"
              inputMode="decimal"
              value={amountFilter}
              onChange={(e) => setAmountFilter(e.target.value)}
              className="w-24 rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Montant min
            <input
              type="text"
              inputMode="decimal"
              value={amountMinFilter}
              onChange={(e) => setAmountMinFilter(e.target.value)}
              className="w-24 rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Montant max
            <input
              type="text"
              inputMode="decimal"
              value={amountMaxFilter}
              onChange={(e) => setAmountMaxFilter(e.target.value)}
              className="w-24 rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Date exacte
            <input
              type="date"
              value={dateExactFilter}
              onChange={(e) => setDateExactFilter(e.target.value)}
              className="rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Du
            <input
              type="date"
              value={dateFromFilter}
              onChange={(e) => setDateFromFilter(e.target.value)}
              className="rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-caption text-ink-muted">
            Au
            <input
              type="date"
              value={dateToFilter}
              onChange={(e) => setDateToFilter(e.target.value)}
              className="rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink"
            />
          </label>
          {sortedTags.length > 0 && (
            <div className="flex flex-col gap-1 text-caption text-ink-muted">
              Tags
              <div className="flex max-w-md flex-wrap gap-2">
                {sortedTags.map((tag) => (
                  <label
                    key={tag.tag_id}
                    className="flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-caption text-ink"
                  >
                    <input
                      type="checkbox"
                      checked={tagIdsFilter.includes(tag.tag_id)}
                      onChange={() => toggleTagFilter(tag.tag_id)}
                    />
                    {tagBreadcrumb(tag, tagsById)}
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {error && <p className="mt-4 text-body text-alert">{error}</p>}

        {!loading && !error && transactions.length === 0 && (
          <p className="mt-6 text-body text-ink-muted">
            {filtersActive
              ? 'Aucune Transaction ne correspond aux filtres.'
              : 'Aucune Transaction sur cette Période.'}
          </p>
        )}

        {transactions.length > 0 && (
          <>
            <table className="mt-6 hidden w-full lg:block lg:table">
              <thead className="bg-surface">
                <tr>
                  <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">
                    Date
                  </th>
                  <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">
                    Libellé
                  </th>
                  <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">
                    Tiers
                  </th>
                  <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">
                    Tags
                  </th>
                  <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">
                    Montant
                  </th>
                  <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => (
                  <tr
                    key={transaction.transaction_id}
                    role="button"
                    tabIndex={0}
                    onClick={() => openEdit(transaction)}
                    onKeyDown={(e) => handleRowKeyDown(e, transaction)}
                    className="cursor-pointer border-t border-border-subtle hover:bg-surface-panel"
                  >
                    <td className="px-2 py-2 text-body text-ink">
                      {formatDate(transaction.date)}
                    </td>
                    <td className="px-2 py-2 text-body text-ink">{transaction.label}</td>
                    <td className="px-2 py-2 text-body text-ink-muted">
                      {transaction.payee ?? ''}
                    </td>
                    <td className="px-2 py-2 text-body">
                      {transaction.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {transaction.tags.map((tag) => (
                            <span
                              key={tag.tag_id}
                              className="rounded-full bg-accent-bg px-2 py-0.5 text-caption font-bold text-accent"
                            >
                              {tag.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                      {formatMontant(transaction.amount)}
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button
                        type="button"
                        onClick={(e) => requestDelete(e, transaction)}
                        onKeyDown={stopKeyPropagation}
                        aria-label="Supprimer cette transaction"
                        className="flex h-11 w-11 items-center justify-center text-ink-muted hover:text-alert"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-6 flex flex-col gap-3 lg:hidden">
              {transactions.map((transaction) => (
                <div
                  key={transaction.transaction_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => openEdit(transaction)}
                  onKeyDown={(e) => handleRowKeyDown(e, transaction)}
                  className="cursor-pointer rounded border border-border bg-surface p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-body text-ink">{transaction.label}</span>
                    <div className="flex items-center gap-1">
                      <span className="font-mono text-body-strong text-ink">
                        {formatMontant(transaction.amount)}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => requestDelete(e, transaction)}
                        onKeyDown={stopKeyPropagation}
                        aria-label="Supprimer cette transaction"
                        className="flex h-11 w-11 items-center justify-center text-ink-muted hover:text-alert"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="text-caption text-ink-muted">
                      {formatDate(transaction.date)}
                    </span>
                    <span className="text-caption text-ink-muted">
                      {transaction.payee ?? ''}
                    </span>
                  </div>
                  {transaction.tags.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {transaction.tags.map((tag) => (
                        <span
                          key={tag.tag_id}
                          className="rounded-full bg-accent-bg px-2 py-0.5 text-caption font-bold text-accent"
                        >
                          {tag.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {deleteTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-modal-title"
            onKeyDown={handleModalKeyDown}
            className="w-full max-w-sm rounded border border-border bg-surface p-4"
          >
            <p id="delete-modal-title" className="text-body-strong text-ink">
              Supprimer cette transaction ?
            </p>
            {deleteError && (
              <div className="mt-2 flex flex-col gap-2">
                <p className="text-body text-alert">{deleteError}</p>
                <button
                  type="button"
                  onClick={confirmDelete}
                  className="self-start text-body-strong text-alert underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                ref={cancelButtonRef}
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="rounded border border-border px-3 py-2 text-body text-ink disabled:opacity-60"
              >
                Annuler
              </button>
              <button
                ref={confirmButtonRef}
                type="button"
                onClick={confirmDelete}
                disabled={deleting}
                className="rounded bg-alert px-3 py-2 text-body-strong text-surface disabled:opacity-60"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

export default Transactions
