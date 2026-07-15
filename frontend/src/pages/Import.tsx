import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { importCsv, importOfx, previewCsv } from '../api/import'
import type { CsvImportResult, CsvPreviewResult, ImportResult } from '../api/import'
import CsvColumnMapping from '../components/CsvColumnMapping'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_rgba(37,99,235,0.12)]'

type ImportSummary = ({ kind: 'ofx' } & ImportResult) | ({ kind: 'csv' } & CsvImportResult)

type CsvMappingState = { date: string; montant: string; libelle: string; tiers: string }

const EMPTY_CSV_MAPPING: CsvMappingState = { date: '', montant: '', libelle: '', tiers: '' }

function Import() {
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountId, setAccountId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ImportSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<'form' | 'csv-mapping'>('form')
  const [csvPreview, setCsvPreview] = useState<CsvPreviewResult | null>(null)
  const [csvMapping, setCsvMapping] = useState<CsvMappingState>(EMPTY_CSV_MAPPING)
  const submittingRef = useRef(false)
  const previewRequestIdRef = useRef(0)

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        setAccountId((current) => current ?? data[0]?.account_id ?? null)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
  }, [])

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const input = event.target
    const selected = input.files?.[0] ?? null
    setFile(selected)
    setError(null)
    setCsvPreview(null)
    setStep('form')

    if (selected && selected.name.toLowerCase().endsWith('.csv')) {
      if (accountId === null) {
        setError('Sélectionnez un compte avant de choisir un fichier CSV.')
        setFile(null)
        input.value = ''
        return
      }
      const requestId = ++previewRequestIdRef.current
      previewCsv(selected, accountId)
        .then((preview) => {
          if (requestId !== previewRequestIdRef.current) return
          setCsvPreview(preview)
          setCsvMapping(
            preview.saved_mapping
              ? {
                  date: preview.saved_mapping.date_column,
                  montant: preview.saved_mapping.montant_column,
                  libelle: preview.saved_mapping.libelle_column,
                  tiers: preview.saved_mapping.tiers_column ?? '',
                }
              : EMPTY_CSV_MAPPING,
          )
          setStep('csv-mapping')
        })
        .catch((err) => {
          if (requestId !== previewRequestIdRef.current) return
          setError(err instanceof Error ? err.message : 'Erreur inattendue')
          setFile(null)
          input.value = ''
        })
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (file === null || accountId === null || submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    setError(null)
    try {
      const importResult = await importOfx(accountId, file)
      setResult({ kind: 'ofx', ...importResult })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  async function handleCsvImport() {
    if (file === null || accountId === null || submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    setError(null)
    try {
      const importResult = await importCsv(accountId, file, {
        date_column: csvMapping.date,
        montant_column: csvMapping.montant,
        libelle_column: csvMapping.libelle,
        tiers_column: csvMapping.tiers || null,
      })
      setResult({ kind: 'csv', ...importResult })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  if (result !== null) {
    return (
      <main className="mx-auto max-w-md px-4 py-6 sm:px-4 lg:px-7">
        <h1 className="text-page-title font-bold text-ink">Import terminé</h1>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border p-4">
            <div className="mb-2 h-[26px] w-[26px] rounded-md bg-positive-bg" aria-hidden="true" />
            <div className="font-mono text-stat-value text-ink">{result.imported_count}</div>
            <div className="mt-0.5 text-caption text-ink-muted">Transactions importées</div>
          </div>
          <div className="rounded-lg border border-border p-4">
            <div className="mb-2 h-[26px] w-[26px] rounded-md bg-surface-panel" aria-hidden="true" />
            <div className="font-mono text-stat-value text-ink">
              {result.kind === 'ofx' ? result.duplicate_count : result.skipped_count}
            </div>
            <div className="mt-0.5 text-caption text-ink-muted">
              {result.kind === 'ofx'
                ? 'Doublons ignorés (FITID déjà connus)'
                : 'Lignes ignorées (invalides)'}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => navigate('/transactions')}
          className="mt-6 rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)]"
        >
          Retour aux transactions
        </button>
      </main>
    )
  }

  if (step === 'csv-mapping' && csvPreview !== null) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
        <CsvColumnMapping
          fileName={file?.name ?? ''}
          columns={csvPreview.columns}
          previewRows={csvPreview.preview_rows}
          mapping={csvMapping}
          onChange={(field, value) => setCsvMapping((prev) => ({ ...prev, [field]: value }))}
          onSubmit={handleCsvImport}
          submitting={submitting}
        />
        {error && (
          <p role="alert" className="mt-4 text-body text-alert">
            {error}
          </p>
        )}
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-md px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">Importer un relevé</h1>

      <form
        onSubmit={handleSubmit}
        className="mt-4 flex flex-col gap-4 rounded border border-border bg-surface p-4"
      >
        <label className="flex flex-col gap-1">
          <span className="text-label text-ink-muted">Compte</span>
          <select
            value={accountId ?? ''}
            onChange={(e) => setAccountId(Number(e.target.value))}
            className={formFieldClass}
          >
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-label text-ink-muted">Fichier OFX ou CSV</span>
          <input
            type="file"
            accept=".ofx,.csv"
            onChange={handleFileChange}
            className={formFieldClass}
          />
        </label>

        {error && (
          <p role="alert" className="text-body text-alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={
            file === null ||
            accountId === null ||
            submitting ||
            file.name.toLowerCase().endsWith('.csv')
          }
          className="rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)] disabled:opacity-60"
        >
          Importer
        </button>
      </form>
    </main>
  )
}

export default Import
