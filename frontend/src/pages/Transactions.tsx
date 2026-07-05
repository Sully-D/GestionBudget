import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { deleteTransaction, getTransactions } from '../api/transactions'
import type { Transaction } from '../api/transactions'
import { formatDate, formatMontant, shiftDate } from '../lib/format'

function Transactions() {
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountId, setAccountId] = useState<number | null>(null)
  const [referenceDate, setReferenceDate] = useState<string | undefined>(undefined)
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

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        setAccountId((current) => current ?? data[0]?.account_id ?? null)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
  }, [])

  useEffect(() => {
    if (accountId === null) return
    let cancelled = false
    setLoading(true)
    getTransactions(accountId, referenceDate)
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
  }, [accountId, referenceDate])

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
      setReferenceDate(shiftDate(periodStart, -1))
    }
  }

  function goToNextPeriod() {
    if (periodEnd) {
      setReferenceDate(shiftDate(periodEnd, 1))
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
      const result = await getTransactions(accountId, referenceDate)
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
              setReferenceDate(undefined)
            }}
            className="rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink"
          >
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.name}
              </option>
            ))}
          </select>

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

          <Link to="/transactions/import" className="text-body text-accent underline">
            Importer un relevé
          </Link>
        </div>

        {error && <p className="mt-4 text-body text-alert">{error}</p>}

        {!loading && !error && transactions.length === 0 && (
          <p className="mt-6 text-body text-ink-muted">
            Aucune Transaction sur cette Période.{' '}
            <Link to="/transactions/import" className="text-accent underline">
              Importer un relevé
            </Link>{' '}
            ou{' '}
            <Link to="/transactions/nouvelle" className="text-accent underline">
              saisir manuellement
            </Link>
            .
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
