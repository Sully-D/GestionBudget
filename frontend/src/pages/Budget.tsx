import { useEffect, useMemo, useRef, useState } from 'react'
import type { DragEvent, KeyboardEvent, ReactNode } from 'react'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { getBudgetTargets, getPeriodSummary, upsertBudgetTarget, deleteBudgetTarget } from '../api/budget'
import type { BudgetTarget, RevenuePeriodSummary } from '../api/budget'
import { createRule, deleteRule, getRules, reorderRules, updateRule } from '../api/rules'
import type { Rule, RuleConditionType, RuleUpdatePayload } from '../api/rules'
import { createTag, deleteTag, getTags, updateTag } from '../api/tags'
import type { Tag } from '../api/tags'
import { getTagUsageCount } from '../api/transactions'
import CibleRow from '../components/CibleRow'
import RuleRow from '../components/RuleRow'
import TagTreeRow from '../components/TagTreeRow'
import type { TagNode } from '../components/TagTreeRow'
import { formatMontant, tagBreadcrumb } from '../lib/format'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-2 py-1 text-body text-ink focus:border-accent focus:outline-none'

function buildTree(tags: Tag[]): TagNode[] {
  const childrenByParent = new Map<number, Tag[]>()
  for (const tag of tags) {
    if (tag.parent_id === null) continue
    const siblings = childrenByParent.get(tag.parent_id) ?? []
    siblings.push(tag)
    childrenByParent.set(tag.parent_id, siblings)
  }

  function toNode(tag: Tag): TagNode {
    return {
      tag,
      children: (childrenByParent.get(tag.tag_id) ?? []).map(toNode),
    }
  }

  return tags.filter((t) => t.parent_id === null).map(toNode)
}

interface CibleBlock {
  tag: Tag
  target: BudgetTarget
  children: CibleBlock[]
  sumChildren: number
  warning: boolean
}

// Deux décimales en Decimal(5,2) : arrondir avant de comparer évite qu'une
// somme flottante (ex. 33.33 + 33.33 + 33.34) ne bascule autour d'une égalité exacte.
function round2(value: number): number {
  return Math.round(value * 100) / 100
}

function buildTargetBlocks(tags: Tag[], targetByTagId: Map<number, BudgetTarget>): CibleBlock[] {
  const childrenByParent = new Map<number, Tag[]>()
  const roots: Tag[] = []
  for (const tag of tags) {
    if (!targetByTagId.has(tag.tag_id)) continue
    const parentHasTarget = tag.parent_id !== null && targetByTagId.has(tag.parent_id)
    if (parentHasTarget) {
      const siblings = childrenByParent.get(tag.parent_id as number) ?? []
      siblings.push(tag)
      childrenByParent.set(tag.parent_id as number, siblings)
    } else {
      roots.push(tag)
    }
  }

  function buildBlock(tag: Tag): CibleBlock {
    const target = targetByTagId.get(tag.tag_id) as BudgetTarget
    const children = (childrenByParent.get(tag.tag_id) ?? []).map(buildBlock)
    const sumChildren = children.reduce((sum, c) => sum + c.target.percentage, 0)
    return {
      tag,
      target,
      children,
      sumChildren,
      warning: children.length > 0 && round2(sumChildren) > round2(target.percentage),
    }
  }

  return roots.map(buildBlock)
}

function targetAmount(percentage: number, total: number | undefined): number {
  return total !== undefined ? (percentage / 100) * total : 0
}

