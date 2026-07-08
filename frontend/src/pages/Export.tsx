import { useEffect, useState } from 'react'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { downloadFilteredExport, downloadFullExport } from '../api/export'

function Export() {
  const [loading, setLoading] = useState<'json' | 'csv' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)
  const [periodStart, setPeriodStart] = useState<string>('')
  const [periodEnd, setPeriodEnd] = useState<string>('')
  const [periodEdited, setPeriodEdited] = useState(false)
  const [filteredLoading, setFilteredLoading] = useState<'json' | 'csv' | null>(null)
  const [filteredError, setFilteredError] = useState<string | null>(null)

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        setAccountsError(null)
        const defaultAccount = data[0]
        if (defaultAccount) {
          setSelectedAccountId(defaultAccount.account_id)
          setPeriodStart(defaultAccount.period_start)
          setPeriodEnd(defaultAccount.period_end)
        }
      })
      .catch((err) => {
        setAccountsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
  }, [])

  function handleSelectAccount(accountId: number) {
    setSelectedAccountId(accountId)
    if (periodEdited) return
    const account = accounts.find((a) => a.account_id === accountId)
    if (account) {
      setPeriodStart(account.period_start)
      setPeriodEnd(account.period_end)
    }
  }

  async function handleDownload(format: 'json' | 'csv') {
    setLoading(format)
    setError(null)
    try {
      await downloadFullExport(format)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      setLoading(null)
    }
  }

  async function handleFilteredDownload(format: 'json' | 'csv') {
    if (selectedAccountId === null) return
    setFilteredLoading(format)
    setFilteredError(null)
    try {
      await downloadFilteredExport(selectedAccountId, format, periodStart || undefined, periodEnd || undefined)
    } catch (err) {
      setFilteredError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      setFilteredLoading(null)
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">Export des données</h1>

      <section className="mt-4 flex flex-col gap-3 rounded border border-border bg-surface p-4">
        <h2 className="text-body-strong text-ink">Export complet</h2>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => handleDownload('json')}
            disabled={loading !== null}
            className="rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)] disabled:opacity-60"
          >
            {loading === 'json' ? 'Chargement…' : 'Télécharger JSON'}
          </button>
          <button
            type="button"
            onClick={() => handleDownload('csv')}
            disabled={loading !== null}
            className="rounded-lg border border-border px-4 py-3 text-body-strong text-ink disabled:opacity-60"
          >
            {loading === 'csv' ? 'Chargement…' : 'Télécharger CSV'}
          </button>
        </div>
        {error && (
          <p role="alert" className="text-body text-alert">
            {error}
          </p>
        )}
      </section>

      <section className="mt-4 flex flex-col gap-3 rounded border border-border bg-surface p-4">
        <h2 className="text-body-strong text-ink">Export filtré</h2>

        {accountsError && (
          <p role="alert" className="text-body text-alert">
            {accountsError}
          </p>
        )}

        <label className="flex flex-col gap-1 text-body text-ink">
          Compte
          <select
            value={selectedAccountId ?? ''}
            onChange={(e) => handleSelectAccount(Number(e.target.value))}
            className="rounded border border-border px-3 py-2 text-body text-ink"
          >
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.name}
              </option>
            ))}
          </select>
        </label>

        <div className="flex gap-3">
          <label className="flex flex-1 flex-col gap-1 text-body text-ink">
            Du
            <input
              type="date"
              value={periodStart}
              onChange={(e) => {
                setPeriodStart(e.target.value)
                setPeriodEdited(true)
              }}
              className="rounded border border-border px-3 py-2 text-body text-ink"
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-body text-ink">
            Au
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => {
                setPeriodEnd(e.target.value)
                setPeriodEdited(true)
              }}
              className="rounded border border-border px-3 py-2 text-body text-ink"
            />
          </label>
        </div>

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => handleFilteredDownload('json')}
            disabled={filteredLoading !== null || selectedAccountId === null}
            className="rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)] disabled:opacity-60"
          >
            {filteredLoading === 'json' ? 'Chargement…' : 'Télécharger JSON'}
          </button>
          <button
            type="button"
            onClick={() => handleFilteredDownload('csv')}
            disabled={filteredLoading !== null || selectedAccountId === null}
            className="rounded-lg border border-border px-4 py-3 text-body-strong text-ink disabled:opacity-60"
          >
            {filteredLoading === 'csv' ? 'Chargement…' : 'Télécharger CSV'}
          </button>
        </div>

        {filteredError && (
          <p role="alert" className="text-body text-alert">
            {filteredError}
          </p>
        )}
      </section>
    </main>
  )
}

export default Export
