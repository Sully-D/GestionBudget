import { unwrap } from './http'

export interface TagSummary {
  tag_id: number
  name: string
}

export interface Transaction {
  transaction_id: number
  account_id: number
  date: string
  amount: number
  label: string
  payee: string | null
  tags: TagSummary[]
}

export interface TransactionCreatePayload {
  account_id: number
  date: string
  amount: number
  label: string
  payee?: string
}

export interface TransactionUpdatePayload {
  date: string
  amount: number
  label: string
  payee?: string
}

export interface TransactionsList {
  period_start: string | null
  period_end: string | null
  filtered: boolean
  transactions: Transaction[]
}

export async function getTransactions(
  accountId: number,
  referenceDate?: string,
): Promise<TransactionsList> {
  const params = new URLSearchParams({ account_id: String(accountId) })
  if (referenceDate) {
    params.set('reference_date', referenceDate)
  }
  const response = await fetch(`/transactions?${params.toString()}`)
  return unwrap<TransactionsList>(response)
}

export interface TransactionSearchFilters {
  label?: string
  payee?: string
  amount?: number
  amountMin?: number
  amountMax?: number
  dateExact?: string
  dateFrom?: string
  dateTo?: string
  tagIds?: number[]
}

export async function searchTransactions(
  accountId: number,
  filters: TransactionSearchFilters,
): Promise<TransactionsList> {
  const params = new URLSearchParams({ account_id: String(accountId) })
  if (filters.label) params.set('label', filters.label)
  if (filters.payee) params.set('payee', filters.payee)
  if (filters.amount !== undefined) params.set('amount', String(filters.amount))
  if (filters.amountMin !== undefined) params.set('amount_min', String(filters.amountMin))
  if (filters.amountMax !== undefined) params.set('amount_max', String(filters.amountMax))
  if (filters.dateExact) params.set('date_exact', filters.dateExact)
  if (filters.dateFrom) params.set('date_from', filters.dateFrom)
  if (filters.dateTo) params.set('date_to', filters.dateTo)
  for (const tagId of filters.tagIds ?? []) {
    params.append('tag_id', String(tagId))
  }
  const response = await fetch(`/transactions?${params.toString()}`)
  return unwrap<TransactionsList>(response)
}

export async function createTransaction(
  payload: TransactionCreatePayload,
): Promise<Transaction> {
  const response = await fetch('/transactions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Transaction>(response)
}

export async function getTransaction(transactionId: number): Promise<Transaction> {
  const response = await fetch(`/transactions/${transactionId}`)
  return unwrap<Transaction>(response)
}

export async function updateTransaction(
  transactionId: number,
  payload: TransactionUpdatePayload,
): Promise<Transaction> {
  const response = await fetch(`/transactions/${transactionId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Transaction>(response)
}

export async function deleteTransaction(transactionId: number): Promise<void> {
  const response = await fetch(`/transactions/${transactionId}`, { method: 'DELETE' })
  await unwrap<null>(response)
}

export async function addTransactionTag(
  transactionId: number,
  tagId: number,
): Promise<Transaction> {
  const response = await fetch(`/transactions/${transactionId}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag_id: tagId }),
  })
  return unwrap<Transaction>(response)
}

export async function removeTransactionTag(
  transactionId: number,
  tagId: number,
): Promise<void> {
  const response = await fetch(`/transactions/${transactionId}/tags/${tagId}`, {
    method: 'DELETE',
  })
  await unwrap<null>(response)
}

export async function getTagUsageCount(tagId: number): Promise<number> {
  const response = await fetch(`/transactions/tags/${tagId}/count`)
  const data = await unwrap<{ count: number }>(response)
  return data.count
}
