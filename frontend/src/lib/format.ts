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
