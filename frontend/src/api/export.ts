async function triggerDownload(url: string): Promise<void> {
  const response = await fetch(url)
  if (!response.ok) {
    let message = 'Erreur inattendue'
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // ignore: corps non-JSON
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  const disposition = response.headers.get('content-disposition') ?? ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match?.[1] ?? 'export'

  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

export async function downloadFullExport(format: 'json' | 'csv'): Promise<void> {
  await triggerDownload(`/export/full?format=${format}`)
}

export async function downloadFilteredExport(
  accountId: number,
  format: 'json' | 'csv',
  periodStart?: string,
  periodEnd?: string,
): Promise<void> {
  const params = new URLSearchParams({ account_id: String(accountId), format })
  if (periodStart) params.set('period_start', periodStart)
  if (periodEnd) params.set('period_end', periodEnd)
  await triggerDownload(`/export/filtered?${params.toString()}`)
}
