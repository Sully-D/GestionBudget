import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import {
  getDisponible,
  getRecapCouple,
  getRepartitionCommune,
  getTagSpending,
  getTagTracking,
  updateCoupleChargesPercentage,
} from '../api/budget'
import type { Disponible, RecapCoupleRead, RepartitionCommuneRead, TagSpending, TagTracking } from '../api/budget'
import { getProjection } from '../api/projections'
import type { ProjectionItem } from '../api/projections'
import { getTags } from '../api/tags'
import type { Tag } from '../api/tags'
import { getTransactions } from '../api/transactions'
import type { Transaction } from '../api/transactions'
import AccountCard from '../components/AccountCard'
import {
  breadcrumbPath,
  buildSpendingRows,
  formatDate,
  formatMontant,
  formatPourcentage,
  shiftDate,
  tagBreadcrumb,
} from '../lib/format'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink focus:border-accent focus:outline-none'

const horizons = [1, 3, 6] as const
type Horizon = (typeof horizons)[number]

const typeLabels: Record<ProjectionItem['type'], string> = {
  recurrente: 'Récurrente',
  planifiee: 'Planifiée',
}

type TagStatus = 'ok' | 'warn' | 'over'

interface TrackingTagRef {
  tag_id: number
  name: string
  parent_id: number | null
}

interface EnrichedTagRow {
  row: TagTracking
  label: string
  pctRevenus: number | null
  status: TagStatus | null
  ratio: number
}

// Seuils confirmés EXPERIENCE.md : OK < 90 %, proche (warn) 90-99 %, dépassement (over) >= 100 %.
function statusFor(ratio: number): TagStatus {
  if (ratio >= 100) return 'over'
  if (ratio >= 90) return 'warn'
  return 'ok'
}

// Pourcentage affiché arrondi à 99 max côté warn : un ratio brut dans [99.5, 100)
// (donc encore classé warn par statusFor) arrondirait sinon visuellement à "100 %",
// contradictoire avec le badge ambre (over commence strictement à 100).
function statusLabel(status: TagStatus, ratio: number): string {
  if (status === 'ok') return 'OK'
  if (status === 'warn') return `${Math.min(Math.round(ratio), 99)} %`
  return `+${Math.round(ratio - 100)} %`
}

function statusEtat(status: TagStatus, ratio: number): string {
  if (status === 'ok') return 'dans la Cible'
  if (status === 'warn') return `proche de la Cible (${Math.min(Math.round(ratio), 99)}%)`
  return `dépassement de ${Math.round(ratio - 100)}%`
}

// Pourcentage annoncé par aria-valuetext (Dev Notes Task 45) : ratio arrondi pour
// ok/warn, mais excédent (ratio − 100) pour over — distinct d'aria-valuenow, qui
// reste toujours plafonné à 100 pour la position visuelle de la barre.
function ariaValueTextPct(status: TagStatus, ratio: number): number {
  if (status === 'over') return Math.round(ratio - 100)
  return Math.min(Math.round(ratio), 99)
}

function statusBarClass(status: TagStatus): string {
  if (status === 'over') return 'bg-alert'
  if (status === 'warn') return 'bg-warn'
  return 'bg-positive'
}

function statusBadgeClass(status: TagStatus): string {
  if (status === 'over') return 'bg-alert-bg text-alert-text-strong'
  if (status === 'warn') return 'bg-warn-bg text-warn'
  return 'bg-positive-bg text-positive-text-strong'
}

// `target_amount` ne peut être 0 qu'au cas limite Revenus de la Période = 0
// (target_amount = percentage/100 × total_revenue) — garde division par zéro,
// symétrique à la garde `revenus === 0` déjà posée en Story 6.1.
// `revenus` est `null` tant que `getDisponible` n'a pas résolu (ou a échoué) :
// dans ce cas `pctRevenus` reste `null` plutôt qu'un faux "0,0 %" indistinct
// d'un revenu réellement nul.
function buildEnrichedRows(tagTracking: TagTracking[], revenus: number | null): EnrichedTagRow[] {
  const tagById = new Map<number, TrackingTagRef>(
    tagTracking.map((r) => [r.tag_id, { tag_id: r.tag_id, name: r.tag_name, parent_id: r.parent_id }]),
  )
  return tagTracking.map((row) => {
    const pctRevenus = revenus === null ? null : revenus !== 0 ? (row.spent / revenus) * 100 : 0
    const hasTarget = row.target_amount !== null
    const ratio = hasTarget && row.target_amount! > 0 ? (row.spent / row.target_amount!) * 100 : 0
    return {
      row,
      label: breadcrumbPath({ tag_id: row.tag_id, name: row.tag_name, parent_id: row.parent_id }, tagById),
      pctRevenus,
      status: hasTarget ? statusFor(ratio) : null,
      ratio,
    }
  })
}

