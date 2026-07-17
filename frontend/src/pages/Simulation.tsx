import { useState } from 'react'
import { calculerBudgetCoupleSimule, calculerDisponibleSimule, formatMontant } from '../lib/format'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_rgba(37,99,235,0.12)]'

const DEFAULT_REVENUS = 3000
const DEFAULT_CHARGES = 1200
const DEFAULT_DEPENSES_PLANIFIEES = 400
const DEFAULT_DEPENSES_COURANTES = 700

// Valeurs par défaut choisies pour que le scénario initial du bloc Budget
// Couple soit cohérent sans message d'erreur (AC #2) : Charges Lui/Elle dans
// le même ratio que Revenus Lui/Elle (3:2) => Virement Lui/Elle = 0 avec un
// Solde de référence à 0, jamais de virement négatif au chargement.
const DEFAULT_REVENUS_LUI = 1800
const DEFAULT_REVENUS_ELLE = 1200
const DEFAULT_CHARGES_LUI = 300
const DEFAULT_CHARGES_ELLE = 200
const DEFAULT_SOLDE_REFERENCE = 0

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

  const [revenusLuiCouple, setRevenusLuiCouple] = useState(String(DEFAULT_REVENUS_LUI))
  const [revenusElleCouple, setRevenusElleCouple] = useState(String(DEFAULT_REVENUS_ELLE))
  const [chargesLuiCouple, setChargesLuiCouple] = useState(String(DEFAULT_CHARGES_LUI))
  const [chargesElleCouple, setChargesElleCouple] = useState(String(DEFAULT_CHARGES_ELLE))
  const [soldeReferenceCouple, setSoldeReferenceCouple] = useState(String(DEFAULT_SOLDE_REFERENCE))
  // Vide par défaut (pas de "0" pré-rempli) : traité comme 0 % par le pattern
  // de parsing existant, aucun état "non défini"/tiret (spec-budget-couple-
  // page-simulation.md, Always).
  const [pourcentageChargesConvenues, setPourcentageChargesConvenues] = useState('')

  const budgetCouple = calculerBudgetCoupleSimule(
    Number(revenusLuiCouple.replace(',', '.')) || 0,
    Number(revenusElleCouple.replace(',', '.')) || 0,
    Number(chargesLuiCouple.replace(',', '.')) || 0,
    Number(chargesElleCouple.replace(',', '.')) || 0,
    Number(soldeReferenceCouple.replace(',', '.')) || 0,
    Number(pourcentageChargesConvenues.replace(',', '.')) || 0,
  )

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

      {/* Budget Couple (sandbox) — calqué visuellement sur le Tableau 2 du
          Dashboard Compte Commun (Dashboard.tsx ~647-723,
          spec-recap-budget-couple-dashboard-commun.md), mais alimenté par des
          champs Lui/Elle fictifs saisis localement et calculé intégralement
          côté client via calculerBudgetCoupleSimule : pas de Tableau 1
          "Récap'", pas d'appel API, pas de bouton "Enregistrer" — cohérent
          avec le mode sandbox (spec-budget-couple-page-simulation.md).
          Composant délibérément non partagé avec Dashboard.tsx (modèles de
          données différents : Comptes réels fetchés serveur vs saisie
          Lui/Elle locale). */}
      <form
        onSubmit={(e) => e.preventDefault()}
        className="mt-6 flex flex-col gap-4 rounded border border-border bg-surface p-4"
      >
        <h2 className="text-section-title font-bold uppercase text-ink-muted">
          Scénario Budget Couple
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-1 lg:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Revenus Lui</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={revenusLuiCouple}
              onChange={(e) => setRevenusLuiCouple(e.target.value)}
              className={formFieldClass}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Revenus Elle</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={revenusElleCouple}
              onChange={(e) => setRevenusElleCouple(e.target.value)}
              className={formFieldClass}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Charges déjà payées Lui</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={chargesLuiCouple}
              onChange={(e) => setChargesLuiCouple(e.target.value)}
              className={formFieldClass}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Charges déjà payées Elle</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={chargesElleCouple}
              onChange={(e) => setChargesElleCouple(e.target.value)}
              className={formFieldClass}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Solde de référence</span>
            {/* Pas de `min="0"` (contrairement aux autres champs de ce bloc) :
                mirroir de `reference_balance` sur le vrai Compte Commun, qui
                peut légitimement être négatif (objectif de solde non atteint). */}
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              value={soldeReferenceCouple}
              onChange={(e) => setSoldeReferenceCouple(e.target.value)}
              className={formFieldClass}
            />
          </label>
        </div>
      </form>

      <div className="mt-4 overflow-hidden rounded border border-border">
        <div className="border-b border-border bg-surface-panel px-4 py-3">
          <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
            Budget Couple
          </span>
        </div>
        <div className="flex flex-col gap-3 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-body text-ink-muted">Revenus du Couple</span>
            <span className="font-mono text-body-strong text-ink">
              {formatMontant(budgetCouple.revenusCouple)}
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <label
              htmlFor="budget-couple-simule-pourcentage"
              className="text-body text-ink-muted"
            >
              Charges convenues (% des Revenus)
            </label>
            <input
              id="budget-couple-simule-pourcentage"
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              max="100"
              value={pourcentageChargesConvenues}
              onChange={(e) => setPourcentageChargesConvenues(e.target.value)}
              className={`${formFieldClass} w-24 text-right`}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-body text-ink-muted">Budget de charges convenu</span>
            <span className="font-mono text-body-strong text-ink">
              {formatMontant(budgetCouple.budgetChargesConvenu)}
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-body text-ink-muted">Reste disponible</span>
            <span className="font-mono text-body-strong text-ink">
              {formatMontant(budgetCouple.resteDisponible)}
            </span>
          </div>

          {/* Virement Lui/Elle — calcul dérivé automatique, jamais de bouton.
              Échec "soft" (virementError) : message explicite à la place des
              deux lignes de virement, le reste du bloc reste affiché normalement
              (même logique que Dashboard.tsx Tableau 2). */}
          {budgetCouple.virementError ? (
            <p className="text-body text-alert">{budgetCouple.virementError}</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-body text-ink-muted">Virement Lui</span>
                <span className="font-mono text-body-strong text-ink">
                  {formatMontant(budgetCouple.virementLui ?? 0)}
                </span>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-body text-ink-muted">Virement Elle</span>
                <span className="font-mono text-body-strong text-ink">
                  {formatMontant(budgetCouple.virementElle ?? 0)}
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  )
}

export default Simulation
