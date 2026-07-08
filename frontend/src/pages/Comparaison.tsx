import { useEffect, useState } from 'react'
import { getAccounts, getAccountBalanceAsOf } from '../api/accounts'
import type { Account, AccountBalanceAsOf } from '../api/accounts'
import { getDisponible, getTagSpending } from '../api/budget'
import type { Disponible, TagSpending } from '../api/budget'
import { getTransactions } from '../api/transactions'
import type { Transaction } from '../api/transactions'
import AccountCard from '../components/AccountCard'
import { buildSpendingRows, formatDate, formatMontant, formatPourcentage, shiftDate } from '../lib/format'

function formatEcart(diff: number): string {
  return `${diff > 0 ? '+' : ''}${formatMontant(diff)}`
}

interface ComparisonTagRow {
  tagId: number
  label: string
  spentA: number
  spentB: number
}

// Union des Tags présents dans l'une ou l'autre Période (AC #2) : un Tag absent
// d'une des deux Périodes y est compté pour 0, jamais omis de la ligne.
function buildComparisonRows(tagSpendingA: TagSpending[], tagSpendingB: TagSpending[]): ComparisonTagRow[] {
  const rowsA = buildSpendingRows(tagSpendingA)
  const rowsB = buildSpendingRows(tagSpendingB)
  const spentById = new Map<number, { label: string; spentA: number; spentB: number }>()

  for (const { row, label } of rowsA) {
    spentById.set(row.tag_id, { label, spentA: row.spent, spentB: 0 })
  }
  for (const { row, label } of rowsB) {
    const existing = spentById.get(row.tag_id)
    if (existing) {
      existing.spentB = row.spent
    } else {
      spentById.set(row.tag_id, { label, spentA: 0, spentB: row.spent })
    }
  }

  return Array.from(spentById.entries())
    .map(([tagId, { label, spentA, spentB }]) => ({ tagId, label, spentA, spentB }))
    .sort((a, b) => a.label.localeCompare(b.label, 'fr'))
}

// Écart B - A en valeur et en % (base = valeur A, AC #2) : coloré favorable/
// défavorable selon le sens fourni par l'appelant (une hausse de Disponible/Solde
// est favorable, jamais l'inverse pour une dépense).
function EcartBadge({ diff, base, favorableWhenPositive }: { diff: number; base: number; favorableWhenPositive: boolean }) {
  if (diff === 0) return <span className="text-body text-ink-muted">—</span>
  const isFavorable = favorableWhenPositive ? diff > 0 : diff < 0
  const colorClass = isFavorable ? 'text-positive-text-strong' : 'text-alert-text-strong'
  const sign = diff > 0 ? '+' : ''
  const pct = base !== 0 ? (diff / Math.abs(base)) * 100 : null
  return (
    <span className={`font-mono text-body ${colorClass}`}>
      {sign}{formatMontant(diff)}
      {pct !== null && ` (${sign}${formatPourcentage(Math.abs(pct))})`}
    </span>
  )
}

function PeriodColumnHeader({
  label,
  periodStart,
  periodEnd,
  onPrevious,
  onNext,
}: {
  label: string
  periodStart: string | null
  periodEnd: string | null
  onPrevious: () => void
  onNext: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-label uppercase text-ink-muted">{label}</span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPrevious}
          aria-label={`${label} : Période précédente`}
          className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
        >
          ‹
        </button>
        <span className="text-body text-ink">
          {periodStart && periodEnd ? `${formatDate(periodStart)} – ${formatDate(periodEnd)}` : ''}
        </span>
        <button
          type="button"
          onClick={onNext}
          aria-label={`${label} : Période suivante`}
          className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
        >
          ›
        </button>
      </div>
    </div>
  )
}

