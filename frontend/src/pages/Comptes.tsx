import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { getAccounts, updateAccount } from '../api/accounts'
import type { Account } from '../api/accounts'
import {
  addOneOff,
  deleteOneOff,
  deleteSalaireCorrection,
  getPeriodSummary,
  upsertSalaire,
} from '../api/budget'
import type { RevenuePeriodSummary } from '../api/budget'
import AccountCard from '../components/AccountCard'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_rgba(37,99,235,0.12)]'

function Comptes() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [startDay, setStartDay] = useState('')
  const [referenceBalance, setReferenceBalance] = useState('')
  const [referenceDate, setReferenceDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  const [summary, setSummary] = useState<RevenuePeriodSummary | null>(null)
  const [revenueError, setRevenueError] = useState<string | null>(null)
  const [salaireReference, setSalaireReference] = useState('')
  const [salaireCorrection, setSalaireCorrection] = useState('')
  const [oneOffAmount, setOneOffAmount] = useState('')
  const [oneOffDescription, setOneOffDescription] = useState('')

  const [oneOffDeleteTarget, setOneOffDeleteTarget] = useState<{
    revenue_id: number
    description: string | null
  } | null>(null)
  const [deletingOneOff, setDeletingOneOff] = useState(false)
  const [oneOffDeleteError, setOneOffDeleteError] = useState<string | null>(null)

  const [correctionResetConfirm, setCorrectionResetConfirm] = useState(false)
  const [resettingCorrection, setResettingCorrection] = useState(false)
  const [correctionResetError, setCorrectionResetError] = useState<string | null>(null)

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        setSelectedId((current) => current ?? data[0]?.account_id ?? null)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
  }, [])

  const selectedAccount = accounts.find((a) => a.account_id === selectedId) ?? null

  useEffect(() => {
    if (selectedAccount) {
      setStartDay(String(selectedAccount.start_day))
      setReferenceBalance(
        selectedAccount.reference_balance !== null
          ? String(selectedAccount.reference_balance)
          : '',
      )
      setReferenceDate(selectedAccount.reference_date ?? '')
      setError(null)
    }
  }, [selectedAccount])

  useEffect(() => {
    setSummary(null)
    setRevenueError(null)
    setSalaireCorrection('')
    setOneOffAmount('')
    setOneOffDescription('')
    if (!selectedAccount || selectedAccount.is_common) return
    let cancelled = false
    getPeriodSummary(selectedAccount.account_id, selectedAccount.period_start)
      .then((data) => {
        if (!cancelled) {
          setSummary(data)
          setSalaireReference(data.reference_amount !== null ? String(data.reference_amount) : '')
        }
      })
      .catch((err) => {
        if (!cancelled) setRevenueError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
    return () => {
      cancelled = true
    }
  }, [selectedAccount])

  async function refreshSummary() {
    if (!selectedAccount) return
    const updated = await getPeriodSummary(selectedAccount.account_id, selectedAccount.period_start)
    setSummary(updated)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!selectedAccount) return
    setError(null)
    const hasBalance = referenceBalance !== ''
    const hasDate = referenceDate !== ''
    if (hasBalance !== hasDate) {
      setError('Le solde de référence et sa date doivent être renseignés ensemble.')
      return
    }
    try {
      const hasReference = hasBalance && hasDate
      const updated = await updateAccount(selectedAccount.account_id, {
        start_day: Number(startDay),
        ...(hasReference
          ? {
              reference_balance: Number(referenceBalance),
              reference_date: referenceDate,
            }
          : {}),
      })
      setAccounts((prev) =>
        prev.map((a) => (a.account_id === updated.account_id ? updated : a)),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  async function handleSalaireReferenceSubmit(event: FormEvent) {
    event.preventDefault()
    if (!selectedAccount) return
    setRevenueError(null)
    try {
      await upsertSalaire({
        account_id: selectedAccount.account_id,
        period_start: null,
        amount: Number(salaireReference),
      })
      await refreshSummary()
    } catch (err) {
      setRevenueError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  async function handleSalaireCorrectionSubmit(event: FormEvent) {
    event.preventDefault()
    if (!selectedAccount) return
    setRevenueError(null)
    try {
      await upsertSalaire({
        account_id: selectedAccount.account_id,
        period_start: selectedAccount.period_start,
        amount: Number(salaireCorrection),
      })
      setSalaireCorrection('')
      await refreshSummary()
    } catch (err) {
      setRevenueError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function requestResetCorrection() {
    setCorrectionResetError(null)
    setCorrectionResetConfirm(true)
  }

  async function confirmResetCorrection() {
    if (!selectedAccount) return
    setResettingCorrection(true)
    try {
      await deleteSalaireCorrection(selectedAccount.account_id, selectedAccount.period_start)
    } catch (err) {
      setCorrectionResetError(err instanceof Error ? err.message : 'Erreur inattendue')
      setResettingCorrection(false)
      return
    }
    setCorrectionResetConfirm(false)
    setResettingCorrection(false)
    try {
      await refreshSummary()
    } catch (err) {
      setRevenueError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  async function handleAddOneOff(event: FormEvent) {
    event.preventDefault()
    if (!selectedAccount) return
    setRevenueError(null)
    try {
      await addOneOff({
        account_id: selectedAccount.account_id,
        period_start: selectedAccount.period_start,
        amount: Number(oneOffAmount),
        description: oneOffDescription,
      })
      setOneOffAmount('')
      setOneOffDescription('')
      await refreshSummary()
    } catch (err) {
      setRevenueError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function requestDeleteOneOff(entry: { revenue_id: number; description: string | null }) {
    setOneOffDeleteError(null)
    setOneOffDeleteTarget(entry)
  }

  async function confirmDeleteOneOff() {
    if (oneOffDeleteTarget === null) return
    setDeletingOneOff(true)
    try {
      await deleteOneOff(oneOffDeleteTarget.revenue_id)
    } catch (err) {
      setOneOffDeleteError(err instanceof Error ? err.message : 'Erreur inattendue')
      setDeletingOneOff(false)
      return
    }
    setOneOffDeleteTarget(null)
    setDeletingOneOff(false)
    try {
      await refreshSummary()
    } catch (err) {
      setRevenueError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">Comptes</h1>
      <div className="mt-4 flex flex-col gap-3">
        {accounts.map((account) => (
          <AccountCard
            key={account.account_id}
            account={account}
            selected={account.account_id === selectedId}
            onSelect={setSelectedId}
          />
        ))}
      </div>
      {selectedAccount && (
        <>
          <form
            onSubmit={handleSubmit}
            className="mt-6 flex flex-col gap-4 rounded border border-border bg-surface p-4"
          >
            <h2 className="text-section-title font-bold uppercase text-ink-muted">
              {selectedAccount.name}
            </h2>
            <label className="flex flex-col gap-1">
              <span className="text-label text-ink-muted">
                Jour de début de Période (1-28)
              </span>
              <input
                type="number"
                min={1}
                max={28}
                value={startDay}
                onChange={(e) => setStartDay(e.target.value)}
                className={formFieldClass}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-label text-ink-muted">
                Solde de référence — montant
              </span>
              <input
                type="number"
                step="0.01"
                value={referenceBalance}
                onChange={(e) => setReferenceBalance(e.target.value)}
                className={formFieldClass}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-label text-ink-muted">
                Solde de référence — date
              </span>
              <input
                type="date"
                value={referenceDate}
                onChange={(e) => setReferenceDate(e.target.value)}
                className={formFieldClass}
              />
            </label>
            {error && <p className="text-body text-alert">{error}</p>}
            <button
              type="submit"
              className="rounded-lg bg-accent px-4 py-2 text-body-strong text-surface"
            >
              Enregistrer
            </button>
          </form>

          {selectedAccount.is_common ? (
            <p className="mt-6 text-body text-ink-muted">
              Le Compte Commun n'a pas de revenus propres.
            </p>
          ) : (
            <section className="mt-6 flex flex-col gap-4 rounded border border-border bg-surface p-4">
              <h2 className="text-section-title font-bold uppercase text-ink-muted">Revenus</h2>
              {revenueError && <p className="text-body text-alert">{revenueError}</p>}
              {summary && (
                <>
                  <form onSubmit={handleSalaireReferenceSubmit} className="flex flex-col gap-1">
                    <label className="flex flex-col gap-1">
                      <span className="text-label text-ink-muted">Salaire de référence</span>
                      <input
                        type="number"
                        step="0.01"
                        value={salaireReference}
                        onChange={(e) => setSalaireReference(e.target.value)}
                        className={formFieldClass}
                      />
                    </label>
                    <button
                      type="submit"
                      className="self-start rounded-lg bg-accent px-3 py-1.5 text-body-strong text-surface"
                    >
                      Enregistrer
                    </button>
                  </form>

                  <div className="flex flex-col gap-2">
                    <span className="text-label text-ink-muted">Salaire de cette Période</span>
                    {summary.has_correction ? (
                      <div className="flex items-center gap-2">
                        <span className="text-body text-ink">
                          {summary.effective_salary.toFixed(2)} € (corrigé)
                        </span>
                        <button
                          type="button"
                          onClick={requestResetCorrection}
                          className="text-label text-accent"
                        >
                          Réinitialiser
                        </button>
                      </div>
                    ) : (
                      <span className="text-body text-ink-muted">
                        {summary.effective_salary.toFixed(2)} € (salaire de référence)
                      </span>
                    )}
                    <form onSubmit={handleSalaireCorrectionSubmit} className="flex items-end gap-2">
                      <label className="flex flex-col gap-1">
                        <span className="text-label text-ink-muted">Corriger pour cette Période</span>
                        <input
                          type="number"
                          step="0.01"
                          value={salaireCorrection}
                          onChange={(e) => setSalaireCorrection(e.target.value)}
                          className={formFieldClass}
                        />
                      </label>
                      <button
                        type="submit"
                        className="rounded-lg bg-accent px-3 py-1.5 text-body-strong text-surface"
                      >
                        Corriger
                      </button>
                    </form>
                  </div>

                  <div className="flex flex-col gap-2">
                    <span className="text-label text-ink-muted">
                      Rentrées ponctuelles de la Période
                    </span>
                    {summary.one_off.length === 0 && (
                      <p className="text-body text-ink-muted">Aucune rentrée ponctuelle.</p>
                    )}
                    <ul className="flex flex-col gap-1">
                      {summary.one_off.map((entry) => (
                        <li
                          key={entry.revenue_id}
                          className="flex items-center justify-between gap-2 text-body text-ink"
                        >
                          <span>
                            {entry.description} — {entry.amount.toFixed(2)} €
                          </span>
                          <button
                            type="button"
                            aria-label="Supprimer la rentrée ponctuelle"
                            onClick={() => requestDeleteOneOff(entry)}
                            className="text-ink-muted hover:text-alert"
                          >
                            ✕
                          </button>
                        </li>
                      ))}
                    </ul>
                    <form onSubmit={handleAddOneOff} className="flex items-end gap-2">
                      <label className="flex flex-col gap-1">
                        <span className="text-label text-ink-muted">Montant</span>
                        <input
                          type="number"
                          step="0.01"
                          value={oneOffAmount}
                          onChange={(e) => setOneOffAmount(e.target.value)}
                          className={formFieldClass}
                        />
                      </label>
                      <label className="flex flex-col gap-1">
                        <span className="text-label text-ink-muted">Description</span>
                        <input
                          type="text"
                          value={oneOffDescription}
                          onChange={(e) => setOneOffDescription(e.target.value)}
                          className={formFieldClass}
                        />
                      </label>
                      <button
                        type="submit"
                        className="rounded-lg bg-accent px-3 py-1.5 text-body-strong text-surface"
                      >
                        Ajouter
                      </button>
                    </form>
                  </div>

                  <p className="text-body-strong text-ink">
                    Total Revenus de la Période : {summary.total.toFixed(2)} €
                  </p>
                </>
              )}
            </section>
          )}
        </>
      )}

      {correctionResetConfirm && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-correction-modal-title"
            className="w-full max-w-sm rounded border border-border bg-surface p-4"
          >
            <p id="reset-correction-modal-title" className="text-body-strong text-ink">
              Réinitialiser le salaire de cette Période ?
            </p>
            {correctionResetError && (
              <div className="mt-2 flex flex-col gap-2">
                <p className="text-body text-alert">{correctionResetError}</p>
                <button
                  type="button"
                  onClick={confirmResetCorrection}
                  className="self-start text-body-strong text-alert underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCorrectionResetConfirm(false)}
                disabled={resettingCorrection}
                className="rounded border border-border px-3 py-2 text-body text-ink disabled:opacity-60"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={confirmResetCorrection}
                disabled={resettingCorrection}
                className="rounded bg-alert px-3 py-2 text-body-strong text-surface disabled:opacity-60"
              >
                Réinitialiser
              </button>
            </div>
          </div>
        </div>
      )}

      {oneOffDeleteTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-one-off-modal-title"
            className="w-full max-w-sm rounded border border-border bg-surface p-4"
          >
            <p id="delete-one-off-modal-title" className="text-body-strong text-ink">
              Supprimer la rentrée « {oneOffDeleteTarget.description} » ?
            </p>
            {oneOffDeleteError && (
              <div className="mt-2 flex flex-col gap-2">
                <p className="text-body text-alert">{oneOffDeleteError}</p>
                <button
                  type="button"
                  onClick={confirmDeleteOneOff}
                  className="self-start text-body-strong text-alert underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setOneOffDeleteTarget(null)}
                disabled={deletingOneOff}
                className="rounded border border-border px-3 py-2 text-body text-ink disabled:opacity-60"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={confirmDeleteOneOff}
                disabled={deletingOneOff}
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

export default Comptes
