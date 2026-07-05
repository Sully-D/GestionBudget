import { useMemo, useState } from 'react'
import type { DragEvent, KeyboardEvent } from 'react'
import type { Rule, RuleConditionType, RuleUpdatePayload } from '../api/rules'
import type { Tag } from '../api/tags'
import { conditionLabels, tagBreadcrumb } from '../lib/format'

const iconButtonClass =
  'flex h-11 w-11 flex-shrink-0 items-center justify-center text-ink-muted hover:text-ink'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink focus:border-accent focus:outline-none'

interface RuleRowProps {
  rule: Rule
  allTags: Tag[]
  position: number
  total: number
  dragging: boolean
  onDragStart: () => void
  onDragEnter: () => void
  onDragEnd: (event: DragEvent) => void
  onKeyboardMove: (direction: 'up' | 'down') => void
  onKeyboardCommit: () => void
  onKeyboardCancel: () => void
  armed: boolean
  onArm: () => void
  onEdit: (ruleId: number, payload: RuleUpdatePayload) => Promise<void>
  onDeleteConfirm: (rule: Rule) => void
}

function RuleRow({
  rule,
  allTags,
  position,
  total,
  dragging,
  onDragStart,
  onDragEnter,
  onDragEnd,
  onKeyboardMove,
  onKeyboardCommit,
  onKeyboardCancel,
  armed,
  onArm,
  onEdit,
  onDeleteConfirm,
}: RuleRowProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editConditionType, setEditConditionType] = useState<RuleConditionType>(rule.condition_type)
  const [editConditionValue, setEditConditionValue] = useState(rule.condition_value)
  const [editTagId, setEditTagId] = useState(String(rule.tag_id))
  const [editError, setEditError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const targetTag = allTags.find((t) => t.tag_id === rule.tag_id)
  const tagById = useMemo(() => new Map(allTags.map((t) => [t.tag_id, t])), [allTags])

  function startEditing() {
    setEditConditionType(rule.condition_type)
    setEditConditionValue(rule.condition_value)
    setEditTagId(String(rule.tag_id))
    setEditError(null)
    setIsEditing(true)
  }

  async function submitEdit() {
    const trimmed = editConditionValue.trim()
    if (trimmed === '') {
      setEditError('La valeur de la condition ne peut pas être vide.')
      return
    }
    if (editTagId === '') {
      setEditError('Choisissez un Tag cible.')
      return
    }
    if (submitting) return
    setSubmitting(true)
    try {
      await onEdit(rule.rule_id, {
        condition_type: editConditionType,
        condition_value: trimmed,
        tag_id: Number(editTagId),
      })
      setIsEditing(false)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      setSubmitting(false)
    }
  }

  function handleEditValueKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      setIsEditing(false)
      setEditError(null)
    }
  }

  function handleDragHandleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault()
      if (armed) {
        onKeyboardCommit()
      } else {
        onArm()
      }
    } else if (armed && event.key === 'ArrowUp') {
      event.preventDefault()
      onKeyboardMove('up')
    } else if (armed && event.key === 'ArrowDown') {
      event.preventDefault()
      onKeyboardMove('down')
    } else if (armed && event.key === 'Escape') {
      event.preventDefault()
      onKeyboardCancel()
    }
  }

  function handleDragHandleBlur() {
    if (armed) {
      onKeyboardCancel()
    }
  }

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDragEnter={onDragEnter}
      onDrop={(e) => e.preventDefault()}
      className={`flex items-center gap-3 border-b border-border-subtle px-4 py-2 ${dragging ? 'opacity-50' : ''} ${armed ? 'bg-accent-bg' : ''}`}
    >
      <button
        type="button"
        draggable="true"
        onDragStart={onDragStart}
        onDragEnter={onDragEnter}
        onDragEnd={onDragEnd}
        onKeyDown={handleDragHandleKeyDown}
        onBlur={handleDragHandleBlur}
        aria-label={
          armed
            ? `Réordonner : Espace pour déplacer (position ${position} sur ${total})`
            : 'Réordonner : Espace pour déplacer'
        }
        className="flex h-11 w-11 flex-shrink-0 cursor-grab items-center justify-center text-ink-faint"
      >
        <span aria-hidden="true" className="grid grid-cols-2 gap-0.5">
          {Array.from({ length: 6 }).map((_, i) => (
            <span key={i} className="h-1 w-1 rounded-full bg-current" />
          ))}
        </span>
      </button>

      <span className="w-4 flex-shrink-0 font-mono text-caption text-ink-faint">{position}</span>

      {isEditing ? (
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <select
            value={editConditionType}
            onChange={(e) => setEditConditionType(e.target.value as RuleConditionType)}
            disabled={submitting}
            className={formFieldClass}
          >
            <option value="label_contains">Libellé contient</option>
            <option value="payee_exact">Tiers =</option>
          </select>
          <input
            autoFocus
            type="text"
            placeholder="Valeur"
            value={editConditionValue}
            onChange={(e) => setEditConditionValue(e.target.value)}
            onKeyDown={handleEditValueKeyDown}
            disabled={submitting}
            className={formFieldClass}
          />
          <select
            value={editTagId}
            onChange={(e) => setEditTagId(e.target.value)}
            disabled={submitting}
            className={formFieldClass}
          >
            <option value="">Choisir un Tag…</option>
            {allTags.map((t) => (
              <option key={t.tag_id} value={t.tag_id}>
                {tagBreadcrumb(t, tagById)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={submitEdit}
            disabled={submitting}
            className="text-body-strong text-accent disabled:opacity-60"
          >
            Enregistrer
          </button>
          {editError && <p className="w-full text-caption text-alert">{editError}</p>}
        </div>
      ) : (
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <span className="max-w-full truncate text-body text-ink">
            <span className="text-ink-muted">{conditionLabels[rule.condition_type]}</span>{' '}
            <span className="font-bold">&quot;{rule.condition_value}&quot;</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="text-ink-faint" aria-hidden="true">
              →
            </span>
            <span className="whitespace-nowrap rounded-full bg-accent-bg px-2.5 py-0.5 text-caption font-bold text-accent">
              {targetTag ? tagBreadcrumb(targetTag, tagById) : `Tag ${rule.tag_id}`}
            </span>
          </span>
        </div>
      )}

      {!isEditing && (
        <div className="flex flex-shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={startEditing}
            aria-label="Modifier la règle"
            className={iconButtonClass}
          >
            ✎
          </button>
          <button
            type="button"
            onClick={() => onDeleteConfirm(rule)}
            aria-label="Supprimer la règle"
            className={`${iconButtonClass} hover:text-alert`}
          >
            🗑
          </button>
        </div>
      )}
    </div>
  )
}

export default RuleRow