function Comparaison() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)

  const [referenceDateA, setReferenceDateA] = useState<string | undefined>(undefined)
  const [referenceDateB, setReferenceDateB] = useState<string | undefined>(undefined)

  const [transactionsA, setTransactionsA] = useState<Transaction[]>([])
  const [transactionsALoading, setTransactionsALoading] = useState(false)
  const [transactionsAError, setTransactionsAError] = useState<string | null>(null)
  const [periodStartA, setPeriodStartA] = useState<string | null>(null)
  const [periodEndA, setPeriodEndA] = useState<string | null>(null)

  const [transactionsB, setTransactionsB] = useState<Transaction[]>([])
  const [transactionsBLoading, setTransactionsBLoading] = useState(false)
  const [transactionsBError, setTransactionsBError] = useState<string | null>(null)
  const [periodStartB, setPeriodStartB] = useState<string | null>(null)
  const [periodEndB, setPeriodEndB] = useState<string | null>(null)

  const [disponibleA, setDisponibleA] = useState<Disponible | null>(null)
  const [disponibleAError, setDisponibleAError] = useState<string | null>(null)
  const [disponibleB, setDisponibleB] = useState<Disponible | null>(null)
  const [disponibleBError, setDisponibleBError] = useState<string | null>(null)

  const [tagSpendingA, setTagSpendingA] = useState<TagSpending[]>([])
  const [tagSpendingALoading, setTagSpendingALoading] = useState(false)
  const [tagSpendingAError, setTagSpendingAError] = useState<string | null>(null)
  const [tagSpendingB, setTagSpendingB] = useState<TagSpending[]>([])
  const [tagSpendingBLoading, setTagSpendingBLoading] = useState(false)
  const [tagSpendingBError, setTagSpendingBError] = useState<string | null>(null)

  const [balanceA, setBalanceA] = useState<AccountBalanceAsOf | null>(null)
  const [balanceAError, setBalanceAError] = useState<string | null>(null)
  const [balanceB, setBalanceB] = useState<AccountBalanceAsOf | null>(null)
  const [balanceBError, setBalanceBError] = useState<string | null>(null)

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        setSelectedAccountId((current) => current ?? data.find((a) => !a.is_common)?.account_id ?? data[0]?.account_id ?? null)
        setAccountsError(null)
      })
      .catch((err) => {
        setAccountsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
  }, [])

  const selectedAccount = accounts.find((a) => a.account_id === selectedAccountId) ?? null

  // Changer de Compte réinitialise les deux Périodes à leurs valeurs par défaut
  // (A = Période courante, B = Période précédente) — ajustement pendant le rendu,
  // même pattern que Dashboard.tsx (Dev Notes 6.3), pour éviter la course d'effets.
  const [previousAccountId, setPreviousAccountId] = useState(selectedAccountId)
  if (selectedAccountId !== previousAccountId) {
    setPreviousAccountId(selectedAccountId)
    setReferenceDateA(undefined)
    setReferenceDateB(selectedAccount ? shiftDate(selectedAccount.period_start, -1) : undefined)
  }

  // Colonne A : résolution des bornes de Période puis, si non vide, données de comparaison.
  useEffect(() => {
    setTransactionsA([])
    setTransactionsAError(null)
    setPeriodStartA(null)
    setPeriodEndA(null)
    setDisponibleA(null)
    setDisponibleAError(null)
    setTagSpendingA([])
    setTagSpendingALoading(false)
    setTagSpendingAError(null)
    setBalanceA(null)
    setBalanceAError(null)

    if (!selectedAccount) return

    let cancelled = false

    setTransactionsALoading(true)
    getTransactions(selectedAccount.account_id, referenceDateA)
      .then((result) => {
        if (cancelled) return
        setPeriodStartA(result.period_start)
        setPeriodEndA(result.period_end)
        setTransactionsA(result.transactions)
        setTransactionsAError(null)

        if (result.transactions.length === 0) return

        const targetPeriodStart = referenceDateA ?? selectedAccount.period_start

        setTagSpendingALoading(true)
        getTagSpending(selectedAccount.account_id, targetPeriodStart)
          .then((data) => {
            if (!cancelled) setTagSpendingA(data)
          })
          .catch((err) => {
            if (!cancelled) setTagSpendingAError(err instanceof Error ? err.message : 'Erreur inattendue')
          })
          .finally(() => {
            if (!cancelled) setTagSpendingALoading(false)
          })

        getAccountBalanceAsOf(selectedAccount.account_id, result.period_end)
          .then((data) => {
            if (!cancelled) setBalanceA(data)
          })
          .catch((err) => {
            if (!cancelled) setBalanceAError(err instanceof Error ? err.message : 'Erreur inattendue')
          })

        if (!selectedAccount.is_common) {
          getDisponible(selectedAccount.account_id, targetPeriodStart)
            .then((data) => {
              if (!cancelled) setDisponibleA(data)
            })
            .catch((err) => {
              if (!cancelled) setDisponibleAError(err instanceof Error ? err.message : 'Erreur inattendue')
            })
        }
      })
      .catch((err) => {
        if (cancelled) return
        setTransactionsAError(err instanceof Error ? err.message : 'Erreur inattendue')
        setTransactionsA([])
      })
      .finally(() => {
        if (!cancelled) setTransactionsALoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedAccount, referenceDateA])

  // Colonne B : réplique fidèlement la logique de la colonne A (décision de portée :
  // pas de hook partagé dans cette story, cf. Dev Notes §Portée non couverte).
  useEffect(() => {
    setTransactionsB([])
    setTransactionsBError(null)
    setPeriodStartB(null)
    setPeriodEndB(null)
    setDisponibleB(null)
    setDisponibleBError(null)
    setTagSpendingB([])
    setTagSpendingBLoading(false)
    setTagSpendingBError(null)
    setBalanceB(null)
    setBalanceBError(null)

    if (!selectedAccount) return

    let cancelled = false

    setTransactionsBLoading(true)
    getTransactions(selectedAccount.account_id, referenceDateB)
      .then((result) => {
        if (cancelled) return
        setPeriodStartB(result.period_start)
        setPeriodEndB(result.period_end)
        setTransactionsB(result.transactions)
        setTransactionsBError(null)

        if (result.transactions.length === 0) return

        const targetPeriodStart = referenceDateB ?? selectedAccount.period_start

        setTagSpendingBLoading(true)
        getTagSpending(selectedAccount.account_id, targetPeriodStart)
          .then((data) => {
            if (!cancelled) setTagSpendingB(data)
          })
          .catch((err) => {
            if (!cancelled) setTagSpendingBError(err instanceof Error ? err.message : 'Erreur inattendue')
          })
          .finally(() => {
            if (!cancelled) setTagSpendingBLoading(false)
          })

        getAccountBalanceAsOf(selectedAccount.account_id, result.period_end)
          .then((data) => {
            if (!cancelled) setBalanceB(data)
          })
          .catch((err) => {
            if (!cancelled) setBalanceBError(err instanceof Error ? err.message : 'Erreur inattendue')
          })

        if (!selectedAccount.is_common) {
          getDisponible(selectedAccount.account_id, targetPeriodStart)
            .then((data) => {
              if (!cancelled) setDisponibleB(data)
            })
            .catch((err) => {
              if (!cancelled) setDisponibleBError(err instanceof Error ? err.message : 'Erreur inattendue')
            })
        }
      })
      .catch((err) => {
        if (cancelled) return
        setTransactionsBError(err instanceof Error ? err.message : 'Erreur inattendue')
        setTransactionsB([])
      })
      .finally(() => {
        if (!cancelled) setTransactionsBLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedAccount, referenceDateB])

  function goToPreviousPeriodA() {
    if (periodStartA) setReferenceDateA(shiftDate(periodStartA, -1))
  }
  function goToNextPeriodA() {
    if (periodEndA) setReferenceDateA(shiftDate(periodEndA, 1))
  }
  function goToPreviousPeriodB() {
    if (periodStartB) setReferenceDateB(shiftDate(periodStartB, -1))
  }
  function goToNextPeriodB() {
    if (periodEndB) setReferenceDateB(shiftDate(periodEndB, 1))
  }

  const bothPeriodsResolved = periodStartA !== null && periodStartB !== null
  const isEmptyState = bothPeriodsResolved && (transactionsA.length === 0 || transactionsB.length === 0)
  const isLoading = transactionsALoading || transactionsBLoading
  const transactionsErrorMessage = transactionsAError ?? transactionsBError
  const comparisonRows = buildComparisonRows(tagSpendingA, tagSpendingB)

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-title font-bold text-ink">Comparaison de Périodes</h1>

      {accountsError && <p className="mt-4 text-body text-alert">{accountsError}</p>}

      {selectedAccount && (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <PeriodColumnHeader
            label="Période A"
            periodStart={periodStartA}
            periodEnd={periodEndA}
            onPrevious={goToPreviousPeriodA}
            onNext={goToNextPeriodA}
          />
          <PeriodColumnHeader
            label="Période B"
            periodStart={periodStartB}
            periodEnd={periodEndB}
            onPrevious={goToPreviousPeriodB}
            onNext={goToNextPeriodB}
          />
        </div>
      )}

      {selectedAccount && isLoading && !transactionsErrorMessage && (
        <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
      )}

      {selectedAccount && !isLoading && transactionsErrorMessage && (
        <p className="mt-4 text-body text-alert">{transactionsErrorMessage}</p>
      )}

      {selectedAccount && !isLoading && !transactionsErrorMessage && isEmptyState && (
        <p className="mt-6 text-body text-ink-muted">
          Comparaison impossible tant qu'il n'y a pas deux Périodes de données.
        </p>
      )}

      {selectedAccount && !isLoading && !transactionsErrorMessage && !isEmptyState && bothPeriodsResolved && (
        <>
          {!selectedAccount.is_common && (disponibleA || disponibleB) && (
            <section className="mt-6 grid gap-4 lg:grid-cols-2">
              <div className="rounded border border-border bg-surface p-4">
                <p className="text-label uppercase text-ink-muted">Disponible</p>
                <p className="mt-1 font-mono text-body-strong text-ink">
                  {disponibleA ? formatMontant(disponibleA.disponible) : disponibleAError ? '—' : '…'}
                </p>
              </div>
              <div className="rounded border border-border bg-surface p-4">
                <p className="text-label uppercase text-ink-muted">Disponible</p>
                <p className="mt-1 font-mono text-body-strong text-ink">
                  {disponibleB ? formatMontant(disponibleB.disponible) : disponibleBError ? '—' : '…'}
                </p>
              </div>
              {disponibleA && disponibleB && (
                <div className="lg:col-span-2">
                  <span className="text-caption text-ink-muted">Écart : </span>
                  <EcartBadge
                    diff={disponibleB.disponible - disponibleA.disponible}
                    base={disponibleA.disponible}
                    favorableWhenPositive
                  />
                </div>
              )}
            </section>
          )}

          <section className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="rounded border border-border bg-surface p-4">
              <p className="text-label uppercase text-ink-muted">Solde de fin de Période</p>
              <p className="mt-1 font-mono text-body-strong text-ink">
                {balanceA ? formatMontant(balanceA.balance) : balanceAError ? '—' : '…'}
              </p>
            </div>
            <div className="rounded border border-border bg-surface p-4">
              <p className="text-label uppercase text-ink-muted">Solde de fin de Période</p>
              <p className="mt-1 font-mono text-body-strong text-ink">
                {balanceB ? formatMontant(balanceB.balance) : balanceBError ? '—' : '…'}
              </p>
            </div>
            {balanceA && balanceB && (
              <div className="lg:col-span-2">
                <span className="text-caption text-ink-muted">Écart : </span>
                <EcartBadge diff={balanceB.balance - balanceA.balance} base={balanceA.balance} favorableWhenPositive />
              </div>
            )}
          </section>

          <section className="mt-8">
            <h2 className="text-label uppercase text-ink-muted">Répartition par Tag</h2>

            {(tagSpendingAError || tagSpendingBError) && (
              <p className="mt-2 text-body text-alert">{tagSpendingAError ?? tagSpendingBError}</p>
            )}

            {(tagSpendingALoading || tagSpendingBLoading) && !tagSpendingAError && !tagSpendingBError && (
              <p className="mt-2 text-body text-ink-muted">Chargement…</p>
            )}

            {!tagSpendingALoading && !tagSpendingBLoading && !tagSpendingAError && !tagSpendingBError && comparisonRows.length === 0 && (
              <p className="mt-2 text-body text-ink-muted">Aucune dépense taguée sur ces Périodes.</p>
            )}

            {!tagSpendingAError && !tagSpendingBError && comparisonRows.length > 0 && (
              <>
                <table className="mt-4 hidden w-full lg:table">
                  <thead className="bg-surface">
                    <tr>
                      <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Tag</th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Période A</th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Période B</th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Écart</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonRows.map(({ tagId, label, spentA, spentB }) => (
                      <tr key={tagId} className="border-t border-border-subtle">
                        <td className="px-2 py-2 text-body text-ink">{label}</td>
                        <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                          {formatMontant(spentA)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                          {formatMontant(spentB)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-body text-ink-muted">
                          {formatEcart(spentB - spentA)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="mt-4 flex flex-col gap-3 lg:hidden">
                  {comparisonRows.map(({ tagId, label, spentA, spentB }) => (
                    <div key={tagId} className="rounded border border-border bg-surface p-3">
                      <span className="text-body text-ink">{label}</span>
                      <div className="mt-1 flex items-center justify-between text-caption text-ink-muted">
                        <span>A : {formatMontant(spentA)}</span>
                        <span>B : {formatMontant(spentB)}</span>
                      </div>
                      <div className="mt-1 text-caption text-ink-muted">Écart : {formatEcart(spentB - spentA)}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        </>
      )}

      <div className="mt-8 flex flex-col gap-3">
        {accounts.map((account) => (
          <AccountCard
            key={account.account_id}
            account={account}
            selected={account.account_id === selectedAccountId}
            onSelect={setSelectedAccountId}
          />
        ))}
      </div>
    </main>
  )
}

export default Comparaison
