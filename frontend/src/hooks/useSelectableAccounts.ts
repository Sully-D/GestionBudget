import { useEffect, useState } from 'react'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'

export interface SelectableAccounts {
  accounts: Account[]
  accountsLoaded: boolean
  accountsError: string | null
  selectedAccountId: number | null
  setSelectedAccountId: (accountId: number) => void
}

// Charge les Comptes personnels (hors Compte Commun) et sélectionne le premier
// par défaut — bootstrap dupliqué à l'identique entre Recurrentes.tsx et
// Projection.tsx depuis les Stories 5.1/5.2, extrait ici (clôture Epic 7,
// item d'action rétro sur les patterns frontend dupliqués).
export function useSelectableAccounts(): SelectableAccounts {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountsLoaded, setAccountsLoaded] = useState(false)
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)

  useEffect(() => {
    getAccounts()
      .then((data) => {
        const personal = data.filter((a) => !a.is_common)
        setAccounts(personal)
        setSelectedAccountId((current) => current ?? personal[0]?.account_id ?? null)
        setAccountsError(null)
      })
      .catch((err) => {
        setAccountsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => setAccountsLoaded(true))
  }, [])

  return { accounts, accountsLoaded, accountsError, selectedAccountId, setSelectedAccountId }
}
