import { useEffect, useState } from 'react'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { getDisponible } from '../api/budget'
import type { Disponible } from '../api/budget'
import AccountCard from '../components/AccountCard'
import { formatMontant, formatPourcentage } from '../lib/format'

function Dashboard() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)

  const [disponible, setDisponible] = useState<Disponible | null>(null)
  const [disponibleLoading, setDisponibleLoading] = useState(false)
  const [disponibleError, setDisponibleError] = useState<string | null>(null)

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

  useEffect(() => {
    setDisponible(null)
    setDisponibleError(null)

    if (!selectedAccount || selectedAccount.is_common) return

    let cancelled = false
    setDisponibleLoading(true)
    getDisponible(selectedAccount.account_id, selectedAccount.period_start)
      .then((data) => {
        if (!cancelled) setDisponible(data)
      })
      .catch((err) => {
        if (!cancelled) setDisponibleError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (!cancelled) setDisponibleLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedAccount])

  const pourcentageRevenus =
    disponible && disponible.revenus !== 0 ? (disponible.disponible / disponible.revenus) * 100 : 0

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      {selectedAccount?.is_common && (
        <p className="rounded border border-border bg-surface-panel p-4 text-body text-ink-muted">
          Le Compte Commun n'a pas de formule Disponible.
        </p>
      )}

      {selectedAccount && !selectedAccount.is_common && disponibleError && (
        <p className="text-body text-alert">{disponibleError}</p>
      )}

      {selectedAccount && !selectedAccount.is_common && disponibleLoading && !disponible && (
        <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
      )}

      {selectedAccount && !selectedAccount.is_common && disponible && (
        <>
          {/* Mobile : hero-card autonome + grille 2x2 de kpi-cards séparée */}
          <div className="lg:hidden">
            <div className="rounded-lg bg-ink p-4 text-surface">
              <p className="text-label uppercase text-sidebar-text-muted">Disponible</p>
              <p className="mt-1 font-mono text-hero-value-mobile font-bold">
                {formatMontant(disponible.disponible)}
              </p>
              <p className="mt-1 text-body text-positive">{formatPourcentage(pourcentageRevenus)} des Revenus</p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded border border-border bg-surface p-3">
                <p className="text-label uppercase text-ink-muted">Revenus</p>
                <p className="mt-1 font-mono text-body-strong text-ink">{formatMontant(disponible.revenus)}</p>
              </div>
              <div className="rounded border border-border bg-surface p-3">
                <p className="text-label uppercase text-ink-muted">Charges récur.</p>
                <p className="mt-1 font-mono text-body-strong text-alert">
                  {formatMontant(-disponible.charges_recurrentes)}
                </p>
              </div>
              <div className="rounded border border-border bg-surface p-3">
                <p className="text-label uppercase text-ink-muted">Dép. planifiées</p>
                <p className="mt-1 font-mono text-body-strong text-alert">
                  {formatMontant(-disponible.depenses_planifiees)}
                </p>
              </div>
              <div className="rounded border border-border bg-surface p-3">
                <p className="text-label uppercase text-ink-muted">Dép. courantes</p>
                <p className="mt-1 font-mono text-body-strong text-alert">
                  {formatMontant(-disponible.depenses_courantes)}
                </p>
              </div>
            </div>
          </div>

          {/* Desktop : un seul conteneur bordé, 5 cellules côte à côte */}
          <div className="hidden overflow-hidden rounded-md border border-border lg:grid lg:grid-cols-[200px_repeat(4,1fr)]">
            <div className="bg-ink p-4 text-surface">
              <p className="text-label uppercase text-sidebar-text-muted">Disponible</p>
              <p className="mt-1 font-mono text-hero-value font-bold">{formatMontant(disponible.disponible)}</p>
              <p className="mt-1 text-body text-positive">{formatPourcentage(pourcentageRevenus)} des Revenus</p>
            </div>
            <div className="border-r border-border p-4">
              <p className="text-label uppercase text-ink-muted">Revenus</p>
              <p className="mt-1 font-mono text-body-strong text-ink">{formatMontant(disponible.revenus)}</p>
            </div>
            <div className="border-r border-border p-4">
              <p className="text-label uppercase text-ink-muted">Charges récur.</p>
              <p className="mt-1 font-mono text-body-strong text-alert">
                {formatMontant(-disponible.charges_recurrentes)}
              </p>
            </div>
            <div className="border-r border-border p-4">
              <p className="text-label uppercase text-ink-muted">Dép. planifiées</p>
              <p className="mt-1 font-mono text-body-strong text-alert">
                {formatMontant(-disponible.depenses_planifiees)}
              </p>
            </div>
            <div className="p-4">
              <p className="text-label uppercase text-ink-muted">Dép. courantes</p>
              <p className="mt-1 font-mono text-body-strong text-alert">
                {formatMontant(-disponible.depenses_courantes)}
              </p>
            </div>
          </div>
        </>
      )}

      {accountsError && <p className="mt-4 text-body text-alert">{accountsError}</p>}

      <div className="mt-6 flex flex-col gap-3">
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

export default Dashboard
