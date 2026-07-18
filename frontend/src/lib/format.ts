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
// `tagBreadcrumb`/`sortTagsByCategoryAndName` (Tag complet, api/tags.ts) et par
// les pages qui reconstruisent une forme locale allégée depuis une autre
// réponse API (ex. Dashboard.tsx/TagTracking). `byId` doit être mémoïsé par
// l'appelant (ex. `useMemo`) plutôt que reconstruit à chaque appel — ce
// chemin est typiquement emprunté une fois par option d'un <select> de Tags,
// soit N fois par rendu.
function ancestorChain<T extends BreadcrumbNode>(node: T, byId: Map<number, T>): T[] {
  const chain: T[] = [node]
  const visited = new Set<number>([node.tag_id])
  let current = node
  while (current.parent_id !== null) {
    const parent = byId.get(current.parent_id)
    if (!parent || visited.has(parent.tag_id)) break
    chain.unshift(parent)
    visited.add(parent.tag_id)
    current = parent
  }
  return chain
}

export function breadcrumbPath<T extends BreadcrumbNode>(node: T, byId: Map<number, T>): string {
  return ancestorChain(node, byId)
    .map((t) => t.name)
    .join(' › ')
}

export function tagBreadcrumb(tag: Tag, byId: Map<number, Tag>): string {
  return breadcrumbPath(tag, byId)
}

