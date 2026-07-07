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
