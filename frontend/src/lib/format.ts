import type { TagSpending } from '../api/budget'
import type { RuleConditionType } from '../api/rules'
import type { Tag } from '../api/tags'

// fr-FR/EUR en dur : choix délibéré, l'application cible un seul foyer
// mono-devise (pas de paramètre de locale/devise prévu au PRD).
export function formatMontant(value: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

// `value` est déjà exprimée en 0-100 (pas une fraction 0-1) : pas de style
// `percent` natif d'Intl ici, un simple NumberFormat décimal + suffixe " %".
export function formatPourcentage(value: number): string {
  return `${new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value)} %`
}

export const conditionLabels: Record<RuleConditionType, string> = {
  label_contains: 'Libellé contient',
  payee_exact: 'Tiers =',
}

interface BreadcrumbNode {
  tag_id: number
  name: string
  parent_id: number | null
}

// Générique sur toute forme exposant {tag_id, name, parent_id} : partagé par
// `tagBreadcrumb` (Tag complet, api/tags.ts) et par les pages qui reconstruisent
// une forme locale allégée depuis une autre réponse API (ex. Dashboard.tsx/TagTracking).
// `byId` doit être mémoïsé par l'appelant (ex. `useMemo`) plutôt que reconstruit
// à chaque appel — cette fonction est typiquement invoquée une fois par option
// d'un <select> de Tags, soit N fois par rendu.
export function breadcrumbPath<T extends BreadcrumbNode>(node: T, byId: Map<number, T>): string {
  const parts: string[] = [node.name]
  const visited = new Set<number>([node.tag_id])
  let current = node
  while (current.parent_id !== null) {
    const parent = byId.get(current.parent_id)
    if (!parent || visited.has(parent.tag_id)) break
    parts.unshift(parent.name)
    visited.add(parent.tag_id)
    current = parent
  }
  return parts.join(' › ')
}

export function tagBreadcrumb(tag: Tag, byId: Map<number, Tag>): string {
  return breadcrumbPath(tag, byId)
}

// Renvoie `tagId` s'il désigne encore un Tag présent dans `byId`, sinon `null`.
// Partagé par Recurrentes.tsx/Projection.tsx pour détecter au démarrage d'une
// édition qu'un Tag référencé a été supprimé entretemps, plutôt que de laisser
// le <select> retomber silencieusement sur une autre option.
export function existingTagId(tagId: number | null, byId: Map<number, unknown>): number | null {
  return tagId !== null && byId.has(tagId) ? tagId : null
}

// Simulation (page sandbox) : mêmes termes que la formule officielle du
// Disponible (AD-9) mais appliquée à des valeurs fictives saisies par
// l'utilisateur, jamais aux entités réelles (aucun appel API/backend).
export function calculerDisponibleSimule(
  revenus: number,
  charges: number,
  depensesPlanifiees: number,
  depensesCourantes: number,
): number {
  const disponible = revenus - charges - depensesPlanifiees - depensesCourantes
  // Normalise -0 en 0 : sinon un résultat nul s'affiche "-0,00 €" dans l'encart positif.
  return disponible === 0 ? 0 : disponible
}

export interface BudgetCoupleSimule {
  revenusCouple: number
  budgetChargesConvenu: number
  resteDisponible: number
  virementLui: number | null
  virementElle: number | null
  virementError: string | null
  resteAVivreLui: number | null
  resteAVivreElle: number | null
}

// Arrondit au centime (même règle que le `Decimal.quantize(..., ROUND_HALF_UP)`
// de get_recap_couple) avant toute comparaison à zéro : sans cet arrondi, un
// résultat mathématiquement nul (ex. virement=0€ à partir d'entrées à 2
// décimales) peut atterrir sur un résidu flottant du type -0.0004 et déclencher
// à tort virementError. Normalise aussi -0 (s'afficherait "-0,00 €"/"-0,00 %").
function arrondiCentimes(value: number): number {
  const rounded = Math.round(value * 100) / 100
  return rounded === 0 ? 0 : rounded
}

// Simulation (page sandbox) : réplique fidèle des formules de
// `get_recap_couple` (backend/app/budget/service.py ~882-932), appliquées à un
// Lui/Elle fictifs saisis localement plutôt qu'à des Comptes réels — aucun
// appel API possible depuis cette page (cf. spec-budget-couple-page-simulation.md).
// Noms de variables alignés sur le service Python pour faciliter une
// resynchronisation manuelle si la formule serveur change. Les échecs de
// virement (revenus nuls/négatifs, ou virement négatif) sont "soft" :
// `virementError` est renseigné et virementLui/virementElle valent `null`,
// mais budgetChargesConvenu/resteDisponible restent calculés et affichés.
export function calculerBudgetCoupleSimule(
  revenusLui: number,
  revenusElle: number,
  chargesLui: number,
  chargesElle: number,
  soldeReference: number,
  pourcentage: number,
): BudgetCoupleSimule {
  const revenusCouple = arrondiCentimes(revenusLui + revenusElle)
  const chargesCouple = arrondiCentimes(chargesLui + chargesElle)
  const budgetChargesConvenu = arrondiCentimes((pourcentage / 100) * revenusCouple)
  const resteDisponible = arrondiCentimes(revenusCouple - budgetChargesConvenu)

  // Revenus négatifs (ex. un champ saisi en négatif) traités séparément des
  // Revenus nuls (spec-budget-couple-page-simulation.md, Ask First : cas
  // explicitement nommé, résolu par décision humaine avec un message dédié).
  if (revenusCouple < 0) {
    return {
      revenusCouple,
      budgetChargesConvenu,
      resteDisponible,
      virementLui: null,
      virementElle: null,
      virementError: 'Virement non calculable : Revenus du Couple négatifs.',
      resteAVivreLui: null,
      resteAVivreElle: null,
    }
  }

  if (revenusCouple === 0) {
    return {
      revenusCouple,
      budgetChargesConvenu,
      resteDisponible,
      virementLui: null,
      virementElle: null,
      virementError: 'Virement non calculable : aucun revenu constaté.',
      resteAVivreLui: null,
      resteAVivreElle: null,
    }
  }

  const besoinTotal = arrondiCentimes(chargesCouple + soldeReference)
  const virementLuiBrut = arrondiCentimes((revenusLui / revenusCouple) * besoinTotal - chargesLui)
  const virementElleBrut = arrondiCentimes((revenusElle / revenusCouple) * besoinTotal - chargesElle)

  const negatifs: string[] = []
  if (virementLuiBrut < 0) negatifs.push('Lui')
  if (virementElleBrut < 0) negatifs.push('Elle')

  if (negatifs.length > 0) {
    return {
      revenusCouple,
      budgetChargesConvenu,
      resteDisponible,
      virementLui: null,
      virementElle: null,
      virementError: `Virement non calculable : ${negatifs.join(', ')} a/ont déjà payé plus que sa/leur part théorique.`,
      resteAVivreLui: null,
      resteAVivreElle: null,
    }
  }

  return {
    revenusCouple,
    budgetChargesConvenu,
    resteDisponible,
    virementLui: virementLuiBrut,
    virementElle: virementElleBrut,
    virementError: null,
    // Reste à vivre = Revenus − Charges déjà payées − Virement vers le Commun :
    // même concept que reste_a_vivre du Tableau 1 (Dashboard), mais appliqué
    // ici à Lui/Elle plutôt qu'à un Compte réel. Non calculable dès que le
    // Virement ne l'est pas (mêmes cas d'erreur ci-dessus).
    resteAVivreLui: arrondiCentimes(revenusLui - chargesLui - virementLuiBrut),
    resteAVivreElle: arrondiCentimes(revenusElle - chargesElle - virementElleBrut),
  }
}

export function formatDate(value: string): string {
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

export function shiftDate(value: string, days: number): string {
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  date.setDate(date.getDate() + days)
  const shiftedYear = date.getFullYear()
  const shiftedMonth = String(date.getMonth() + 1).padStart(2, '0')
  const shiftedDay = String(date.getDate()).padStart(2, '0')
  return `${shiftedYear}-${shiftedMonth}-${shiftedDay}`
}

export interface EnrichedSpendingRow {
  row: TagSpending
  label: string
}

// Répartition par Tag sans Cible (`TagSpending`, jamais `TagTracking`) : reconstruit
// le breadcrumb depuis une map locale tag_id -> {name, parent_id}. Partagée par
// Dashboard.tsx (Compte Commun) et Comparaison.tsx (les deux colonnes) — 3e/4e
// occurrence de ce calcul, extraite ici plutôt que redupliquée (Story 6.3 [Review][Defer]).
export function buildSpendingRows(tagSpending: TagSpending[]): EnrichedSpendingRow[] {
  const tagById = new Map<number, { tag_id: number; name: string; parent_id: number | null }>(
    tagSpending.map((r) => [r.tag_id, { tag_id: r.tag_id, name: r.tag_name, parent_id: r.parent_id }]),
  )
  return tagSpending.map((row) => ({
    row,
    label: breadcrumbPath({ tag_id: row.tag_id, name: row.tag_name, parent_id: row.parent_id }, tagById),
  }))
}
