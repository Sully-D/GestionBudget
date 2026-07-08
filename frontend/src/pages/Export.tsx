import { useState } from 'react'
import { downloadFullExport } from '../api/export'

function Export() {
  const [loading, setLoading] = useState<'json' | 'csv' | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleDownload(format: 'json' | 'csv') {
    setLoading(format)
    setError(null)
    try {
      await downloadFullExport(format)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      setLoading(null)
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">Export des données</h1>

      <section className="mt-4 flex flex-col gap-3 rounded border border-border bg-surface p-4">
        <h2 className="text-body-strong text-ink">Export complet</h2>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => handleDownload('json')}
            disabled={loading !== null}
            className="rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)] disabled:opacity-60"
          >
            {loading === 'json' ? 'Chargement…' : 'Télécharger JSON'}
          </button>
          <button
            type="button"
            onClick={() => handleDownload('csv')}
            disabled={loading !== null}
            className="rounded-lg border border-border px-4 py-3 text-body-strong text-ink disabled:opacity-60"
          >
            {loading === 'csv' ? 'Chargement…' : 'Télécharger CSV'}
          </button>
        </div>
        {error && (
          <p role="alert" className="text-body text-alert">
            {error}
          </p>
        )}
      </section>
    </main>
  )
}

export default Export
