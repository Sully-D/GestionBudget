import { useMemo, useState } from 'react'
import type { Tag } from '../api/tags'
import type { TagSummary } from '../api/transactions'
import { addTransactionTag, getTransaction, removeTransactionTag } from '../api/transactions'
import { sortTagsByCategoryAndName, tagBreadcrumb } from '../lib/format'

interface TransactionTagEditorProps {
  transactionId: number
  tags: TagSummary[]
  allTags: Tag[]
  allTagsLoading?: boolean
  onTagsChange: (tags: TagSummary[]) => void
}

const formFieldClass =
  'rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink focus:border-accent focus:outline-none'

function TransactionTagEditor({
  transactionId,
  tags,
  allTags,
  allTagsLoading = false,
  onTagsChange,
}: TransactionTagEditorProps) {
  const [selectedTagId, setSelectedTagId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [removingIds, setRemovingIds] = useState<Set<number>>(new Set())

  const tagById = useMemo(() => new Map(allTags.map((t) => [t.tag_id, t])), [allTags])
  const availableTags = useMemo(() => {
    const associatedIds = new Set(tags.map((t) => t.tag_id))
    return sortTagsByCategoryAndName(
      allTags.filter((t) => !associatedIds.has(t.tag_id)),
      tagById,
    )
  }, [allTags, tags, tagById])

  async function refetchTags() {
    const transaction = await getTransaction(transactionId)
    onTagsChange(transaction.tags)
  }

  async function handleAdd() {
    if (selectedTagId === '' || submitting) return
    setSubmitting(true)
    setError(null)
    const tagId = Number(selectedTagId)
    try {
      await addTransactionTag(transactionId, tagId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
      setSubmitting(false)
      return
    }
    setSelectedTagId('')
    try {
      await refetchTags()
    } catch {
      setError("Tag ajouté, mais l'affichage n'a pas pu être rafraîchi — rechargez la page.")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRemove(tagId: number) {
    if (removingIds.has(tagId)) return
    setRemovingIds((current) => new Set(current).add(tagId))
    setError(null)
    try {
      await removeTransactionTag(transactionId, tagId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
      setRemovingIds((current) => {
        const next = new Set(current)
        next.delete(tagId)
        return next
      })
      return
    }
    try {
      await refetchTags()
    } catch {
      setError("Tag retiré, mais l'affichage n'a pas pu être rafraîchi — rechargez la page.")
    } finally {
      setRemovingIds((current) => {
        const next = new Set(current)
        next.delete(tagId)
        return next
      })
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-label text-ink-muted">Tags</span>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <span
              key={tag.tag_id}
              className="inline-flex items-center gap-1 rounded-full bg-accent-bg py-0.5 pl-2.5 pr-1 text-caption font-bold text-accent"
            >
              {tag.name}
              <button
                type="button"
                onClick={() => handleRemove(tag.tag_id)}
                disabled={removingIds.has(tag.tag_id)}
                aria-label={`Retirer le tag ${tag.name}`}
                className="flex h-11 w-11 items-center justify-center text-accent hover:text-alert disabled:opacity-60"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-1">
        <label htmlFor="transaction-tag-picker" className="text-label text-ink-muted">
          Tag
        </label>
        <div className="flex items-center gap-2">
          <select
            id="transaction-tag-picker"
            value={selectedTagId}
            onChange={(e) => setSelectedTagId(e.target.value)}
            disabled={submitting || availableTags.length === 0}
            className={formFieldClass}
          >
            <option value="">Choisir un Tag…</option>
            {availableTags.map((t) => (
              <option key={t.tag_id} value={t.tag_id}>
                {tagBreadcrumb(t, tagById)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleAdd}
            disabled={selectedTagId === '' || submitting || availableTags.length === 0}
            className="text-body-strong text-accent disabled:opacity-60"
          >
            + Ajouter
          </button>
        </div>
      </div>

      {availableTags.length === 0 && (
        <p className="text-caption text-ink-muted">
          {allTagsLoading
            ? 'Chargement des Tags…'
            : allTags.length === 0
              ? "Aucun Tag disponible — créez-en un dans Budget."
              : 'Tous les Tags sont déjà associés.'}
        </p>
      )}

      {error && <p className="text-caption text-alert">{error}</p>}
    </div>
  )
}

export default TransactionTagEditor