// Tri utilisé par les listes de sélection de Tags (ajout de Tag à une
// Transaction, suggestion d'auto-tagging) : catégorie racine (niveau 1) puis
// nom du Tag, tous deux en ordre alphabétique fr ; `tag_id` en dernier
// recours pour un tri déterministe si deux catégories ou deux Tags portent
// le même nom (aucune contrainte d'unicité sur `name` côté backend). `byId`
// doit être mémoïsé par l'appelant, comme pour `breadcrumbPath`. Le nom de
// catégorie de chaque Tag est résolu une seule fois (decorate-sort-undecorate)
// plutôt que dans le comparateur, pour éviter de remonter l'arbre à chaque
// paire comparée.
export function sortTagsByCategoryAndName<T extends BreadcrumbNode>(tags: T[], byId: Map<number, T>): T[] {
  const decorated = tags.map((tag) => ({ tag, categoryName: ancestorChain(tag, byId)[0].name }))
  decorated.sort((a, b) => {
    const categoryCompare = a.categoryName.localeCompare(b.categoryName, 'fr')
    if (categoryCompare !== 0) return categoryCompare
    const nameCompare = a.tag.name.localeCompare(b.tag.name, 'fr')
    return nameCompare !== 0 ? nameCompare : a.tag.tag_id - b.tag.tag_id
  })
  return decorated.map((d) => d.tag)
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

// Simulation (page sandbox) : réplique fidèle des *formules* de
// `get_recap_couple` (backend/app/budget/service.py ~882-932), appliquées à un
// Lui/Elle fictifs saisis localement plutôt qu'à des Comptes réels — aucun
// appel API possible depuis cette page (cf. spec-budget-couple-page-simulation.md).
// Le *texte* des messages d'erreur diverge volontairement de celui du backend/
// Dashboard depuis spec-simulation-messages-virement-detailles.md (messages
// chiffrés avec proposition de résolution, propres à cette page sandbox) :
// seules les formules numériques doivent rester synchronisées manuellement.
// Noms de variables alignés sur le service Python pour faciliter cette
// resynchronisation si la formule serveur change. Les échecs de virement
// (revenus nuls/négatifs, besoin total négatif, ou virement négatif) sont
// "soft" : `virementError` est renseigné et virementLui/virementElle valent
// `null`, mais budgetChargesConvenu/resteDisponible restent calculés et affichés.
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
      virementError:
        `Virement non calculable : Revenus du Couple négatifs (${formatMontant(revenusCouple)}). ` +
        `Vérifiez les Revenus Lui (${formatMontant(arrondiCentimes(revenusLui))}) et Elle ` +
        `(${formatMontant(arrondiCentimes(revenusElle))}) saisis : au moins un des deux doit être ` +
        'corrigé pour obtenir un total positif ou nul.',
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
      virementError:
        `Virement non calculable : Revenus du Couple nuls (Lui ${formatMontant(arrondiCentimes(revenusLui))}, ` +
        `Elle ${formatMontant(arrondiCentimes(revenusElle))}). Renseignez au moins un revenu pour permettre ` +
        'le calcul.',
      resteAVivreLui: null,
      resteAVivreElle: null,
    }
  }

  const besoinTotal = arrondiCentimes(chargesCouple + soldeReference)

  // Besoin total négatif (Solde de référence très négatif, champ sans `min`) :
  // gardé *avant* le calcul par personne pour ne jamais exposer une "part
  // théorique" négative dans le message (spec-simulation-messages-virement-
  // detailles.md, Spec Change Log 2026-07-18, décision humaine).
  if (besoinTotal < 0) {
    return {
      revenusCouple,
      budgetChargesConvenu,
      resteDisponible,
      virementLui: null,
      virementElle: null,
      virementError:
        'Virement non calculable : le besoin total à répartir (Charges du Couple + Solde de référence) ' +
        `est négatif (${formatMontant(besoinTotal)}). Augmentez le Solde de référence d'au moins ` +
        `${formatMontant(arrondiCentimes(-besoinTotal))} pour repasser à un besoin total nul ou positif, ` +
        'ou vérifiez les Charges du Couple saisies.',
      resteAVivreLui: null,
      resteAVivreElle: null,
    }
  }

  const virementLuiBrut = arrondiCentimes((revenusLui / revenusCouple) * besoinTotal - chargesLui)
  const virementElleBrut = arrondiCentimes((revenusElle / revenusCouple) * besoinTotal - chargesElle)

  // Détail chiffré (charges déjà payées / part théorique / montant en trop)
  // par personne concernée, pour un message actionnable plutôt que générique
  // (demande utilisateur : "quelque chose de plus parlant avec des chiffres
  // et une proposition pour résoudre le problème"). `besoinTotal >= 0` est
  // désormais garanti par la garde ci-dessus, donc part théorique >= 0 tant
  // que les revenus individuels le sont aussi (un revenu Lui/Elle négatif
  // isolé, Revenus Couple restant positif, est un gap pré-existant hors
  // scope — cf. deferred-work.md).
  const detailsNegatifs: string[] = []
  if (virementLuiBrut < 0) {
    // `chargesLuiAffichee` arrondie une seule fois puis réutilisée pour le
    // montant affiché ET pour le calcul de la part théorique affichée :
    // évite un écart d'un centime entre les deux si `chargesLui` porte une
    // précision infra-centime (finding revue Blind Hunter). `virementLuiBrut`
    // lui-même reste calculé à partir de `chargesLui` brut (formule frozen,
    // ne pas toucher).
    const chargesLuiAffichee = arrondiCentimes(chargesLui)
    const partTheoriqueLui = arrondiCentimes(chargesLuiAffichee + virementLuiBrut)
    const tropPayeLui = arrondiCentimes(-virementLuiBrut)
    detailsNegatifs.push(
      `Lui a déjà payé ${formatMontant(chargesLuiAffichee)} de Charges pour une part théorique de ` +
        `${formatMontant(partTheoriqueLui)}, soit ${formatMontant(tropPayeLui)} de trop (réduisez ses Charges ` +
        'déjà payées de ce montant, ou augmentez le Solde de référence du Compte Commun)',
    )
  }
  if (virementElleBrut < 0) {
    const chargesElleAffichee = arrondiCentimes(chargesElle)
    const partTheoriqueElle = arrondiCentimes(chargesElleAffichee + virementElleBrut)
    const tropPayeElle = arrondiCentimes(-virementElleBrut)
    detailsNegatifs.push(
      `Elle a déjà payé ${formatMontant(chargesElleAffichee)} de Charges pour une part théorique de ` +
        `${formatMontant(partTheoriqueElle)}, soit ${formatMontant(tropPayeElle)} de trop (réduisez ses Charges ` +
        'déjà payées de ce montant, ou augmentez le Solde de référence du Compte Commun)',
    )
  }

  if (detailsNegatifs.length > 0) {
    return {
      revenusCouple,
      budgetChargesConvenu,
      resteDisponible,
      virementLui: null,
      virementElle: null,
      virementError: `Virement non calculable : ${detailsNegatifs.join(' ; ')}.`,
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
