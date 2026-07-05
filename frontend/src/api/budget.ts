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
