import type { MouseEvent } from 'react'
import type { AmbiguousCsvRow } from '../api/import'
import { formatDate, formatMontant } from '../lib/format'

type RowDecision = 'import' | 'ignore'

interface CsvDuplicateReviewProps {
  fileName: string
  ambiguousRows: AmbiguousCsvRow[]
  decisions: Record<number, RowDecision>
  onDecide: (rowIndex: number, decision: RowDecision) => void
  onSubmit: () => void
  submitting: boolean
}

function CsvDuplicateReview({
  fileName,
  ambiguousRows,
  decisions,
  onDecide,
  onSubmit,
  submitting,
}: CsvDuplicateReviewProps) {
  const undecidedCount = ambiguousRows.filter((row) => !decisions[row.row_index]).length
  const isValid = undecidedCount === 0

  function handleConfirmClick(event: MouseEvent<HTMLButtonElement>) {
    if (!isValid) {
      event.preventDefault()
      return
    }
    onSubmit()
  }

  return (
    <div>
      <h1 className="text-page-title font-bold text-ink">Lignes à revoir</h1>
      <p className="mt-1 text-body text-ink-muted">
        Fichier <span className="font-mono">{fileName}</span> · {ambiguousRows.length} ligne
        {ambiguousRows.length > 1 ? 's' : ''} ressemble{ambiguousRows.length > 1 ? 'nt' : ''} à une
        transaction déjà présente sur ce compte, sans lui être identique{ambiguousRows.length > 1 ? 's' : ''}.
        Aucune transaction ne sera enregistrée tant que chaque ligne n'est pas tranchée.
      </p>

      <div className="mt-4 rounded border border-border">
        {!isValid && (
          <p role="alert" aria-live="assertive" className="m-3 rounded bg-alert-bg p-3 text-body text-alert">
            {undecidedCount} ligne{undecidedCount > 1 ? 's' : ''} non tranchée{undecidedCount > 1 ? 's' : ''}.
          </p>
        )}
        <div className="divide-y divide-border-subtle">
          {ambiguousRows.map((row) => {
            const decision = decisions[row.row_index]
            return (
              <div key={row.row_index} className="p-4">
                <div className="grid grid-cols-2 gap-4 text-body">
                  <div>
                    <p className="text-caption uppercase text-ink-muted">Ligne du fichier</p>
                    <p className="mt-1 font-mono text-ink">
                      {formatDate(row.date)} · {formatMontant(row.amount)}
                    </p>
                    <p className="text-ink">{row.label}</p>
                    {row.payee && <p className="text-ink-muted">{row.payee}</p>}
                  </div>
                  <div>
                    <p className="text-caption uppercase text-ink-muted">Transaction déjà existante</p>
                    <p className="mt-1 font-mono text-ink">
                      {formatDate(row.date)} · {formatMontant(row.amount)}
                    </p>
                    <p className="text-ink">{row.existing_label}</p>
                    {row.existing_payee && <p className="text-ink-muted">{row.existing_payee}</p>}
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => onDecide(row.row_index, 'import')}
                    aria-pressed={decision === 'import'}
                    className={`rounded-lg px-3 py-2 text-body ${
                      decision === 'import'
                        ? 'bg-accent text-surface'
                        : 'border border-border text-ink'
                    }`}
                  >
                    Importer quand même
                  </button>
                  <button
                    type="button"
                    onClick={() => onDecide(row.row_index, 'ignore')}
                    aria-pressed={decision === 'ignore'}
                    className={`rounded-lg px-3 py-2 text-body ${
                      decision === 'ignore'
                        ? 'bg-accent text-surface'
                        : 'border border-border text-ink'
                    }`}
                  >
                    Ignorer (doublon)
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        {!isValid && (
          <span className="text-caption text-alert">
            Tranchez chaque ligne avant de confirmer.
          </span>
        )}
        <button
          type="button"
          aria-disabled={!isValid || submitting}
          onClick={handleConfirmClick}
          className={`ml-auto rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)] ${
            !isValid || submitting ? 'opacity-60' : ''
          }`}
        >
          Confirmer l'import
        </button>
      </div>
    </div>
  )
}

export default CsvDuplicateReview