function Budget() {
  const [activeTab, setActiveTab] = useState<'tags' | 'rules' | 'targets'>('tags')

  const [tags, setTags] = useState<Tag[]>([])
  const tagById = useMemo(() => new Map(tags.map((t) => [t.tag_id, t])), [tags])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isAddingRoot, setIsAddingRoot] = useState(false)
  const [newRootValue, setNewRootValue] = useState('')
  const [addRootError, setAddRootError] = useState<string | null>(null)
  const [submittingRoot, setSubmittingRoot] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState<Tag | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)
  const retryButtonRef = useRef<HTMLButtonElement>(null)

  const [renameTarget, setRenameTarget] = useState<{
    tag: Tag
    newName: string
    count: number
  } | null>(null)
  const [renameError, setRenameError] = useState<string | null>(null)
  const [renaming, setRenaming] = useState(false)
  const renameCancelButtonRef = useRef<HTMLButtonElement>(null)
  const renameConfirmButtonRef = useRef<HTMLButtonElement>(null)
  const renameRetryButtonRef = useRef<HTMLButtonElement>(null)

  const [rules, setRules] = useState<Rule[]>([])
  const [rulesLoaded, setRulesLoaded] = useState(false)
  const [rulesLoading, setRulesLoading] = useState(false)
  const [rulesError, setRulesError] = useState<string | null>(null)

  const [isAddingRule, setIsAddingRule] = useState(false)
  const [newRuleConditionType, setNewRuleConditionType] = useState<RuleConditionType>('label_contains')
  const [newRuleConditionValue, setNewRuleConditionValue] = useState('')
  const [newRuleTagId, setNewRuleTagId] = useState('')
  const [addRuleError, setAddRuleError] = useState<string | null>(null)
  const [submittingRule, setSubmittingRule] = useState(false)

  const [draggedId, setDraggedId] = useState<number | null>(null)
  const [preDragOrder, setPreDragOrder] = useState<Rule[] | null>(null)
  const [dragError, setDragError] = useState<string | null>(null)
  const [reordering, setReordering] = useState(false)

  const [armedRuleId, setArmedRuleId] = useState<number | null>(null)
  const [preArmOrder, setPreArmOrder] = useState<Rule[] | null>(null)
  const [keyboardAnnouncement, setKeyboardAnnouncement] = useState('')

  const [ruleDeleteTarget, setRuleDeleteTarget] = useState<Rule | null>(null)
  const [ruleDeleteError, setRuleDeleteError] = useState<string | null>(null)
  const [ruleDeleting, setRuleDeleting] = useState(false)
  const ruleCancelButtonRef = useRef<HTMLButtonElement>(null)
  const ruleConfirmButtonRef = useRef<HTMLButtonElement>(null)
  const ruleRetryButtonRef = useRef<HTMLButtonElement>(null)

  const [personalAccounts, setPersonalAccounts] = useState<Account[]>([])
  const [accountsLoaded, setAccountsLoaded] = useState(false)
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [selectedTargetAccountId, setSelectedTargetAccountId] = useState<number | null>(null)
  const selectedTargetAccount =
    personalAccounts.find((a) => a.account_id === selectedTargetAccountId) ?? null

  const [targets, setTargets] = useState<BudgetTarget[]>([])
  const [targetSummary, setTargetSummary] = useState<RevenuePeriodSummary | null>(null)
  const [targetsLoading, setTargetsLoading] = useState(false)
  const [targetsError, setTargetsError] = useState<string | null>(null)
  const targetByTagId = useMemo(() => new Map(targets.map((t) => [t.tag_id, t])), [targets])

  const [isAddingTarget, setIsAddingTarget] = useState(false)
  const [targetFormMode, setTargetFormMode] = useState<'create' | 'edit'>('create')
  const [targetFormTagId, setTargetFormTagId] = useState('')
  const [targetFormPercentage, setTargetFormPercentage] = useState('')
  const [targetFormError, setTargetFormError] = useState<string | null>(null)
  const [submittingTarget, setSubmittingTarget] = useState(false)

  const [targetDeleteTarget, setTargetDeleteTarget] = useState<BudgetTarget | null>(null)
  const [targetDeleteError, setTargetDeleteError] = useState<string | null>(null)
  const [targetDeleting, setTargetDeleting] = useState(false)
  const targetCancelButtonRef = useRef<HTMLButtonElement>(null)
  const targetConfirmButtonRef = useRef<HTMLButtonElement>(null)
  const targetRetryButtonRef = useRef<HTMLButtonElement>(null)

  function refetch() {
    return getTags().then((data) => {
      setTags(data)
      setError(null)
    })
  }

  useEffect(() => {
    setLoading(true)
    refetch()
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (deleteTarget === null) return
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape' && !deleting) {
        setDeleteTarget(null)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [deleteTarget, deleting])

  useEffect(() => {
    if (deleteTarget !== null) {
      cancelButtonRef.current?.focus()
    }
  }, [deleteTarget])

  useEffect(() => {
    if (renameTarget === null) return
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape' && !renaming) {
        setRenameTarget(null)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [renameTarget, renaming])

  useEffect(() => {
    if (renameTarget !== null) {
      renameCancelButtonRef.current?.focus()
    }
  }, [renameTarget])

  async function handleRenameRequest(tag: Tag, newName: string) {
    if (newName === tag.name) return
    setError(null)
    let count: number
    try {
      count = await getTagUsageCount(tag.tag_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
      return
    }
    if (count === 0) {
      try {
        await updateTag(tag.tag_id, { name: newName })
        await refetch()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erreur inattendue')
      }
      return
    }
    setRenameError(null)
    setRenameTarget({ tag, newName, count })
  }

  async function confirmRename() {
    if (renameTarget === null) return
    setRenaming(true)
    try {
      await updateTag(renameTarget.tag.tag_id, { name: renameTarget.newName })
    } catch (err) {
      setRenameError(err instanceof Error ? err.message : 'Erreur inattendue')
      setRenaming(false)
      return
    }
    setRenameTarget(null)
    setRenaming(false)
    try {
      await refetch()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function handleRenameModalKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return
    const focusable = [
      renameRetryButtonRef.current,
      renameCancelButtonRef.current,
      renameConfirmButtonRef.current,
    ].filter((el): el is HTMLButtonElement => el !== null)
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  async function handleAddChild(parentId: number, name: string) {
    await createTag({ name, parent_id: parentId })
    try {
      await refetch()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function startAddingRoot() {
    setNewRootValue('')
    setAddRootError(null)
    setIsAddingRoot(true)
  }

  async function submitAddRoot() {
    const trimmed = newRootValue.trim()
    if (trimmed === '') {
      setAddRootError('Le nom du Tag ne peut pas être vide.')
      return
    }
    if (submittingRoot) return
    setSubmittingRoot(true)
    try {
      await createTag({ name: trimmed })
    } catch (err) {
      setAddRootError(err instanceof Error ? err.message : 'Erreur inattendue')
      setSubmittingRoot(false)
      return
    }
    setIsAddingRoot(false)
    setSubmittingRoot(false)
    try {
      await refetch()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function handleAddRootKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault()
      submitAddRoot()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setIsAddingRoot(false)
      setAddRootError(null)
    }
  }

  function handleModalKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return
    const focusable = [retryButtonRef.current, cancelButtonRef.current, confirmButtonRef.current].filter(
      (el): el is HTMLButtonElement => el !== null
    )
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  async function confirmDelete() {
    if (deleteTarget === null) return
    setDeleting(true)
    try {
      await deleteTag(deleteTarget.tag_id)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Erreur inattendue')
      setDeleting(false)
      return
    }
    setDeleteTarget(null)
    setDeleting(false)
    try {
      await refetch()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function openDeleteConfirm(tag: Tag) {
    setDeleteError(null)
    setDeleteTarget(tag)
  }

  function refetchRules() {
    return getRules().then((data) => {
      setRules(data)
      setRulesError(null)
    })
  }

  useEffect(() => {
    if (activeTab !== 'rules' || rulesLoaded) return
    setRulesLoading(true)
    refetchRules()
      .then(() => setRulesLoaded(true))
      .catch((err) => {
        setRulesError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => setRulesLoading(false))
  }, [activeTab, rulesLoaded])

  useEffect(() => {
    if (ruleDeleteTarget === null) return
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape' && !ruleDeleting) {
        setRuleDeleteTarget(null)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [ruleDeleteTarget, ruleDeleting])

  useEffect(() => {
    if (ruleDeleteTarget !== null) {
      ruleCancelButtonRef.current?.focus()
    }
  }, [ruleDeleteTarget])

  useEffect(() => {
    if (activeTab !== 'targets' || accountsLoaded) return
    getAccounts()
      .then((data) => {
        const personal = data.filter((a) => !a.is_common)
        setPersonalAccounts(personal)
        setSelectedTargetAccountId((current) => current ?? personal[0]?.account_id ?? null)
        setAccountsError(null)
      })
      .catch((err) => {
        setAccountsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => setAccountsLoaded(true))
  }, [activeTab, accountsLoaded])

  useEffect(() => {
    if (selectedTargetAccount === null) {
      setTargets([])
      setTargetSummary(null)
      return
    }
    let cancelled = false
    setTargetsLoading(true)
    Promise.all([
      getBudgetTargets(selectedTargetAccount.account_id),
      getPeriodSummary(selectedTargetAccount.account_id, selectedTargetAccount.period_start),
    ])
      .then(([targetsData, summaryData]) => {
        if (cancelled) return
        setTargets(targetsData)
        setTargetSummary(summaryData)
        setTargetsError(null)
      })
      .catch((err) => {
        if (!cancelled) setTargetsError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (!cancelled) setTargetsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedTargetAccount])

  useEffect(() => {
    if (targetDeleteTarget === null) return
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape' && !targetDeleting) {
        setTargetDeleteTarget(null)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [targetDeleteTarget, targetDeleting])

  useEffect(() => {
    if (targetDeleteTarget !== null) {
      targetCancelButtonRef.current?.focus()
    }
  }, [targetDeleteTarget])

  async function refetchTargets() {
    if (!selectedTargetAccount) return
    const [targetsData, summaryData] = await Promise.all([
      getBudgetTargets(selectedTargetAccount.account_id),
      getPeriodSummary(selectedTargetAccount.account_id, selectedTargetAccount.period_start),
    ])
    setTargets(targetsData)
    setTargetSummary(summaryData)
  }

  function startAddingTarget() {
    setTargetFormMode('create')
    setTargetFormTagId('')
    setTargetFormPercentage('')
    setTargetFormError(null)
    setIsAddingTarget(true)
  }

  function startEditingTarget(target: BudgetTarget) {
    setTargetFormMode('edit')
    setTargetFormTagId(String(target.tag_id))
    setTargetFormPercentage(String(target.percentage))
    setTargetFormError(null)
    setIsAddingTarget(true)
  }

  async function submitTargetForm() {
    if (!selectedTargetAccount) return
    if (targetFormTagId === '') {
      setTargetFormError('Choisissez un Tag.')
      return
    }
    const percentageValue = Number(targetFormPercentage)
    if (targetFormPercentage.trim() === '' || Number.isNaN(percentageValue) || percentageValue <= 0 || percentageValue > 100) {
      setTargetFormError('Le pourcentage doit être compris entre 0 et 100.')
      return
    }
    if (submittingTarget) return
    setSubmittingTarget(true)
    try {
      await upsertBudgetTarget({
        account_id: selectedTargetAccount.account_id,
        tag_id: Number(targetFormTagId),
        percentage: percentageValue,
      })
    } catch (err) {
      setTargetFormError(err instanceof Error ? err.message : 'Erreur inattendue')
      setSubmittingTarget(false)
      return
    }
    setIsAddingTarget(false)
    setSubmittingTarget(false)
    try {
      await refetchTargets()
    } catch (err) {
      setTargetsError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function handleTargetFormKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault()
      submitTargetForm()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setIsAddingTarget(false)
      setTargetFormError(null)
    }
  }

  function openTargetDeleteConfirm(target: BudgetTarget) {
    setTargetDeleteError(null)
    setTargetDeleteTarget(target)
  }

  async function confirmTargetDelete() {
    if (targetDeleteTarget === null) return
    setTargetDeleting(true)
    try {
      await deleteBudgetTarget(targetDeleteTarget.target_id)
    } catch (err) {
      setTargetDeleteError(err instanceof Error ? err.message : 'Erreur inattendue')
      setTargetDeleting(false)
      return
    }
    setTargetDeleteTarget(null)
    setTargetDeleting(false)
    try {
      await refetchTargets()
    } catch (err) {
      setTargetsError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function handleTargetModalKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return
    const focusable = [
      targetRetryButtonRef.current,
      targetCancelButtonRef.current,
      targetConfirmButtonRef.current,
    ].filter((el): el is HTMLButtonElement => el !== null)
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  function startAddingRule() {
    setNewRuleConditionType('label_contains')
    setNewRuleConditionValue('')
    setNewRuleTagId('')
    setAddRuleError(null)
    setIsAddingRule(true)
  }

  async function submitAddRule() {
    const trimmed = newRuleConditionValue.trim()
    if (trimmed === '') {
      setAddRuleError('La valeur de la condition ne peut pas être vide.')
      return
    }
    if (newRuleTagId === '') {
      setAddRuleError('Choisissez un Tag cible.')
      return
    }
    if (submittingRule) return
    setSubmittingRule(true)
    try {
      await createRule({
        condition_type: newRuleConditionType,
        condition_value: trimmed,
        tag_id: Number(newRuleTagId),
      })
    } catch (err) {
      setAddRuleError(err instanceof Error ? err.message : 'Erreur inattendue')
      setSubmittingRule(false)
      return
    }
    setIsAddingRule(false)
    setSubmittingRule(false)
    try {
      await refetchRules()
    } catch (err) {
      setRulesError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function handleAddRuleValueKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault()
      submitAddRule()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setIsAddingRule(false)
      setAddRuleError(null)
    }
  }

  async function handleEditRule(ruleId: number, payload: RuleUpdatePayload) {
    await updateRule(ruleId, payload)
    try {
      await refetchRules()
    } catch (err) {
      setRulesError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function handleDragStart(ruleId: number) {
    setDraggedId(ruleId)
    setPreDragOrder(rules)
  }

  function handleDragEnter(targetId: number) {
    if (draggedId === null || draggedId === targetId) return
    setRules((current) => {
      const fromIndex = current.findIndex((r) => r.rule_id === draggedId)
      const toIndex = current.findIndex((r) => r.rule_id === targetId)
      if (fromIndex === -1 || toIndex === -1) return current
      const next = [...current]
      const [moved] = next.splice(fromIndex, 1)
      next.splice(toIndex, 0, moved)
      return next
    })
  }

  async function handleDragEnd(event: DragEvent) {
    if (draggedId === null || reordering) return
    const cancelled = event.dataTransfer.dropEffect === 'none'
    setDraggedId(null)
    if (cancelled) {
      if (preDragOrder !== null) setRules(preDragOrder)
      setPreDragOrder(null)
      return
    }
    const orderedIds = rules.map((r) => r.rule_id)
    setPreDragOrder(null)
    setReordering(true)
    try {
      await reorderRules(orderedIds)
      setDragError(null)
    } catch (err) {
      setDragError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
    try {
      await refetchRules()
    } catch (err) {
      setRulesError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      setReordering(false)
    }
  }

  function handleArmRule(rule: Rule) {
    setArmedRuleId(rule.rule_id)
    setPreArmOrder(rules)
    const index = rules.findIndex((r) => r.rule_id === rule.rule_id)
    setKeyboardAnnouncement(`Position ${index + 1} sur ${rules.length}`)
  }

  function handleKeyboardMove(direction: 'up' | 'down') {
    if (armedRuleId === null) return
    setRules((current) => {
      const index = current.findIndex((r) => r.rule_id === armedRuleId)
      if (index === -1) return current
      const targetIndex = direction === 'up' ? index - 1 : index + 1
      if (targetIndex < 0 || targetIndex >= current.length) return current
      const next = [...current]
      const [moved] = next.splice(index, 1)
      next.splice(targetIndex, 0, moved)
      setKeyboardAnnouncement(`Position ${targetIndex + 1} sur ${next.length}`)
      return next
    })
  }

  async function handleKeyboardCommit() {
    if (armedRuleId === null || reordering) return
    const orderedIds = rules.map((r) => r.rule_id)
    setArmedRuleId(null)
    setPreArmOrder(null)
    setReordering(true)
    try {
      await reorderRules(orderedIds)
    } catch (err) {
      setRulesError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
    try {
      await refetchRules()
    } catch (err) {
      setRulesError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      setReordering(false)
    }
  }

  function handleKeyboardCancel() {
    if (preArmOrder !== null) {
      setRules(preArmOrder)
    }
    setArmedRuleId(null)
    setPreArmOrder(null)
    setKeyboardAnnouncement('')
  }

  async function confirmRuleDelete() {
    if (ruleDeleteTarget === null) return
    setRuleDeleting(true)
    try {
      await deleteRule(ruleDeleteTarget.rule_id)
    } catch (err) {
      setRuleDeleteError(err instanceof Error ? err.message : 'Erreur inattendue')
      setRuleDeleting(false)
      return
    }
    setRuleDeleteTarget(null)
    setRuleDeleting(false)
    try {
      await refetchRules()
    } catch (err) {
      setRulesError(err instanceof Error ? err.message : 'Erreur inattendue')
    }
  }

  function openRuleDeleteConfirm(rule: Rule) {
    setRuleDeleteError(null)
    setRuleDeleteTarget(rule)
  }

  function handleRuleModalKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return
    const focusable = [
      ruleRetryButtonRef.current,
      ruleCancelButtonRef.current,
      ruleConfirmButtonRef.current,
    ].filter((el): el is HTMLButtonElement => el !== null)
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const tree = buildTree(tags)
  const targetBlocks = useMemo(() => buildTargetBlocks(tags, targetByTagId), [tags, targetByTagId])
  const tagsWithoutTarget = useMemo(
    () => tags.filter((t) => !targetByTagId.has(t.tag_id)),
    [tags, targetByTagId],
  )
  const editingTargetTag =
    targetFormMode === 'edit' && targetFormTagId !== ''
      ? tagById.get(Number(targetFormTagId))
      : undefined

  function renderCibleBlock(block: CibleBlock, depth: number, parentPercentage: number | null): ReactNode {
    const widthPct = depth === 0 ? 100 : (block.target.percentage / (parentPercentage as number)) * 100
    return (
      <div key={block.tag.tag_id}>
        <CibleRow
          tag={block.tag}
          percentage={block.target.percentage}
          amount={targetAmount(block.target.percentage, targetSummary?.total)}
          widthPct={widthPct}
          depth={depth}
          onEdit={() => startEditingTarget(block.target)}
          onDeleteConfirm={() => openTargetDeleteConfirm(block.target)}
        />
        {block.warning && (
          <p className="border-b border-border-subtle bg-alert-bg px-2 py-2 text-caption text-alert">
            La somme des Tags enfants (
            {block.children
              .map((c) => `${tagBreadcrumb(c.tag, tagById)} ${c.target.percentage}%`)
              .join(' + ')}{' '}
            = {block.sumChildren}%) dépasse la Cible du Tag parent {tagBreadcrumb(block.tag, tagById)} (
            {block.target.percentage}%).
          </p>
        )}
        {block.children.map((child) => renderCibleBlock(child, depth + 1, block.target.percentage))}
      </div>
    )
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-4 lg:px-7">
      <div
        inert={
          deleteTarget !== null ||
          ruleDeleteTarget !== null ||
          renameTarget !== null ||
          targetDeleteTarget !== null
        }
      >
        <h1 className="text-page-title font-bold text-ink">Budget</h1>

        <div className="mt-4 inline-flex rounded-lg border border-border bg-surface-panel p-0.5">
          <button
            type="button"
            onClick={() => setActiveTab('tags')}
            className={`rounded-md px-4 py-1.5 text-body-strong ${activeTab === 'tags' ? 'bg-ink text-surface' : 'text-ink-muted'}`}
          >
            Tags
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('rules')}
            className={`rounded-md px-4 py-1.5 text-body-strong ${activeTab === 'rules' ? 'bg-ink text-surface' : 'text-ink-muted'}`}
          >
            Règles
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('targets')}
            className={`rounded-md px-4 py-1.5 text-body-strong ${activeTab === 'targets' ? 'bg-ink text-surface' : 'text-ink-muted'}`}
          >
            Cibles
          </button>
        </div>

        {activeTab === 'tags' && (
          <div className="mt-6 overflow-hidden rounded border border-border">
            <div className="flex items-center justify-between border-b border-border bg-surface-panel px-4 py-3">
              <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
                Tags — arborescence
              </span>
              <button
                type="button"
                onClick={startAddingRoot}
                className="text-body-strong text-accent"
              >
                + Nouveau Tag racine
              </button>
            </div>

            <div className="px-0 py-1">
              {error && <p className="px-4 py-3 text-body text-alert">{error}</p>}

              {isAddingRoot && (
                <div className="flex flex-col gap-1 border-b border-border-subtle px-4 py-2">
                  <input
                    autoFocus
                    type="text"
                    placeholder="Nom du Tag"
                    value={newRootValue}
                    onChange={(e) => setNewRootValue(e.target.value)}
                    onKeyDown={handleAddRootKeyDown}
                    disabled={submittingRoot}
                    className={formFieldClass}
                  />
                  {addRootError && <p className="text-caption text-alert">{addRootError}</p>}
                </div>
              )}

              {loading && <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>}

              {!loading && !error && tree.length === 0 && !isAddingRoot && (
                <div className="flex flex-col gap-2 px-4 py-8 text-center">
                  <p className="text-body text-ink-muted">Aucun Tag pour l'instant.</p>
                  <button
                    type="button"
                    onClick={startAddingRoot}
                    className="self-center text-body-strong text-accent"
                  >
                    + Nouveau Tag racine
                  </button>
                </div>
              )}

              <div className="px-4">
                {tree.map((node) => (
                  <TagTreeRow
                    key={node.tag.tag_id}
                    node={node}
                    depth={0}
                    onRenameRequest={handleRenameRequest}
                    onAddChild={handleAddChild}
                    onDeleteConfirm={openDeleteConfirm}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'rules' && (
          <div className="mt-6 overflow-hidden rounded border border-border">
            <div className="flex items-center justify-between border-b border-border bg-surface-panel px-4 py-3">
              <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
                Règles d'auto-tagging — ordre d'évaluation
              </span>
              <button
                type="button"
                onClick={startAddingRule}
                className="text-body-strong text-accent"
              >
                + Nouvelle Règle
              </button>
            </div>

            <div className="px-0 py-1">
              <div aria-live="polite" className="sr-only">
                {keyboardAnnouncement}
              </div>

              {rulesError && <p className="px-4 py-3 text-body text-alert">{rulesError}</p>}
              {dragError && <p className="px-4 py-3 text-body text-alert">{dragError}</p>}

              {isAddingRule && (
                <div className="flex flex-col gap-2 border-b border-border-subtle px-4 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={newRuleConditionType}
                      onChange={(e) => setNewRuleConditionType(e.target.value as RuleConditionType)}
                      disabled={submittingRule}
                      className={formFieldClass}
                    >
                      <option value="label_contains">Libellé contient</option>
                      <option value="payee_exact">Tiers =</option>
                    </select>
                    <input
                      autoFocus
                      type="text"
                      placeholder="Valeur"
                      value={newRuleConditionValue}
                      onChange={(e) => setNewRuleConditionValue(e.target.value)}
                      onKeyDown={handleAddRuleValueKeyDown}
                      disabled={submittingRule}
                      className={formFieldClass}
                    />
                    <select
                      value={newRuleTagId}
                      onChange={(e) => setNewRuleTagId(e.target.value)}
                      disabled={submittingRule}
                      className={formFieldClass}
                    >
                      <option value="">Choisir un Tag…</option>
                      {tags.map((t) => (
                        <option key={t.tag_id} value={t.tag_id}>
                          {tagBreadcrumb(t, tagById)}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={submitAddRule}
                      disabled={submittingRule}
                      className="text-body-strong text-accent disabled:opacity-60"
                    >
                      Enregistrer
                    </button>
                  </div>
                  {addRuleError && <p className="text-caption text-alert">{addRuleError}</p>}
                </div>
              )}

              {rulesLoading && <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>}

              {!rulesLoading && !rulesError && rules.length === 0 && !isAddingRule && (
                <div className="flex flex-col gap-2 px-4 py-8 text-center">
                  <p className="text-body text-ink-muted">Aucune Règle pour l'instant.</p>
                  <button
                    type="button"
                    onClick={startAddingRule}
                    className="self-center text-body-strong text-accent"
                  >
                    + Nouvelle Règle
                  </button>
                </div>
              )}

              {rules.map((rule, index) => (
                <RuleRow
                  key={rule.rule_id}
                  rule={rule}
                  allTags={tags}
                  position={index + 1}
                  total={rules.length}
                  dragging={draggedId === rule.rule_id}
                  onDragStart={() => handleDragStart(rule.rule_id)}
                  onDragEnter={() => handleDragEnter(rule.rule_id)}
                  onDragEnd={handleDragEnd}
                  onKeyboardMove={handleKeyboardMove}
                  onKeyboardCommit={handleKeyboardCommit}
                  onKeyboardCancel={handleKeyboardCancel}
                  armed={armedRuleId === rule.rule_id}
                  onArm={() => handleArmRule(rule)}
                  onEdit={handleEditRule}
                  onDeleteConfirm={openRuleDeleteConfirm}
                />
              ))}
            </div>
          </div>
        )}

        {activeTab === 'targets' && (
          <div className="mt-6 overflow-hidden rounded border border-border">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-panel px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-section-title font-bold uppercase tracking-wide text-ink-muted">
                  Cibles budgétaires
                </span>
                {personalAccounts.length > 0 && (
                  <select
                    value={selectedTargetAccountId ?? ''}
                    onChange={(e) => setSelectedTargetAccountId(Number(e.target.value))}
                    className={formFieldClass}
                  >
                    {personalAccounts.map((a) => (
                      <option key={a.account_id} value={a.account_id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                )}
                {targetSummary && (
                  <span className="text-caption text-ink-muted">
                    Revenus {formatMontant(targetSummary.total)}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={startAddingTarget}
                disabled={selectedTargetAccount === null}
                className="text-body-strong text-accent disabled:opacity-60"
              >
                + Assigner une Cible
              </button>
            </div>

            <div className="px-0 py-1">
              {accountsError && <p className="px-4 py-3 text-body text-alert">{accountsError}</p>}
              {targetsError && <p className="px-4 py-3 text-body text-alert">{targetsError}</p>}

              {isAddingTarget && (
                <div className="flex flex-col gap-2 border-b border-border-subtle px-4 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={targetFormTagId}
                      onChange={(e) => setTargetFormTagId(e.target.value)}
                      disabled={submittingTarget || targetFormMode === 'edit'}
                      className={formFieldClass}
                    >
                      <option value="">Choisir un Tag…</option>
                      {targetFormMode === 'edit' && editingTargetTag && (
                        <option value={editingTargetTag.tag_id}>
                          {tagBreadcrumb(editingTargetTag, tagById)}
                        </option>
                      )}
                      {targetFormMode === 'create' &&
                        tagsWithoutTarget.map((t) => (
                          <option key={t.tag_id} value={t.tag_id}>
                            {tagBreadcrumb(t, tagById)}
                          </option>
                        ))}
                    </select>
                    <input
                      autoFocus
                      type="number"
                      step="0.01"
                      min="0"
                      max="100"
                      placeholder="%"
                      value={targetFormPercentage}
                      onChange={(e) => setTargetFormPercentage(e.target.value)}
                      onKeyDown={handleTargetFormKeyDown}
                      disabled={submittingTarget}
                      className={formFieldClass}
                    />
                    <button
                      type="button"
                      onClick={submitTargetForm}
                      disabled={submittingTarget}
                      className="text-body-strong text-accent disabled:opacity-60"
                    >
                      Enregistrer
                    </button>
                  </div>
                  {targetFormError && <p className="text-caption text-alert">{targetFormError}</p>}
                </div>
              )}

              {targetsLoading && (
                <p className="px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
              )}

              {!targetsLoading &&
                !targetsError &&
                selectedTargetAccount !== null &&
                targetBlocks.length === 0 &&
                !isAddingTarget && (
                  <div className="flex flex-col gap-2 px-4 py-8 text-center">
                    <p className="text-body text-ink-muted">Aucune Cible pour l'instant.</p>
                    <button
                      type="button"
                      onClick={startAddingTarget}
                      className="self-center text-body-strong text-accent"
                    >
                      + Assigner une Cible
                    </button>
                  </div>
                )}

              <div className="px-4">
                {targetBlocks.map((block) => renderCibleBlock(block, 0, null))}
              </div>
            </div>
          </div>
        )}
      </div>

      {deleteTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-tag-modal-title"
            onKeyDown={handleModalKeyDown}
            className="w-full max-w-sm rounded border border-border bg-surface p-4"
          >
            <p id="delete-tag-modal-title" className="text-body-strong text-ink">
              Supprimer le Tag « {deleteTarget.name} » ?
            </p>
            {deleteError && (
              <div className="mt-2 flex flex-col gap-2">
                <p className="text-body text-alert">{deleteError}</p>
                <button
                  ref={retryButtonRef}
                  type="button"
                  onClick={confirmDelete}
                  className="self-start text-body-strong text-alert underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                ref={cancelButtonRef}
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="rounded border border-border px-3 py-2 text-body text-ink disabled:opacity-60"
              >
                Annuler
              </button>
              <button
                ref={confirmButtonRef}
                type="button"
                onClick={confirmDelete}
                disabled={deleting}
                className="rounded bg-alert px-3 py-2 text-body-strong text-surface disabled:opacity-60"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}

      {ruleDeleteTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-rule-modal-title"
            onKeyDown={handleRuleModalKeyDown}
            className="w-full max-w-sm rounded border border-border bg-surface p-4"
          >
            <p id="delete-rule-modal-title" className="text-body-strong text-ink">
              Supprimer cette Règle ?
            </p>
            {ruleDeleteError && (
              <div className="mt-2 flex flex-col gap-2">
                <p className="text-body text-alert">{ruleDeleteError}</p>
                <button
                  ref={ruleRetryButtonRef}
                  type="button"
                  onClick={confirmRuleDelete}
                  className="self-start text-body-strong text-alert underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                ref={ruleCancelButtonRef}
                type="button"
                onClick={() => setRuleDeleteTarget(null)}
                disabled={ruleDeleting}
                className="rounded border border-border px-3 py-2 text-body text-ink disabled:opacity-60"
              >
                Annuler
              </button>
              <button
                ref={ruleConfirmButtonRef}
                type="button"
                onClick={confirmRuleDelete}
                disabled={ruleDeleting}
                className="rounded bg-alert px-3 py-2 text-body-strong text-surface disabled:opacity-60"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}

      {renameTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="rename-tag-modal-title"
            onKeyDown={handleRenameModalKeyDown}
            className="w-full max-w-sm rounded border border-border bg-surface p-4"
          >
            <p id="rename-tag-modal-title" className="text-body-strong text-ink">
              Cette opération est irréversible — renommer ce tag sur {renameTarget.count}{' '}
              transaction{renameTarget.count > 1 ? 's' : ''} ?
            </p>
            {renameError && (
              <div className="mt-2 flex flex-col gap-2">
                <p className="text-body text-alert">{renameError}</p>
                <button
                  ref={renameRetryButtonRef}
                  type="button"
                  onClick={confirmRename}
                  className="self-start text-body-strong text-alert underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                ref={renameCancelButtonRef}
                type="button"
                onClick={() => setRenameTarget(null)}
                disabled={renaming}
                className="min-h-11 rounded border border-border px-3 py-2 text-body text-ink disabled:opacity-60"
              >
                Annuler
              </button>
              <button
                ref={renameConfirmButtonRef}
                type="button"
                onClick={confirmRename}
                disabled={renaming}
                className="min-h-11 rounded bg-alert px-3 py-2 text-body-strong text-surface disabled:opacity-60"
              >
                Renommer
              </button>
            </div>
          </div>
        </div>
      )}

      {targetDeleteTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-target-modal-title"
            onKeyDown={handleTargetModalKeyDown}
            className="w-full max-w-sm rounded border border-border bg-surface p-4"
          >
            <p id="delete-target-modal-title" className="text-body-strong text-ink">
              Supprimer cette Cible ?
            </p>
            {targetDeleteError && (
              <div className="mt-2 flex flex-col gap-2">
                <p className="text-body text-alert">{targetDeleteError}</p>
                <button
                  ref={targetRetryButtonRef}
                  type="button"
                  onClick={confirmTargetDelete}
                  className="self-start text-body-strong text-alert underline"
                >
                  Réessayer
                </button>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                ref={targetCancelButtonRef}
                type="button"
                onClick={() => setTargetDeleteTarget(null)}
                disabled={targetDeleting}
                className="rounded border border-border px-3 py-2 text-body text-ink disabled:opacity-60"
              >
                Annuler
              </button>
              <button
                ref={targetConfirmButtonRef}
                type="button"
                onClick={confirmTargetDelete}
                disabled={targetDeleting}
                className="rounded bg-alert px-3 py-2 text-body-strong text-surface disabled:opacity-60"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

export default Budget
