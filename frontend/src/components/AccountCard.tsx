import type { Account } from '../api/accounts'
import { formatDate, formatMontant } from '../lib/format'

interface AccountCardProps {
  account: Account
  selected: boolean
  onSelect: (accountId: number) => void
}

function AccountCard({ account, selected, onSelect }: AccountCardProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(account.account_id)}
      className={`w-full rounded border bg-surface p-4 text-left transition-colors ${
        selected ? 'border-accent' : 'border-border'
      }`}
    >
      <p className="text-label text-ink-muted">{account.name}</p>
      <p className="mt-1 font-mono text-body-strong text-ink">
        {formatMontant(account.balance)}
      </p>
      <p className="mt-1 text-caption text-ink-muted">
        {formatDate(account.period_start)} – {formatDate(account.period_end)}
      </p>
    </button>
  )
}

export default AccountCard
