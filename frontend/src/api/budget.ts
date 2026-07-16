import { unwrap } from './http'

export interface Revenue {
  revenue_id: number
  account_id: number
  period_start: string | null
  kind: 'salaire' | 'ponctuel'
  amount: number
  description: string | null
}

export interface RevenuePeriodSummary {
  account_id: number
  period_start: string
  reference_amount: number | null
  effective_salary: number
  has_correction: boolean
  one_off: Revenue[]
  total: number
}

export interface RevenueSalaireUpsertPayload {
  account_id: number
  period_start: string | null
  amount: number
}

export interface RevenueOneOffCreatePayload {
  account_id: number
  period_start: string
  amount: number
  description: string
}

export async function upsertSalaire(payload: RevenueSalaireUpsertPayload): Promise<Revenue> {
  const response = await fetch('/revenues/salaire', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Revenue>(response)
}

export async function deleteSalaireCorrection(accountId: number, periodStart: string): Promise<void> {
  const params = new URLSearchParams({ account_id: String(accountId), period_start: periodStart })
  const response = await fetch(`/revenues/salaire?${params.toString()}`, { method: 'DELETE' })
  await unwrap<null>(response)
}

export async function addOneOff(payload: RevenueOneOffCreatePayload): Promise<Revenue> {
  const response = await fetch('/revenues/one-off', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Revenue>(response)
}

export async function deleteOneOff(revenueId: number): Promise<void> {
  const response = await fetch(`/revenues/one-off/${revenueId}`, { method: 'DELETE' })
  await unwrap<null>(response)
}

export async function getPeriodSummary(
  accountId: number,
  periodStart: string,
): Promise<RevenuePeriodSummary> {
  const params = new URLSearchParams({ account_id: String(accountId), period_start: periodStart })
  const response = await fetch(`/revenues/period?${params.toString()}`)
  return unwrap<RevenuePeriodSummary>(response)
}

export interface BudgetTarget {
  target_id: number
  account_id: number
  tag_id: number
  percentage: number
}

export interface BudgetTargetUpsertPayload {
  account_id: number
  tag_id: number
  percentage: number
}

export async function getBudgetTargets(accountId: number): Promise<BudgetTarget[]> {
  const params = new URLSearchParams({ account_id: String(accountId) })
  const response = await fetch(`/budget-targets?${params.toString()}`)
  return unwrap<BudgetTarget[]>(response)
}

export async function upsertBudgetTarget(payload: BudgetTargetUpsertPayload): Promise<BudgetTarget> {
  const response = await fetch('/budget-targets', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<BudgetTarget>(response)
}

export async function deleteBudgetTarget(targetId: number): Promise<void> {
  const response = await fetch(`/budget-targets/${targetId}`, { method: 'DELETE' })
  await unwrap<null>(response)
}

export interface Disponible {
  account_id: number
  period_start: string
  period_end: string
  revenus: number
  charges_recurrentes: number
  depenses_planifiees: number
  depenses_courantes: number
  disponible: number
}

export async function getDisponible(accountId: number, periodStart: string): Promise<Disponible> {
  const params = new URLSearchParams({ account_id: String(accountId), period_start: periodStart })
  const response = await fetch(`/disponible?${params.toString()}`)
  return unwrap<Disponible>(response)
}

export interface TagTracking {
  tag_id: number
  tag_name: string
  parent_id: number | null
  level: number
  spent: number
  target_percentage: number | null
  target_amount: number | null
  gap: number | null
  projection: number | null
}

export async function getTagTracking(accountId: number, periodStart: string): Promise<TagTracking[]> {
  const params = new URLSearchParams({ account_id: String(accountId), period_start: periodStart })
  const response = await fetch(`/tag-tracking?${params.toString()}`)
  return unwrap<TagTracking[]>(response)
}

export interface TagSpending {
  tag_id: number
  tag_name: string
  parent_id: number | null
  level: number
  spent: number
}

export async function getTagSpending(accountId: number, periodStart: string): Promise<TagSpending[]> {
  const params = new URLSearchParams({ account_id: String(accountId), period_start: periodStart })
  const response = await fetch(`/tag-spending?${params.toString()}`)
  return unwrap<TagSpending[]>(response)
}

export interface RepartitionCommuneAccountPart {
  account_id: number
  account_name: string
  period_start: string
  period_end: string
  revenus: number
  charges: number
  reste_a_vivre: number
  part: number
}

export interface RepartitionCommuneRead {
  tag_id: number
  tag_name: string
  montant_total: number
  parts: RepartitionCommuneAccountPart[]
}

export async function getRepartitionCommune(
  montantTotal: number,
  tagId: number,
  periodStart: string,
): Promise<RepartitionCommuneRead> {
  const params = new URLSearchParams({
    montant_total: String(montantTotal),
    tag_id: String(tagId),
    period_start: periodStart,
  })
  const response = await fetch(`/repartition-commune?${params.toString()}`)
  return unwrap<RepartitionCommuneRead>(response)
}

export interface RecapCoupleAccountRow {
  account_id: number
  account_name: string
  revenus: number
  charges: number
  virements: number
  investissements: number
  charges_plus_virements: number
  reste_a_vivre: number
  virement: number | null
}

export interface RecapCoupleRead {
  account_id: number
  months: number
  period_start: string
  period_end: string
  rows: RecapCoupleAccountRow[]
  total_revenus: number
  total_charges: number
  total_virements: number
  total_investissements: number
  total_charges_plus_virements: number
  total_reste_a_vivre: number
  couple_charges_percentage: number | null
  budget_charges_convenu: number | null
  reste_disponible: number | null
  virement_error: string | null
}

export async function getRecapCouple(accountId: number, months: number): Promise<RecapCoupleRead> {
  const params = new URLSearchParams({ account_id: String(accountId), months: String(months) })
  const response = await fetch(`/budget/recap-couple?${params.toString()}`)
  return unwrap<RecapCoupleRead>(response)
}

export interface CoupleChargesPercentageRead {
  account_id: number
  couple_charges_percentage: number | null
}

export async function updateCoupleChargesPercentage(
  accountId: number,
  percentage: number,
): Promise<CoupleChargesPercentageRead> {
  const response = await fetch('/budget/couple-charges-percentage', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account_id: accountId, percentage }),
  })
  return unwrap<CoupleChargesPercentageRead>(response)
}
