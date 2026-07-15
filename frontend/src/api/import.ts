import { unwrap } from './http'

export interface ImportResult {
  imported_count: number
  duplicate_count: number
}

export async function importOfx(accountId: number, file: File): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('account_id', String(accountId))
  formData.append('file', file)
  const response = await fetch('/import/ofx', { method: 'POST', body: formData })
  return unwrap<ImportResult>(response)
}

export interface CsvColumnMapping {
  date_column: string
  montant_column: string
  libelle_column: string
  tiers_column: string | null
}

export interface CsvPreviewResult {
  columns: string[]
  preview_rows: string[][]
  saved_mapping: CsvColumnMapping | null
}

export interface CsvImportResult {
  imported_count: number
  skipped_count: number
}

export async function previewCsv(file: File, accountId: number): Promise<CsvPreviewResult> {
  const formData = new FormData()
  formData.append('account_id', String(accountId))
  formData.append('file', file)
  const response = await fetch('/import/csv/preview', { method: 'POST', body: formData })
  return unwrap<CsvPreviewResult>(response)
}

export async function importCsv(
  accountId: number,
  file: File,
  mapping: CsvColumnMapping,
): Promise<CsvImportResult> {
  const formData = new FormData()
  formData.append('account_id', String(accountId))
  formData.append('date_column', mapping.date_column)
  formData.append('montant_column', mapping.montant_column)
  formData.append('libelle_column', mapping.libelle_column)
  if (mapping.tiers_column) formData.append('tiers_column', mapping.tiers_column)
  formData.append('file', file)
  const response = await fetch('/import/csv', { method: 'POST', body: formData })
  return unwrap<CsvImportResult>(response)
}
