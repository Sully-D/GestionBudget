import { useMemo, useState } from 'react'
import type { RuleConditionType } from '../api/rules'
import type { Tag } from '../api/tags'
import { conditionLabels, sortTagsByCategoryAndName, tagBreadcrumb } from '../lib/format'

interface TagSuggestionChipProps {
  selectedTagId: number | null
  isSuggestion: boolean
  matchedRule: { condition_type: RuleConditionType; condition_value: string } | null
  allTags: Tag[]
  allTagsLoading: boolean
  onChange: (tagId: number | null) => void
}

const formFieldClass =
  'rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_rgba(37,99,235,0.12)]'

function TagSuggestionChip({
  selectedTagId,
  isSuggestion,
  matchedRule,
  allTags,
  allTagsLoading,
  onChange,
}: TagSuggestionChipProps) {
  const [isEditingLocal, setIsEditingLocal] = useState(false)
  const tagById = useMemo(() => new Map(allTags.map((t) => [t.tag_id, t])), [allTags])
  const sortedTags = useMemo(() => sortTagsByCategoryAndName(allTags, tagById), [allTags, tagById])

  const selectedTag = selectedTagId !== null ? allTags.find((t) => t.tag_id === selectedTagId) : undefined
  const showSelect = isEditingLocal || selectedTagId === null || !selectedTag

  if (showSelect) {
    return (
      <select
        value={selectedTagId ?? ''}
        onChange={(e) => {
          const value = e.target.value
          const tagId = value === '' ? null : Number(value)
          onChange(tagId)
          if (tagId !== null) {
            setIsEditingLocal(false)
          }
        }}
        disabled={allTagsLoading}
        className={formFieldClass}
      >
        <option value="">Aucun Tag</option>
        {sortedTags.map((tag) => (
          <option key={tag.tag_id} value={tag.tag_id}>
            {tagBreadcrumb(tag, tagById)}
          </option>
        ))}
      </select>
    )
  }

  const tagLabel = selectedTag ? tagBreadcrumb(selectedTag, tagById) : ''

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2 rounded-lg border-1.5 border-dashed border-accent bg-accent-bg px-3 py-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {isSuggestion && (
            <span className="rounded border border-dashed border-accent bg-surface px-1.5 py-0.5 text-caption text-accent">
              Suggéré
            </span>
          )}
          <span className="truncate text-body-strong text-ink">{tagLabel}</span>
        </div>
        <button
          type="button"
          onClick={() => setIsEditingLocal(true)}
          aria-label="Modifier le Tag suggéré"
          className="flex h-11 w-11 shrink-0 items-center justify-center text-accent"
        >
          ✎
        </button>
      </div>
      {isSuggestion && matchedRule && (
        <p className="text-caption text-ink-muted">
          Basé sur la Règle &quot;{conditionLabels[matchedRule.condition_type]}{' '}
          {matchedRule.condition_value}&quot;. Un tap pour changer.
        </p>
      )}
    </div>
  )
}

export default TagSuggestionChip
