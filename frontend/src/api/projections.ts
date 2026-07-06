import { unwrap } from './http'

export type Periodicity = 'hebdomadaire' | 'mensuelle' | 'trimestrielle' | 'annuelle'

export interface RecurringCandidate {
  signature: string
  label: string
  amount: number
  periodicity: Periodicity
  occurrence_count: number
  suggested_tag_id: number | null
  suggested_tag_name: string | null
}

export interface RecurringTransaction {
  recurring_id: number
  account_id: number
  tag_id: number | null
  label: string
  amount: number
  periodicity: Periodicity
  status: 'confirmed' | 'rejected'
}

export interface RecurringConfirmPayload {
  account_id: number
  signature: string
  label: string
  amount: number
  periodicity: Periodicity
  tag_id?: number | null
}

export interface RecurringRejectPayload {
  account_id: number
  signature: string
  label: string
  amount: number
  periodicity: Periodicity
}

export interface RecurringUpdatePayload {
  amount: number
  periodicity: Periodicity
  tag_id?: number | null
}

export async function getRecurringCandidates(
  accountId: number,
  tolerancePercentage = 10,
): Promise<RecurringCandidate[]> {
  const params = new URLSearchParams({
    account_id: String(accountId),
    tolerance_percentage: String(tolerancePercentage),
  })
  const response = await fetch(`/recurring/candidates?${params.toString()}`)
  return unwrap<RecurringCandidate[]>(response)
}

export async function confirmRecurring(
  payload: RecurringConfirmPayload,
): Promise<RecurringTransaction> {
  const response = await fetch('/recurring/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<RecurringTransaction>(response)
}

export async function rejectRecurring(
  payload: RecurringRejectPayload,
): Promise<RecurringTransaction> {
  const response = await fetch('/recurring/reject', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<RecurringTransaction>(response)
}

export async function getRecurringTransactions(
  accountId: number,
  status?: 'confirmed' | 'rejected',
): Promise<RecurringTransaction[]> {
  const params = new URLSearchParams({ account_id: String(accountId) })
  if (status) params.set('status', status)
  const response = await fetch(`/recurring?${params.toString()}`)
  return unwrap<RecurringTransaction[]>(response)
}

export async function updateRecurring(
  recurringId: number,
  payload: RecurringUpdatePayload,
): Promise<RecurringTransaction> {
  const response = await fetch(`/recurring/${recurringId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<RecurringTransaction>(response)
}

export async function deleteRecurring(recurringId: number): Promise<void> {
  const response = await fetch(`/recurring/${recurringId}`, { method: 'DELETE' })
  await unwrap<null>(response)
}

export interface PlannedExpense {
  expense_id: number
  account_id: number
  tag_id: number
  series_id: string | null
  period_index: number | null
  total_periods: number | null
  amount: number
  date: string
  description: string
}

export interface PlannedExpenseSimplePayload {
  account_id: number
  tag_id: number
  date: string
  amount: number
  description: string
}

export interface PlannedExpenseSplitPayload {
  account_id: number
  tag_id: number
  start_date: string
  total_amount: number
  total_periods: number
  description: string
}

export interface PlannedExpenseUpdatePayload {
  date: string
  amount: number
  tag_id: number
  description: string
}

export type ProjectionItemType = 'recurrente' | 'planifiee'

export interface ProjectionItem {
  date: string
  type: ProjectionItemType
  label: string
  amount: number
  tag_id: number | null
  tag_name: string | null
}

export async function createPlannedExpense(
  payload: PlannedExpenseSimplePayload,
): Promise<PlannedExpense> {
  const response = await fetch('/planned-expenses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<PlannedExpense>(response)
}

export async function createPlannedExpenseSplit(
  payload: PlannedExpenseSplitPayload,
): Promise<PlannedExpense[]> {
  const response = await fetch('/planned-expenses/split', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<PlannedExpense[]>(response)
}

export async function getPlannedExpenses(accountId: number): Promise<PlannedExpense[]> {
  const params = new URLSearchParams({ account_id: String(accountId) })
  const response = await fetch(`/planned-expenses?${params.toString()}`)
  return unwrap<PlannedExpense[]>(response)
}

export async function updatePlannedExpense(
  expenseId: number,
  payload: PlannedExpenseUpdatePayload,
): Promise<PlannedExpense> {
  const response = await fetch(`/planned-expenses/${expenseId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<PlannedExpense>(response)
}

export async function deletePlannedExpense(expenseId: number): Promise<void> {
  const response = await fetch(`/planned-expenses/${expenseId}`, { method: 'DELETE' })
  await unwrap<null>(response)
}

export async function getProjection(
  accountId: number,
  horizonMonths: 1 | 3 | 6 = 3,
): Promise<ProjectionItem[]> {
  const params = new URLSearchParams({
    account_id: String(accountId),
    horizon_months: String(horizonMonths),
  })
  const response = await fetch(`/projection?${params.toString()}`)
  return unwrap<ProjectionItem[]>(response)
}
