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