function Dashboard() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)

  const [referenceDate, setReferenceDate] = useState<string | undefined>(undefined)

  const [disponible, setDisponible] = useState<Disponible | null>(null)
  const [disponibleLoading, setDisponibleLoading] = useState(false)
  const [disponibleError, setDisponibleError] = useState<string | null>(null)

  const [tagTracking, setTagTracking] = useState<TagTracking[]>([])
  const [tagTrackingLoading, setTagTrackingLoading] = useState(false)
  const [tagTrackingError, setTagTrackingError] = useState<string | null>(null)

  const [tagSpending, setTagSpending] = useState<TagSpending[]>([])
  const [tagSpendingLoading, setTagSpendingLoading] = useState(false)
  const [tagSpendingError, setTagSpendingError] = useState<string | null>(null)

  const [horizon, setHorizon] = useState<Horizon>(3)
  const [projectionItems, setProjectionItems] = useState<ProjectionItem[]>([])
  const [projectionLoading, setProjectionLoading] = useState(false)
  const [projectionError, setProjectionError] = useState<string | null>(null)

  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [transactionsLoading, setTransactionsLoading] = useState(false)
  const [transactionsError, setTransactionsError] = useState<string | null>(null)
  const [periodStart, setPeriodStart] = useState<string | null>(null)
  const [periodEnd, setPeriodEnd] = useState<string | null>(null)

  const [tags, setTags] = useState<Tag[]>([])
  const [tagsError, setTagsError] = useState<string | null>(null)
  const [repartitionMontant, setRepartitionMontant] = useState('')
  const [repartitionTagId, setRepartitionTagId] = useState('')
  const [repartitionResult, setRepartitionResult] = useState<RepartitionCommuneRead | null>(null)
  const [repartitionLoading, setRepartitionLoading] = useState(false)
  const [repartitionError, setRepartitionError] = useState<string | null>(null)
  // Jeton de requête (patron `cancelled` du useEffect principal, adapté à un appel
  // déclenché par bouton plutôt que par effet) : incrémenté à chaque nouveau calcul
  // et à chaque reset de Compte/Période, pour qu'une réponse en vol devenue obsolète
  // ne réaffiche jamais un résultat périmé (AC #4).
  const repartitionRequestIdRef = useRef(0)

  // Récap Budget Couple (Tableau 1 + Tableau 2, Compte Commun uniquement) — fenêtre de
  // N mois calendaires stricts indépendante de la Période budgétaire affichée (AD-2,
  // calcul entièrement serveur). `recapMonthsInput` reste une chaîne pour permettre un
  // champ vide/partiel pendant la frappe sans déclencher de fetch invalide.
  const [recapMonthsInput, setRecapMonthsInput] = useState('3')
  const recapMonthsValue = Number(recapMonthsInput)
  const recapMonthsValid =
    recapMonthsInput.trim() !== '' &&
    Number.isInteger(recapMonthsValue) &&
    recapMonthsValue >= 1 &&
    recapMonthsValue <= 120
  const [recapCouple, setRecapCouple] = useState<RecapCoupleRead | null>(null)
  const [recapCoupleLoading, setRecapCoupleLoading] = useState(false)
  const [recapCoupleError, setRecapCoupleError] = useState<string | null>(null)

  const [percentageDraft, setPercentageDraft] = useState('')
  const [percentageSubmitting, setPercentageSubmitting] = useState(false)
  const [percentageError, setPercentageError] = useState<string | null>(null)
  // Jeton de requête (même patron que `repartitionRequestIdRef`) partagé entre le
  // `useEffect` de fetch principal et le refetch manuel post-PATCH de
  // `submitCoupleChargesPercentage` : incrémenté à chaque déclenchement (changement de
  // Compte/N mois ou sauvegarde réussie), une réponse en vol devenue obsolète n'est
  // jamais appliquée.
  const recapCoupleRequestIdRef = useRef(0)
  // `account_id` du Récap lors de la dernière synchronisation de `percentageDraft` —
  // ne resynchronise que sur un changement de Compte (ou explicitement après une
  // sauvegarde réussie), jamais sur un simple refetch déclenché par un changement de
  // "N mois" pendant que l'utilisateur tape une valeur pas encore enregistrée.
  const percentageSyncedAccountIdRef = useRef<number | null>(null)

  const tagById = useMemo(() => new Map(tags.map((t) => [t.tag_id, t])), [tags])

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

  // Fetch inconditionnel dès le montage : le Dashboard n'a pas connaissance du
  // Compte sélectionné avant le premier rendu, et le calculateur (Compte Commun
  // uniquement) a besoin de la liste des Tags pour son <select>.
  useEffect(() => {
    getTags()
      .then((data) => {
        setTags(data)
        setTagsError(null)
      })
      .catch((err) => {
        setTagsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
  }, [])

  const selectedAccount = accounts.find((a) => a.account_id === selectedAccountId) ?? null

  // `referenceDate` vaut `undefined` sur la Période courante, ou une date à
  // l'intérieur d'une Période archivée (calculée par `shiftDate`) — dérivée ici une
  // seule fois pour être partagée par le `useEffect` de fetch et le calculateur de
  // répartition (bouton « Calculer »), pas dupliquée.
  const targetPeriodStart = selectedAccount ? (referenceDate ?? selectedAccount.period_start) : null

  // Changer de Compte revient toujours à sa propre Période courante, jamais à
  // une Période archivée d'un autre Compte (cf. Dev Notes §Deux sources de
  // Période distinctes). Ajustement pendant le rendu (plutôt qu'un useEffect
  // séparé) pour éviter un cycle de fetch transitoire avec l'ancienne Période
  // archivée avant que la réinitialisation ne soit prise en compte.
  const [previousAccountId, setPreviousAccountId] = useState(selectedAccountId)
  if (selectedAccountId !== previousAccountId) {
    setPreviousAccountId(selectedAccountId)
    setReferenceDate(undefined)
  }

  useEffect(() => {
    setDisponible(null)
    setDisponibleError(null)
    setTagTracking([])
    setTagTrackingError(null)
    setTagSpending([])
    setTagSpendingError(null)
    setTransactions([])
    setTransactionsError(null)
    setPeriodStart(null)
    setPeriodEnd(null)
    // Un résultat de calculateur affiché doit toujours correspondre à la Période/au
    // Compte actuellement affichés (AC #4) — jamais laissé visible après un changement
    // de Compte ou de navigation vers une autre Période via les chevrons (Story 6.3).
    // Invalide aussi tout calcul encore en vol (cf. `repartitionRequestIdRef`) pour
    // qu'une réponse tardive ne ressuscite pas un résultat de l'ancien Compte/Période.
    repartitionRequestIdRef.current += 1
    setRepartitionResult(null)
    setRepartitionError(null)

    if (!selectedAccount) return

    let cancelled = false

    // Seule requête commune aux deux types de Compte : fournit aussi
    // `period_start`/`period_end` de la Période affichée (source des chevrons).
    setTransactionsLoading(true)
    getTransactions(selectedAccount.account_id, referenceDate)
      .then((result) => {
        if (cancelled) return
        setPeriodStart(result.period_start)
        setPeriodEnd(result.period_end)
        setTransactions(result.transactions)
        setTransactionsError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setTransactionsError(err instanceof Error ? err.message : 'Erreur inattendue')
        setTransactions([])
      })
      .finally(() => {
        if (!cancelled) setTransactionsLoading(false)
      })

    if (selectedAccount.is_common) {
      setTagSpendingLoading(true)
      getTagSpending(selectedAccount.account_id, targetPeriodStart!)
        .then((data) => {
          if (!cancelled) setTagSpending(data)
        })
        .catch((err) => {
          if (!cancelled) setTagSpendingError(err instanceof Error ? err.message : 'Erreur inattendue')
        })
        .finally(() => {
          if (!cancelled) setTagSpendingLoading(false)
        })
    } else {
      setDisponibleLoading(true)
      getDisponible(selectedAccount.account_id, targetPeriodStart!)
        .then((data) => {
          if (!cancelled) setDisponible(data)
        })
        .catch((err) => {
          if (!cancelled) setDisponibleError(err instanceof Error ? err.message : 'Erreur inattendue')
        })
        .finally(() => {
          if (!cancelled) setDisponibleLoading(false)
        })

      setTagTrackingLoading(true)
      getTagTracking(selectedAccount.account_id, targetPeriodStart!)
        .then((data) => {
          if (!cancelled) setTagTracking(data)
        })
        .catch((err) => {
          if (!cancelled) setTagTrackingError(err instanceof Error ? err.message : 'Erreur inattendue')
        })
        .finally(() => {
          if (!cancelled) setTagTrackingLoading(false)
        })
    }

    return () => {
      cancelled = true
    }
  }, [selectedAccount, referenceDate, targetPeriodStart])

  // La Projection est ancrée sur `date.today()` côté serveur (jamais sur la
  // Période affichée) : ses dépendances excluent volontairement `referenceDate`
  // pour ne pas la refaire fetcher ni la faire disparaître quand on navigue vers
  // une Période archivée via les chevrons (Story 6.3).
  useEffect(() => {
    if (!selectedAccount || selectedAccount.is_common) {
      setProjectionItems([])
      setProjectionError(null)
      setProjectionLoading(false)
      return
    }

    let cancelled = false

    setProjectionLoading(true)
    getProjection(selectedAccount.account_id, horizon)
      .then((data) => {
        if (!cancelled) {
          setProjectionItems(data)
          setProjectionError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setProjectionError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (!cancelled) setProjectionLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedAccount, horizon])

  const enrichedTagRows = buildEnrichedRows(tagTracking, disponible ? disponible.revenus : null)
  const enrichedSpendingRows = buildSpendingRows(tagSpending)

  const pourcentageRevenus =
    disponible && disponible.revenus !== 0 ? (disponible.disponible / disponible.revenus) * 100 : 0

  function goToPreviousPeriod() {
    if (periodStart) setReferenceDate(shiftDate(periodStart, -1))
  }

  function goToNextPeriod() {
    if (periodEnd) setReferenceDate(shiftDate(periodEnd, 1))
  }

  // Récap Budget Couple : fenêtre de N mois calendaires stricts (indépendante de la
  // Période budgétaire affichée) — recalcul immédiat au changement de N ou de Compte
  // (AC #1), tout calcul reste serveur (AD-2).
  useEffect(() => {
    if (!selectedAccount || !selectedAccount.is_common || !recapMonthsValid) {
      recapCoupleRequestIdRef.current += 1
      setRecapCouple(null)
      setRecapCoupleError(null)
      setRecapCoupleLoading(false)
      return
    }

    const requestId = ++recapCoupleRequestIdRef.current
    setRecapCoupleLoading(true)
    getRecapCouple(selectedAccount.account_id, recapMonthsValue)
      .then((data) => {
        if (recapCoupleRequestIdRef.current !== requestId) return
        setRecapCouple(data)
        setRecapCoupleError(null)
      })
      .catch((err) => {
        if (recapCoupleRequestIdRef.current !== requestId) return
        setRecapCoupleError(err instanceof Error ? err.message : 'Erreur inattendue')
        setRecapCouple(null)
      })
      .finally(() => {
        if (recapCoupleRequestIdRef.current !== requestId) return
        setRecapCoupleLoading(false)
      })
  }, [selectedAccount, recapMonthsValid, recapMonthsValue])

  // Pré-remplissage du NB% (AC #2) : ne resynchronise `percentageDraft` que lorsque le
  // Compte du Récap affiché change (chargement initial inclus, `null` -> Compte Commun,
  // ou changement de Compte sélectionné) — jamais sur un simple refetch déclenché par un
  // changement de "N mois", qui écraserait sinon silencieusement une saisie NB% en cours
  // pas encore enregistrée. La resynchronisation post-sauvegarde est gérée explicitement
  // dans `submitCoupleChargesPercentage`.
  useEffect(() => {
    const currentAccountId = recapCouple ? recapCouple.account_id : null
    if (percentageSyncedAccountIdRef.current === currentAccountId) return
    percentageSyncedAccountIdRef.current = currentAccountId
    setPercentageDraft(
      recapCouple && recapCouple.couple_charges_percentage !== null
        ? String(recapCouple.couple_charges_percentage)
        : '',
    )
    setPercentageError(null)
  }, [recapCouple])

  // Pattern `Budget.tsx::submitTargetForm` : PATCH puis refetch (jamais de mise à jour
  // optimiste locale du Tableau 2), déclenché uniquement par « Enregistrer ». Le refetch
  // réutilise le même jeton `recapCoupleRequestIdRef` que le `useEffect` principal :
  // si l'utilisateur change de Compte ou de "N mois" pendant les deux allers-retours
  // réseau (PATCH puis GET), la réponse tardive de ce refetch manuel est ignorée.
  async function submitCoupleChargesPercentage() {
    if (!selectedAccount) return
    const value = Number(percentageDraft)
    if (percentageDraft.trim() === '' || Number.isNaN(value) || value < 0 || value > 100) {
      setPercentageError('Le pourcentage doit être compris entre 0 et 100.')
      return
    }
    if (percentageSubmitting) return
    setPercentageSubmitting(true)
    try {
      await updateCoupleChargesPercentage(selectedAccount.account_id, value)
    } catch (err) {
      setPercentageError(err instanceof Error ? err.message : 'Erreur inattendue')
      setPercentageSubmitting(false)
      return
    }
    setPercentageError(null)
    setPercentageSubmitting(false)
    if (!recapMonthsValid) return
    const requestId = ++recapCoupleRequestIdRef.current
    try {
      const data = await getRecapCouple(selectedAccount.account_id, recapMonthsValue)
      if (recapCoupleRequestIdRef.current !== requestId) return
      setRecapCouple(data)
      // Sauvegarde réussie : resynchronise explicitement le NB% affiché (formatage
      // normalisé par le serveur), même si le Compte n'a pas changé.
      percentageSyncedAccountIdRef.current = data.account_id
      setPercentageDraft(
        data.couple_charges_percentage !== null ? String(data.couple_charges_percentage) : '',
      )
    } catch (err) {
      if (recapCoupleRequestIdRef.current !== requestId) return
      setRecapCoupleError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  // Calcul non automatique (patron `submitTargetForm` de Budget.tsx) : déclenché
  // uniquement par le bouton « Calculer », jamais en réaction à une simple frappe
  // dans le montant ou un changement de Tag.
  function submitRepartition() {
    if (!targetPeriodStart || repartitionMontant === '' || repartitionTagId === '') return
    const requestId = ++repartitionRequestIdRef.current
    setRepartitionLoading(true)
    getRepartitionCommune(Number(repartitionMontant), Number(repartitionTagId), targetPeriodStart)
      .then((data) => {
        if (repartitionRequestIdRef.current !== requestId) return
        setRepartitionResult(data)
        setRepartitionError(null)
      })
      .catch((err) => {
        if (repartitionRequestIdRef.current !== requestId) return
        setRepartitionError(err instanceof Error ? err.message : 'Erreur inattendue')
        setRepartitionResult(null)
      })
      .finally(() => {
        if (repartitionRequestIdRef.current !== requestId) return
        setRepartitionLoading(false)
      })
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      {selectedAccount?.is_common && (
        <>
          <p className="rounded border border-border bg-surface-panel p-4 text-body text-ink-muted">
            Le Compte Commun n'a pas de formule Disponible.
          </p>
          {/* kpi-card Solde bordé classique — jamais le hero-stat fond sombre sur ce Compte
              (DESIGN.md § kpi-card : réutilisée seule pour le Solde du Compte Commun). */}
          <div className="mt-4 inline-block rounded border border-border bg-surface p-4">
            <p className="text-label uppercase text-ink-muted">Solde</p>
            <p className="mt-1 font-mono text-stat-value font-bold text-ink">
              {formatMontant(selectedAccount.balance)}
            </p>
          </div>

          {/* Récap Budget Couple (Tableau 1 « Récap' » + Tableau 2 « Budget Couple ») —
              Compte Commun uniquement, positionné avant le Calculateur de répartition
              (spec-recap-budget-couple-dashboard-commun.md). Concept de Reste à vivre
              distinct et indépendant de celui du Calculateur : aucune tentative
              d'unification. Calcul entièrement serveur (AD-2). */}
          <section className="mt-8">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-label uppercase text-ink-muted">Récap' Budget Couple</h2>
              <label className="flex items-center gap-2 text-body text-ink-muted">
                Sur
                <input
                  type="number"
                  min="1"
                  max="120"
                  step="1"
                  value={recapMonthsInput}
                  onChange={(e) => setRecapMonthsInput(e.target.value)}
                  aria-label="Nombre de mois du Récap"
                  className={`${formFieldClass} w-16`}
                />
                mois
              </label>
            </div>

            {!recapMonthsValid && (
              <p className="mt-2 text-body text-alert">
                Le nombre de mois doit être un entier compris entre 1 et 120.
              </p>
            )}
            {recapCoupleError && <p className="mt-2 text-body text-alert">{recapCoupleError}</p>}
            {recapCoupleLoading && !recapCouple && !recapCoupleError && (
              <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
            )}

            {recapCouple && (
              <>
                <table className="mt-4 hidden w-full lg:table">
                  <thead className="bg-surface">
                    <tr>
                      <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Compte</th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Revenus</th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Charges</th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Virements</th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">
                        Investissements
                      </th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">
                        Charges + Virements
                      </th>
                      <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">
                        Reste à vivre
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {recapCouple.rows.map((row) => (
                      <tr key={row.account_id} className="border-t border-border-subtle">
                        <td className="px-2 py-2 text-body text-ink">{row.account_name}</td>
                        <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                          {formatMontant(row.revenus)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-body text-ink-muted">
                          {formatMontant(row.charges)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-body text-ink-muted">
                          {formatMontant(row.virements)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-body text-ink-muted">
                          {formatMontant(row.investissements)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-body text-ink-muted">
                          {formatMontant(row.charges_plus_virements)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                          {formatMontant(row.reste_a_vivre)}
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t border-border bg-surface-panel">
                      <td className="px-2 py-2 text-body-strong text-ink">Couple (total)</td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                        {formatMontant(recapCouple.total_revenus)}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink-muted">
                        {formatMontant(recapCouple.total_charges)}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink-muted">
                        {formatMontant(recapCouple.total_virements)}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink-muted">
                        {formatMontant(recapCouple.total_investissements)}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink-muted">
                        {formatMontant(recapCouple.total_charges_plus_virements)}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                        {formatMontant(recapCouple.total_reste_a_vivre)}
                      </td>
                    </tr>
                  </tbody>
                </table>

                <div className="mt-4 flex flex-col gap-3 lg:hidden">
                  {recapCouple.rows.map((row) => (
                    <div key={row.account_id} className="rounded border border-border bg-surface p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-body-strong text-ink">{row.account_name}</span>
                        <span className="font-mono text-body-strong text-ink">
                          {formatMontant(row.reste_a_vivre)}
                        </span>
                      </div>
                      <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-caption text-ink-muted">
                        <span>Revenus : {formatMontant(row.revenus)}</span>
                        <span>Charges : {formatMontant(row.charges)}</span>
                        <span>Virements : {formatMontant(row.virements)}</span>
                        <span>Investissements : {formatMontant(row.investissements)}</span>
                      </div>
                    </div>
                  ))}
                  <div className="rounded border border-border bg-surface-panel p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-body-strong text-ink">Couple (total)</span>
                      <span className="font-mono text-body-strong text-ink">
                        {formatMontant(recapCouple.total_reste_a_vivre)}
                      </span>
                    </div>
                    <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-caption text-ink-muted">
                      <span>Revenus : {formatMontant(recapCouple.total_revenus)}</span>
                      <span>Charges : {formatMontant(recapCouple.total_charges)}</span>
                      <span>Virements : {formatMontant(recapCouple.total_virements)}</span>
                      <span>Investissements : {formatMontant(recapCouple.total_investissements)}</span>
                    </div>
                  </div>
                </div>

                {/* Tableau 2 « Budget Couple » — NB% persisté (colonne `accounts`), jamais
                    d'édition inline : champ + bouton « Enregistrer » (pattern
                    `Budget.tsx::submitTargetForm`), pré-rempli sans action au chargement (AC #2). */}
                <div className="mt-6 overflow-hidden rounded border border-border">
                  <div className="border-b border-border bg-surface-panel px-4 py-3">
                    <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
                      Budget Couple
                    </span>
                  </div>
                  <div className="flex flex-col gap-3 px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-body text-ink-muted">Revenus du Couple</span>
                      <span className="font-mono text-body-strong text-ink">
                        {formatMontant(recapCouple.total_revenus)}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <label htmlFor="couple-charges-percentage" className="text-body text-ink-muted">
                        Charges convenues (% des Revenus)
                      </label>
                      <input
                        id="couple-charges-percentage"
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        value={percentageDraft}
                        onChange={(e) => setPercentageDraft(e.target.value)}
                        disabled={percentageSubmitting}
                        className={formFieldClass}
                      />
                      <button
                        type="button"
                        onClick={submitCoupleChargesPercentage}
                        disabled={percentageSubmitting}
                        className="text-body-strong text-accent disabled:opacity-60"
                      >
                        Enregistrer
                      </button>
                    </div>
                    {percentageError && <p className="text-body text-alert">{percentageError}</p>}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-body text-ink-muted">Budget de charges convenu</span>
                      <span className="font-mono text-body-strong text-ink">
                        {recapCouple.budget_charges_convenu !== null
                          ? formatMontant(recapCouple.budget_charges_convenu)
                          : '—'}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-body text-ink-muted">Reste disponible</span>
                      <span className="font-mono text-body-strong text-ink">
                        {recapCouple.reste_disponible !== null
                          ? formatMontant(recapCouple.reste_disponible)
                          : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </section>

          {/* Calculateur de répartition du virement vers le Compte Commun (FR-35/FR-36,
              Story 6.6) — calcul entièrement serveur (AD-2), aucune agrégation côté client. */}
          <section className="mt-8">
            <h2 className="text-label uppercase text-ink-muted">Calculateur de répartition</h2>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="Montant total"
                aria-label="Montant total à verser"
                value={repartitionMontant}
                onChange={(e) => setRepartitionMontant(e.target.value)}
                disabled={repartitionLoading}
                className={formFieldClass}
              />
              <select
                value={repartitionTagId}
                onChange={(e) => setRepartitionTagId(e.target.value)}
                aria-label="Tag de référence pour le Reste à vivre"
                disabled={repartitionLoading}
                className={formFieldClass}
              >
                <option value="">Choisir un Tag…</option>
                {tags.map((t) => (
                  <option key={t.tag_id} value={t.tag_id}>
                    {tagBreadcrumb(t, tagById)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={submitRepartition}
                disabled={repartitionLoading || repartitionMontant === '' || repartitionTagId === ''}
                className="text-body-strong text-accent disabled:opacity-60"
              >
                Calculer
              </button>
            </div>

            {tagsError && <p className="mt-2 text-body text-alert">{tagsError}</p>}
            {repartitionError && <p className="mt-2 text-body text-alert">{repartitionError}</p>}

            {repartitionResult && (
              <div className="mt-4">
                {/* Rappel explicite du Tag/montant du résultat affiché : le calcul n'est pas
                    réactif (décision Task 4) — le formulaire peut diverger du résultat si
                    l'utilisateur change le Tag/montant sans recliquer « Calculer ». */}
                <p className="text-caption text-ink-muted">
                  Répartition de {formatMontant(repartitionResult.montant_total)} sur{' '}
                  {repartitionResult.tag_name}
                </p>
                <div className="mt-2 overflow-hidden rounded border border-border">
                  {repartitionResult.parts.map((part) => (
                    <div
                      key={part.account_id}
                      className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle px-4 py-2 first:border-t-0"
                      aria-label={`${part.account_name}, Reste à vivre ${formatMontant(part.reste_a_vivre)}, part due ${formatMontant(part.part)}`}
                    >
                      <div>
                        <p className="text-body-strong text-ink">{part.account_name}</p>
                        <p className="text-caption text-ink-muted">
                          Reste à vivre : {formatMontant(part.reste_a_vivre)}
                        </p>
                      </div>
                      <p className="font-mono text-body-strong text-ink">{formatMontant(part.part)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        </>
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

      {selectedAccount && !selectedAccount.is_common && (
        <section className="mt-8">
          <h2 className="text-label uppercase text-ink-muted">Répartition par Tag</h2>

          {tagTrackingError && <p className="mt-2 text-body text-alert">{tagTrackingError}</p>}

          {tagTrackingLoading && tagTracking.length === 0 && !tagTrackingError && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}

          {!tagTrackingLoading && !tagTrackingError && tagTracking.length === 0 && (
            <p className="mt-2 text-body text-ink-muted">Aucune dépense taguée sur cette Période.</p>
          )}

          {enrichedTagRows.length > 0 && (
            <>
              <table className="mt-4 hidden w-full lg:table">
                <thead className="bg-surface">
                  <tr>
                    <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Tag</th>
                    <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Dépensé</th>
                    <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">% Revenus</th>
                    <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Cible</th>
                    <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Projection</th>
                    <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {enrichedTagRows.map(({ row, label, pctRevenus, status, ratio }) => (
                    <tr
                      key={row.tag_id}
                      className={`border-t border-border-subtle ${status === 'over' ? 'bg-alert-bg' : ''}`}
                      aria-label={status ? `${label}, ${formatMontant(row.spent)}, ${statusEtat(status, ratio)}` : undefined}
                    >
                      <td className="px-2 py-2 text-body text-ink">{label}</td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                        {formatMontant(row.spent)}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-body text-ink-muted">
                        {pctRevenus !== null ? formatPourcentage(pctRevenus) : '—'}
                      </td>
                      <td className="px-2 py-2 text-left font-mono text-body text-ink">
                        {status ? (
                          <div className="flex items-center gap-2">
                            <span className="whitespace-nowrap">
                              {formatPourcentage(row.target_percentage ?? 0)} · {formatMontant(row.target_amount ?? 0)}
                            </span>
                            <span
                              className="h-1.5 w-16 flex-shrink-0 overflow-hidden rounded-full bg-border"
                              role="progressbar"
                              aria-valuenow={Math.round(Math.min(ratio, 100))}
                              aria-valuemin={0}
                              aria-valuemax={100}
                              aria-valuetext={`${ariaValueTextPct(status, ratio)}% de la Cible, ${statusEtat(status, ratio)}`}
                            >
                              <span
                                className={`block h-full rounded-full ${statusBarClass(status)}`}
                                style={{ width: `${Math.min(ratio, 100)}%` }}
                              />
                            </span>
                          </div>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-body text-ink-muted">
                        {row.projection !== null ? formatMontant(row.projection) : '—'}
                      </td>
                      <td className="px-2 py-2 text-right">
                        {status ? (
                          <span className={`rounded-full px-2 py-0.5 text-caption font-bold ${statusBadgeClass(status)}`}>
                            {statusLabel(status, ratio)}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="mt-4 flex flex-col gap-3 lg:hidden">
                {enrichedTagRows.map(({ row, label, pctRevenus, status, ratio }) => (
                  <div
                    key={row.tag_id}
                    className={`rounded border border-border bg-surface p-3 ${status === 'over' ? 'bg-alert-bg' : ''}`}
                    aria-label={status ? `${label}, ${formatMontant(row.spent)}, ${statusEtat(status, ratio)}` : undefined}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-body text-ink">{label}</span>
                      <span className="font-mono text-body-strong text-ink">{formatMontant(row.spent)}</span>
                    </div>
                    <div className="mt-1 text-caption text-ink-muted">
                      {pctRevenus !== null ? formatPourcentage(pctRevenus) : '—'} des Revenus
                    </div>
                    {status && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="whitespace-nowrap text-caption text-ink-muted">
                          {formatPourcentage(row.target_percentage ?? 0)} · {formatMontant(row.target_amount ?? 0)}
                        </span>
                        <span
                          className="h-1.5 flex-1 overflow-hidden rounded-full bg-border"
                          role="progressbar"
                          aria-valuenow={Math.round(Math.min(ratio, 100))}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuetext={`${ariaValueTextPct(status, ratio)}% de la Cible, ${statusEtat(status, ratio)}`}
                        >
                          <span
                            className={`block h-full rounded-full ${statusBarClass(status)}`}
                            style={{ width: `${Math.min(ratio, 100)}%` }}
                          />
                        </span>
                        <span
                          className={`flex-shrink-0 rounded-full px-2 py-0.5 text-caption font-bold ${statusBadgeClass(status)}`}
                        >
                          {statusLabel(status, ratio)}
                        </span>
                      </div>
                    )}
                    {status && row.projection !== null && (
                      <div className="mt-1 text-caption text-ink-muted">
                        Projection : {formatMontant(row.projection)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {/* Projection de trésorerie (FR-32) — Comptes personnels uniquement (même garde
          que Disponible, `get_projection` 422 sur le Compte Commun). Vue en lecture seule
          de la même donnée que /projection ; la gestion des Dépenses planifiées reste sur
          cette page dédiée. */}
      {selectedAccount && !selectedAccount.is_common && (
        <section className="mt-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-label uppercase text-ink-muted">Projection</h2>
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

          {projectionError && <p className="mt-2 text-body text-alert">{projectionError}</p>}

          {projectionLoading && projectionItems.length === 0 && !projectionError && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}

          {!projectionLoading && !projectionError && projectionItems.length === 0 && (
            <p className="mt-2 text-body text-ink-muted">Aucun élément dans cet horizon.</p>
          )}

          {projectionItems.length > 0 && (
            <div className="mt-4 overflow-hidden rounded border border-border">
              {projectionItems.map((item, index) => (
                <div
                  key={`${item.date}-${item.type}-${item.label}-${index}`}
                  className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle px-4 py-2 first:border-t-0"
                  aria-label={`${item.label}, ${formatDate(item.date)}, ${typeLabels[item.type]}${item.tag_name !== null ? `, ${item.tag_name}` : ''}, ${formatMontant(item.amount)}`}
                >
                  <div>
                    <p className="text-body-strong text-ink">{item.label}</p>
                    <p className="text-caption text-ink-muted">
                      {formatDate(item.date)} · {typeLabels[item.type]}
                      {item.tag_name !== null ? ` · ${item.tag_name}` : ''}
                    </p>
                  </div>
                  <p className="font-mono text-body-strong text-ink">{formatMontant(item.amount)}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Liste de Transactions en lecture seule, commune aux Comptes personnels et au
          Compte Commun (AC #1 et #3) — l'édition/suppression reste sur Transactions.tsx. */}
      {selectedAccount && (
        <section className="mt-8">
          <h2 className="text-label uppercase text-ink-muted">Transactions</h2>

          {transactionsError && <p className="mt-2 text-body text-alert">{transactionsError}</p>}

          {transactionsLoading && transactions.length === 0 && !transactionsError && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}

          {!transactionsLoading && !transactionsError && transactions.length === 0 && (
            <p className="mt-2 text-body text-ink-muted">Aucune Transaction sur cette Période.</p>
          )}

          {transactions.length > 0 && (
            <>
              <table className="mt-4 hidden w-full lg:table">
                <thead className="bg-surface">
                  <tr>
                    <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Date</th>
                    <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Libellé</th>
                    <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Tiers</th>
                    <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Tags</th>
                    <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Montant</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => {
                    // Virements reçus (AC #3) identifiés par couleur sur le Compte Commun
                    // uniquement — aucune donnée d'« Origine » n'existe sur `Transaction`.
                    const isReceivedTransfer = selectedAccount.is_common && transaction.amount > 0
                    return (
                      <tr key={transaction.transaction_id} className="border-t border-border-subtle">
                        <td className="px-2 py-2 text-body text-ink">{formatDate(transaction.date)}</td>
                        <td className="px-2 py-2 text-body text-ink">{transaction.label}</td>
                        <td className="px-2 py-2 text-body text-ink-muted">{transaction.payee ?? ''}</td>
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
                        <td
                          className={`px-2 py-2 text-right font-mono text-body-strong ${
                            isReceivedTransfer ? 'text-positive-text-strong' : 'text-ink'
                          }`}
                        >
                          {formatMontant(transaction.amount)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              <div className="mt-4 flex flex-col gap-3 lg:hidden">
                {transactions.map((transaction) => {
                  const isReceivedTransfer = selectedAccount.is_common && transaction.amount > 0
                  return (
                    <div key={transaction.transaction_id} className="rounded border border-border bg-surface p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-body text-ink">{transaction.label}</span>
                        <span
                          className={`font-mono text-body-strong ${
                            isReceivedTransfer ? 'text-positive-text-strong' : 'text-ink'
                          }`}
                        >
                          {formatMontant(transaction.amount)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center justify-between">
                        <span className="text-caption text-ink-muted">{formatDate(transaction.date)}</span>
                        <span className="text-caption text-ink-muted">{transaction.payee ?? ''}</span>
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
                  )
                })}
              </div>
            </>
          )}
        </section>
      )}

      {/* Répartition par Tag sans Cible (AC #3) — Compte Commun uniquement, forme de
          données distincte de `TagTracking` (pas de Cible/statut/progress-bar). */}
      {selectedAccount?.is_common && (
        <section className="mt-8">
          <h2 className="text-label uppercase text-ink-muted">Répartition par Tag</h2>

          {tagSpendingError && <p className="mt-2 text-body text-alert">{tagSpendingError}</p>}

          {tagSpendingLoading && tagSpending.length === 0 && !tagSpendingError && (
            <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
          )}

          {!tagSpendingLoading && !tagSpendingError && tagSpending.length === 0 && (
            <p className="mt-2 text-body text-ink-muted">Aucune dépense taguée sur cette Période.</p>
          )}

          {enrichedSpendingRows.length > 0 && (
            <>
              <table className="mt-4 hidden w-full lg:table">
                <thead className="bg-surface">
                  <tr>
                    <th className="px-2 py-2 text-left text-table-header uppercase text-ink-muted">Tag</th>
                    <th className="px-2 py-2 text-right text-table-header uppercase text-ink-muted">Dépensé</th>
                  </tr>
                </thead>
                <tbody>
                  {enrichedSpendingRows.map(({ row, label }) => (
                    <tr key={row.tag_id} className="border-t border-border-subtle">
                      <td className="px-2 py-2 text-body text-ink">{label}</td>
                      <td className="px-2 py-2 text-right font-mono text-body-strong text-ink">
                        {formatMontant(row.spent)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="mt-4 flex flex-col gap-3 lg:hidden">
                {enrichedSpendingRows.map(({ row, label }) => (
                  <div
                    key={row.tag_id}
                    className="flex items-center justify-between rounded border border-border bg-surface p-3"
                  >
                    <span className="text-body text-ink">{label}</span>
                    <span className="font-mono text-body-strong text-ink">{formatMontant(row.spent)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {accountsError && <p className="mt-4 text-body text-alert">{accountsError}</p>}

      {/* Navigation par Période (FR-29) — locale au Dashboard, jamais au-dessus du
          hero-stat (AC #1 de la Story 6.1, toujours en vigueur). Masquée tant
          qu'aucun Compte n'est sélectionné (rien à naviguer). */}
      {selectedAccount && (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={goToPreviousPeriod}
            aria-label="Période précédente"
            className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
          >
            ‹
          </button>
          <span className="text-body text-ink">
            {periodStart && periodEnd ? `${formatDate(periodStart)} – ${formatDate(periodEnd)}` : ''}
          </span>
          <button
            type="button"
            onClick={goToNextPeriod}
            aria-label="Période suivante"
            className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
          >
            ›
          </button>
          <button
            type="button"
            onClick={() => setReferenceDate(undefined)}
            disabled={referenceDate === undefined}
            className="rounded border border-border px-3 py-1 text-body text-accent disabled:cursor-not-allowed disabled:text-ink-muted disabled:opacity-60"
          >
            Période en cours
          </button>
          <Link to="/comparaison" className="rounded border border-border px-3 py-1 text-body text-accent">
            Comparer
          </Link>
        </div>
      )}

      <div className="mt-3 flex flex-col gap-3">
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
