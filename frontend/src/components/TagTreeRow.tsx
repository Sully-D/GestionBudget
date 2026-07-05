import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { Tag } from '../api/tags'

export interface TagNode {
  tag: Tag
  children: TagNode[]
}

const indentByDepth: Record<0 | 1 | 2, string> = {
  0: '',
  1: 'pl-[30px]',
  2: 'pl-[54px]',
}

const iconButtonClass =
  'flex h-11 w-11 items-center justify-center text-ink-muted hover:text-ink'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink focus:border-accent focus:outline-none'

interface TagTreeRowProps {
  node: TagNode
  depth: 0 | 1 | 2
  onRenameRequest: (tag: Tag, name: string) => void
  onAddChild: (parentId: number, name: string) => Promise<void>
  onDeleteConfirm: (tag: Tag) => void
}

function TagTreeRow({ node, depth, onRenameRequest, onAddChild, onDeleteConfirm }: TagTreeRowProps) {
  const [isRenaming, setIsRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState(node.tag.name)
  const [renameError, setRenameError] = useState<string | null>(null)

  const [isAddingChild, setIsAddingChild] = useState(false)
  const [newChildValue, setNewChildValue] = useState('')
  const [addChildError, setAddChildError] = useState<string | null>(null)
  const [submittingChild, setSubmittingChild] = useState(false)

  const [blockedMessage, setBlockedMessage] = useState(false)

  const hasChildren = node.children.length > 0
  const childDepth = (depth + 1) as 0 | 1 | 2

  function startRenaming() {
    setRenameValue(node.tag.name)
    setRenameError(null)
    setIsRenaming(true)
  }

  function submitRename() {
    const trimmed = renameValue.trim()
    if (trimmed === '') {
      setRenameError('Le nom du Tag ne peut pas être vide.')
      return
    }
    onRenameRequest(node.tag, trimmed)
    setIsRenaming(false)
  }

  function handleRenameKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault()
      submitRename()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setIsRenaming(false)
      setRenameError(null)
    }
  }

  function startAddingChild() {
    setNewChildValue('')
    setAddChildError(null)
    setIsAddingChild(true)
  }

  async function submitAddChild() {
    const trimmed = newChildValue.trim()
    if (trimmed === '') {
      setAddChildError('Le nom du Tag ne peut pas être vide.')
      return
    }
    if (submittingChild) return
    setSubmittingChild(true)
    try {
      await onAddChild(node.tag.tag_id, trimmed)
      setIsAddingChild(false)
    } catch (err) {
      setAddChildError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      setSubmittingChild(false)
    }
  }

  function handleAddChildKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault()
      submitAddChild()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setIsAddingChild(false)
      setAddChildError(null)
    }
  }

  function handleDeleteClick() {
    if (hasChildren) {
      setBlockedMessage(true)
      return
    }
    onDeleteConfirm(node.tag)
  }

  return (
    <div>
      <div
        className={`flex items-center justify-between border-b border-border-subtle py-2 pr-2 ${indentByDepth[depth]}`}
      >
        <div className="flex min-w-0 items-center gap-1.5">
          <span
            className={`w-3 text-ink-faint ${hasChildren ? '' : 'invisible'}`}
            aria-hidden="true"
          >
            ⌄
          </span>
          {isRenaming ? (
            <input
              autoFocus
              type="text"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={handleRenameKeyDown}
              className={formFieldClass}
            />
          ) : (
            <span
              className={`truncate text-body text-ink ${depth === 0 ? 'font-bold' : 'font-semibold'}`}
            >
              {node.tag.name}
            </span>
          )}
          {hasChildren && !isRenaming && (
            <span className="text-caption text-ink-faint">
              {node.children.length} sous-tag{node.children.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 opacity-85">
          <button
            type="button"
            onClick={startRenaming}
            aria-label={`Renommer ${node.tag.name}`}
            className={iconButtonClass}
          >
            ✎
          </button>
          {depth < 2 && (
            <button
              type="button"
              onClick={startAddingChild}
              aria-label={`Ajouter un sous-tag à ${node.tag.name}`}
              className={iconButtonClass}
            >
              ＋
            </button>
          )}
          <button
            type="button"
            onClick={handleDeleteClick}
            aria-label={`Supprimer ${node.tag.name}`}
            className={`${iconButtonClass} hover:text-alert`}
          >
            🗑
          </button>
        </div>
      </div>

      {renameError && (
        <p className={`${indentByDepth[depth]} py-1 text-caption text-alert`}>{renameError}</p>
      )}

      {blockedMessage && (
        <p className={`${indentByDepth[depth]} flex items-center gap-2 py-1 text-caption text-alert`}>
          Supprimez d'abord les tags enfants
          <button
            type="button"
            onClick={() => setBlockedMessage(false)}
            className="text-caption text-ink-muted underline"
          >
            OK
          </button>
        </p>
      )}

      {isAddingChild && (
        <div className={`${indentByDepth[childDepth]} flex flex-col gap-1 py-2`}>
          <input
            autoFocus
            type="text"
            placeholder="Nom du sous-tag"
            value={newChildValue}
            onChange={(e) => setNewChildValue(e.target.value)}
            onKeyDown={handleAddChildKeyDown}
            disabled={submittingChild}
            className={formFieldClass}
          />
          {addChildError && <p className="text-caption text-alert">{addChildError}</p>}
        </div>
      )}

      {node.children.map((child) => (
        <TagTreeRow
          key={child.tag.tag_id}
          node={child}
          depth={childDepth}
          onRenameRequest={onRenameRequest}
          onAddChild={onAddChild}
          onDeleteConfirm={onDeleteConfirm}
        />
      ))}
    </div>
  )
}

export default TagTreeRow
