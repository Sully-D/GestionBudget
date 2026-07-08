import { unwrap } from './http'

export interface Account {
  account_id: number
  name: string
  is_common: boolean
  start_day: number
  reference_balance: number | null
  reference_date: string | null
  balance: number
  period_start: string
  period_end: string
}

export interface AccountUpdatePayload {
  start_day?: number
  reference_balance?: number
  reference_date?: string
}

export async function getAccounts(): Promise<Account[]> {
  const response = await fetch('/accounts')
  return unwrap<Account[]>(response)
}

export async function updateAccount(
  accountId: number,
  payload: AccountUpdatePayload,
): Promise<Account> {
  const response = await fetch(`/accounts/${accountId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Account>(response)
}

export interface AccountBalanceAsOf {
  account_id: number
  as_of: string
  balance: number
}

export async function getAccountBalanceAsOf(
  accountId: number,
  asOf: string,
): Promise<AccountBalanceAsOf> {
  const params = new URLSearchParams({ as_of: asOf })
  const response = await fetch(`/accounts/${accountId}/balance?${params.toString()}`)
  return unwrap<AccountBalanceAsOf>(response)
}
