import { useRef } from 'react'
import type { MouseEvent } from 'react'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_rgba(37,99,235,0.12)]'

type RequiredField = 'date' | 'montant' | 'libelle'
type MappingField = RequiredField | 'tiers'

const FIELD_LABELS: Record<MappingField, string> = {
  date: 'Date',
  montant: 'Montant',
  libelle: 'Libellé',
  tiers: 'Tiers',
}

const FIELD_ERROR_PHRASES: Record<RequiredField, string> = {
  date: 'la date',
  montant: 'le montant',
  libelle: 'le libellé',
}

const REQUIRED_FIELDS: RequiredField[] = ['date', 'montant', 'libelle']

interface CsvColumnMappingProps {
  fileName: string
  columns: string[]
  previewRows: string[][]
  mapping: { date: string; montant: string; libelle: string; tiers: string }
  onChange: (field: MappingField, value: string) => void
  onSubmit: () => void
  submitting: boolean
}

function CsvColumnMapping({
  fileName,
  columns,
  previewRows,
  mapping,
  onChange,
  onSubmit,
  submitting,
}: CsvColumnMappingProps) {
  const fieldRefs = {
    date: useRef<HTMLSelectElement>(null),
    montant: useRef<HTMLSelectElement>(null),
    libelle: useRef<HTMLSelectElement>(null),
  }

  const missingFields = REQUIRED_FIELDS.filter((field) => !mapping[field])
  const isValid = missingFields.length === 0

  function handleImportClick(event: MouseEvent<HTMLButtonElement>) {
    if (!isValid) {
      event.preventDefault()
      fieldRefs[missingFields[0]].current?.focus()
      return
    }
    onSubmit()
  }

  function fieldErrorId(field: RequiredField) {
    return `csv-mapping-error-${field}`
  }

  function renderSelect(field: RequiredField | 'tiers', required: boolean) {
    const value = mapping[field]
    const invalid = required && !value
    return (
      <div className="grid grid-cols-[140px_1fr] items-start gap-4 border-b border-border-subtle py-3 last:border-b-0">
        <label htmlFor={`csv-mapping-${field}`} className="pt-2 text-label uppercase text-ink">
          {FIELD_LABELS[field]}{' '}
          {required ? (
            <span className="text-alert">*</span>
          ) : (
            <span className="normal-case font-normal text-ink-faint">(optionnel)</span>
          )}
        </label>
        <div>
          <select
            id={`csv-mapping-${field}`}
            ref={required ? fieldRefs[field as RequiredField] : undefined}
            value={value}
            onChange={(e) => onChange(field, e.target.value)}
            aria-invalid={invalid || undefined}
            aria-describedby={invalid ? fieldErrorId(field as RequiredField) : undefined}
            className={formFieldClass}
          >
            <option value="">— Sélectionner une colonne —</option>
            {columns.map((column) => (
              <option key={column} value={column}>
                {column}
              </option>
            ))}
          </select>
          {invalid && (
            <p id={fieldErrorId(field as RequiredField)} className="mt-1 text-caption text-alert">
              Colonne obligatoire non mappée. Sélectionnez la colonne du fichier contenant{' '}
              {FIELD_ERROR_PHRASES[field as RequiredField]}.
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-page-title font-bold text-ink">Mappage des colonnes CSV</h1>
      <p className="mt-1 text-body text-ink-muted">
        Fichier <span className="font-mono">{fileName}</span> · {columns.length} colonnes détectées
      </p>

      <p className="mt-4 text-section-title font-bold uppercase text-ink-muted">
        Aperçu du fichier
      </p>
      <div className="mt-2 overflow-x-auto rounded-md border border-border">
        <table className="w-full text-body">
          <thead className="bg-surface">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  className="px-3 py-2 text-left text-table-header uppercase text-ink-muted"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {previewRows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-t border-border-subtle">
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="px-3 py-2 font-mono text-ink">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-6 text-section-title font-bold uppercase text-ink-muted">
        Association des colonnes
      </p>
      <div className="mt-2 rounded border border-border">
        {!isValid && (
          <p role="alert" aria-live="assertive" className="m-3 rounded bg-alert-bg p-3 text-body text-alert">
            {missingFields.length === 1
              ? `Import bloqué. La colonne obligatoire « ${FIELD_LABELS[missingFields[0]]} » n'est pas mappée à une colonne du fichier.`
              : `Import bloqué. Les colonnes obligatoires suivantes ne sont pas mappées : ${missingFields
                  .map((field) => FIELD_LABELS[field])
                  .join(', ')}.`}
          </p>
        )}
        <div className="px-4">
          {renderSelect('date', true)}
          {renderSelect('montant', true)}
          {renderSelect('libelle', true)}
          {renderSelect('tiers', false)}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        {!isValid && (
          <span className="text-caption text-alert">
            {missingFields.length} colonne{missingFields.length > 1 ? 's' : ''} obligatoire
            {missingFields.length > 1 ? 's' : ''} non mappée{missingFields.length > 1 ? 's' : ''}.
          </span>
        )}
        <button
          type="button"
          aria-disabled={!isValid || submitting}
          onClick={handleImportClick}
          className={`ml-auto rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)] ${
            !isValid || submitting ? 'opacity-60' : ''
          }`}
        >
          Importer
        </button>
      </div>
    </div>
  )
}

export default CsvColumnMapping
