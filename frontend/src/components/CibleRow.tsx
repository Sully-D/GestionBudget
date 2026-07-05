import type { Tag } from '../api/tags'
import { formatMontant } from '../lib/format'

const iconButtonClass =
  'flex h-11 w-11 flex-shrink-0 items-center justify-center text-ink-muted hover:text-ink'

// Profondeur bornée par MAX_LEVEL=3 côté Tag (racine=0, jusqu'à 2 niveaux d'indentation) —
// classes Tailwind littérales pour rester détectables par le compilateur JIT.
const depthPaddingClasses = ['', 'pl-[34px]', 'pl-[68px]']

interface CibleRowProps {
  tag: Tag
  percentage: number
  amount: number
  widthPct: number
  depth: number
  onEdit: () => void
  onDeleteConfirm: () => void
}

function CibleRow({ tag, percentage, amount, widthPct, depth, onEdit, onDeleteConfirm }: CibleRowProps) {
  const isChild = depth > 0
  return (
    <div
      className={`flex items-center justify-between gap-3 border-b border-border-subtle py-2 pr-2 ${depthPaddingClasses[depth] ?? depthPaddingClasses[depthPaddingClasses.length - 1]}`}
    >
      <span
        className={`min-w-0 flex-1 truncate text-body text-ink ${isChild ? '' : 'font-bold'}`}
      >
        {tag.name}
      </span>
      <div className="flex flex-shrink-0 items-center gap-2">
        <span className="h-1.5 w-16 overflow-hidden rounded-full bg-border" aria-hidden="true">
          <span
            className="block h-full rounded-full bg-accent"
            style={{ width: `${Math.min(widthPct, 100)}%` }}
          />
        </span>
        <span className="w-12 text-right font-mono text-caption text-ink">{percentage} %</span>
        <span className="w-20 text-right font-mono text-caption text-ink-muted">
          {formatMontant(amount)}
        </span>
      </div>
      <div className="flex flex-shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onEdit}
          aria-label={`Modifier la Cible de ${tag.name}`}
          className={iconButtonClass}
        >
          ✎
        </button>
        <button
          type="button"
          onClick={onDeleteConfirm}
          aria-label={`Supprimer la Cible de ${tag.name}`}
          className={`${iconButtonClass} hover:text-alert`}
        >
          🗑
        </button>
      </div>
    </div>
  )
}

export default CibleRow
