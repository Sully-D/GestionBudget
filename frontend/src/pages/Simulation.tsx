import { useState } from 'react'
import { calculerDisponibleSimule, formatMontant } from '../lib/format'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_rgba(37,99,235,0.12)]'

const DEFAULT_REVENUS = 3000
const DEFAULT_CHARGES = 1200
const DEFAULT_DEPENSES_PLANIFIEES = 400
const DEFAULT_DEPENSES_COURANTES = 700

function Simulation() {
  const [revenus, setRevenus] = useState(String(DEFAULT_REVENUS))
  const [charges, setCharges] = useState(String(DEFAULT_CHARGES))
  const [depensesPlanifiees, setDepensesPlanifiees] = useState(String(DEFAULT_DEPENSES_PLANIFIEES))
  const [depensesCourantes, setDepensesCourantes] = useState(String(DEFAULT_DEPENSES_COURANTES))

  const disponible = calculerDisponibleSimule(
    Number(revenus.replace(',', '.')) || 0,
    Number(charges.replace(',', '.')) || 0,
    Number(depensesPlanifiees.replace(',', '.')) || 0,
    Number(depensesCourantes.replace(',', '.')) || 0,
  )
  const isPositive = disponible >= 0

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">Simulation</h1>
      <p className="mt-1 text-body text-ink-muted">
        Mode sandbox — valeurs fictives, rien n'est sauvegardé ni envoyé au serveur.
      </p>

      <form
        onSubmit={(e) => e.preventDefault()}
        className="mt-6 flex flex-col gap-4 rounded border border-border bg-surface p-4"
      >
        <h2 className="text-section-title font-bold uppercase text-ink-muted">
          Scénario budgétaire
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-1 lg:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Revenus</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={revenus}
              onChange={(e) => setRevenus(e.target.value)}
              className={formFieldClass}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Charges récurrentes mensuelles</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={charges}
              onChange={(e) => setCharges(e.target.value)}
              className={formFieldClass}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Dépenses planifiées</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={depensesPlanifiees}
              onChange={(e) => setDepensesPlanifiees(e.target.value)}
              className={formFieldClass}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Dépenses courantes</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={depensesCourantes}
              onChange={(e) => setDepensesCourantes(e.target.value)}
              className={formFieldClass}
            />
          </label>
        </div>
      </form>

      <section
        className={`mt-6 flex items-center justify-between rounded border border-border p-4 ${
          isPositive ? 'bg-positive-bg' : 'bg-alert-bg'
        }`}
      >
        <span className="text-section-title font-bold uppercase text-ink-muted">
          Disponible simulé
        </span>
        <span
          className={`text-page-title font-bold ${
            isPositive ? 'text-positive-text-strong' : 'text-alert-text-strong'
          }`}
        >
          {formatMontant(disponible)}
        </span>
      </section>
    </main>
  )
}

export default Simulation
