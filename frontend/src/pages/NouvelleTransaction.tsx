import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { evaluateRules } from '../api/rules'
import type { RuleEvaluateResult } from '../api/rules'
import { getTags } from '../api/tags'
import type { Tag } from '../api/tags'
import {
  addTransactionTag,
  createTransaction,
  getTransaction,
  updateTransaction,
} from '../api/transactions'
import type { TagSummary } from '../api/transactions'
import TagSuggestionChip from '../components/TagSuggestionChip'
import TransactionTagEditor from '../components/TransactionTagEditor'
import { formatMontant } from '../lib/format'

const formFieldClass =
  'rounded border border-border bg-surface-panel px-3 py-2 text-body text-ink focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_rgba(37,99,235,0.12)]'

type Sign = 'depense' | 'revenu'

function todayIso(): string {
  // Composants de date locaux (comme `shiftDate`), pas `toISOString()` qui est
  // en UTC : sinon la date pré-remplie peut être décalée d'un jour près de
  // minuit pour un utilisateur qui n'est pas sur UTC.
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

interface TransactionFormProps {
  // Absent = mode création (formulaire de saisie rapide). Présent = mode
  // édition d'une Transaction existante : le compte n'est alors plus modifiable
  // (AC #1 de la Story 1.4 ne liste que date/montant/Libellé/Tiers).
  transactionId?: number
}

export function TransactionForm({ transactionId }: TransactionFormProps) {
  const isEditMode = transactionId !== undefined
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountId, setAccountId] = useState<number | null>(null)
  const [date, setDate] = useState(todayIso())
  const [amountValue, setAmountValue] = useState('')
  const [sign, setSign] = useState<Sign>('depense')
  const [label, setLabel] = useState('')
  const [payee, setPayee] = useState('')
  const [amountError, setAmountError] = useState<string | null>(null)
  const [labelError, setLabelError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadingTransaction, setLoadingTransaction] = useState(isEditMode)
  const [allTags, setAllTags] = useState<Tag[]>([])
  const [allTagsLoading, setAllTagsLoading] = useState(true)
  const [transactionTags, setTransactionTags] = useState<TagSummary[]>([])
  const [suggestedResult, setSuggestedResult] = useState<RuleEvaluateResult | null>(null)
  const [manualTagId, setManualTagId] = useState<number | null>(null)
  const [tagManuallySet, setTagManuallySet] = useState(false)
  const [suggestionPending, setSuggestionPending] = useState(false)
  const [tagAssociationRetry, setTagAssociationRetry] = useState<{
    transactionId: number
    tagId: number
  } | null>(null)
  const amountInputRef = useRef<HTMLInputElement>(null)
  const labelInputRef = useRef<HTMLInputElement>(null)
  const navigatedAwayRef = useRef(false)
  const suggestionRequestIdRef = useRef(0)
  // Ref (pas seulement le state `submitting`) car deux soumissions quasi
  // simultanées (double clic/Entrée) peuvent toutes deux lire l'ancien state
  // avant qu'un premier re-rendu n'ait eu lieu — le ref est à jour immédiatement.
  const submittingRef = useRef(false)

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        if (!isEditMode) {
          setAccountId((current) => current ?? data[0]?.account_id ?? null)
        }
      })
      .catch((err) => {
        setSubmitError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
  }, [isEditMode])

  useEffect(() => {
    if (!isEditMode || transactionId === undefined) return
    let cancelled = false
    setLoadingTransaction(true)
    getTransaction(transactionId)
      .then((transaction) => {
        if (cancelled) return
        setAccountId(transaction.account_id)
        setDate(transaction.date)
        setAmountValue(Math.abs(transaction.amount).toString())
        setSign(transaction.amount < 0 ? 'depense' : 'revenu')
        setLabel(transaction.label)
        setPayee(transaction.payee ?? '')
        setTransactionTags(transaction.tags)
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => {
        if (!cancelled) setLoadingTransaction(false)
      })
    return () => {
      cancelled = true
    }
  }, [isEditMode, transactionId])

  useEffect(() => {
    setAllTagsLoading(true)
    getTags()
      .then(setAllTags)
      .catch((err) => {
        setSubmitError(err instanceof Error ? err.message : 'Erreur inattendue')
      })
      .finally(() => setAllTagsLoading(false))
  }, [])

  useEffect(() => {
    if (isEditMode || tagManuallySet) {
      setSuggestionPending(false)
      return
    }
    setSuggestionPending(true)
    const timeoutId = window.setTimeout(() => {
      const requestId = ++suggestionRequestIdRef.current
      evaluateRules(label.trim(), payee.trim() || null)
        .then((result) => {
          // Ignore une réponse obsolète si une saisie plus récente a déjà
          // déclenché un nouvel appel entretemps (résolution hors-ordre).
          if (suggestionRequestIdRef.current === requestId) {
            setSuggestedResult(result)
          }
        })
        .catch(() => {
          // Suggestion non bloquante : un échec réseau équivaut à « aucune correspondance ».
        })
        .finally(() => {
          if (suggestionRequestIdRef.current === requestId) {
            setSuggestionPending(false)
          }
        })
    }, 300)
    return () => window.clearTimeout(timeoutId)
  }, [label, payee, isEditMode, tagManuallySet])

  useEffect(() => {
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        navigatedAwayRef.current = true
        navigate(-1)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [navigate])

  const parsedMagnitude = Number(amountValue.replace(',', '.'))
  const isAmountValid = amountValue.trim() !== '' && Number.isFinite(parsedMagnitude)
  const magnitude = isAmountValid ? parsedMagnitude : 0
  const signedAmount = sign === 'depense' ? -Math.abs(magnitude) : Math.abs(magnitude)

  const effectiveTagId = tagManuallySet ? manualTagId : (suggestedResult?.tag_id ?? null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (submittingRef.current) return
    // Un précédent échec d'association de Tag laisse la Transaction déjà créée
    // (tagAssociationRetry) : resoumettre le formulaire entier créerait un
    // doublon. Le bouton "Valider" principal reste actif (l'utilisateur peut
    // presser Entrée ou cliquer dessus par réflexe plutôt que sur le lien
    // "Réessayer" dédié) — router systématiquement vers le retry ciblé.
    if (tagAssociationRetry !== null) {
      await retryTagAssociation()
      return
    }
    setSubmitError(null)
    setTagAssociationRetry(null)

    if (loadingTransaction) {
      setSubmitError('Chargement de la transaction en cours, réessayez dans un instant.')
      return
    }

    if (!isAmountValid) {
      setAmountError('Le Montant est obligatoire.')
      amountInputRef.current?.focus()
      return
    }
    setAmountError(null)

    if (label.trim() === '') {
      setLabelError('Le Libellé est obligatoire.')
      labelInputRef.current?.focus()
      return
    }
    setLabelError(null)

    if (accountId === null) {
      setSubmitError('Aucun compte disponible.')
      return
    }

    submittingRef.current = true
    setSubmitting(true)
    try {
      if (isEditMode) {
        await updateTransaction(transactionId, {
          date,
          amount: signedAmount,
          label: label.trim(),
          ...(payee.trim() !== '' ? { payee: payee.trim() } : {}),
        })
      } else {
        const newTransaction = await createTransaction({
          account_id: accountId,
          date,
          amount: signedAmount,
          label: label.trim(),
          ...(payee.trim() !== '' ? { payee: payee.trim() } : {}),
        })
        if (effectiveTagId !== null) {
          try {
            await addTransactionTag(newTransaction.transaction_id, effectiveTagId)
          } catch {
            setTagAssociationRetry({ transactionId: newTransaction.transaction_id, tagId: effectiveTagId })
            setSubmitError(
              "Transaction enregistrée, mais le Tag n'a pas pu être associé — ajoutez-le depuis la page de modification.",
            )
            return
          }
        }
      }
      // Si l'utilisateur a déjà quitté la page via Échap pendant que la
      // requête était en vol, ne pas le re-déplacer vers /transactions.
      if (!navigatedAwayRef.current) {
        navigate('/transactions')
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  // Ne réessaie que l'association du Tag sur la Transaction déjà créée —
  // ne resoumet jamais le formulaire entier (éviterait de créer un doublon).
  async function retryTagAssociation() {
    if (tagAssociationRetry === null || submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      await addTransactionTag(tagAssociationRetry.transactionId, tagAssociationRetry.tagId)
      setTagAssociationRetry(null)
      setSubmitError(null)
      if (!navigatedAwayRef.current) {
        navigate('/transactions')
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur inattendue')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  const accountName = accounts.find((account) => account.account_id === accountId)?.name ?? ''

  return (
    <main className="mx-auto max-w-md px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-page-title font-bold text-ink">
        {isEditMode ? 'Modifier la transaction' : 'Nouvelle transaction'}
      </h1>

      {loadError && (
        <div className="mt-4 flex flex-col gap-2">
          <p className="text-body text-alert">{loadError}</p>
          <Link to="/transactions" className="self-start text-body-strong text-accent underline">
            Retour aux transactions
          </Link>
        </div>
      )}

      {!loadError && (
        <form
          onSubmit={handleSubmit}
          className="mt-4 flex flex-col gap-4 rounded border border-border bg-surface p-4"
        >
          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Montant</span>
            <input
              ref={amountInputRef}
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={amountValue}
              onChange={(e) => {
                setAmountValue(e.target.value)
                if (e.target.value.trim() !== '') {
                  setAmountError(null)
                }
              }}
              aria-invalid={amountError !== null}
              aria-describedby={amountError !== null ? 'amount-error' : undefined}
              className={`${formFieldClass} font-mono text-montant-input`}
            />
            {amountError && (
              <span id="amount-error" className="text-caption text-alert">
                {amountError}
              </span>
            )}
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => setSign('depense')}
                className={`rounded-full border px-3 py-1 text-caption font-bold ${
                  sign === 'depense'
                    ? 'border-alert-border bg-alert-bg text-alert'
                    : 'border-border text-ink-muted'
                }`}
              >
                Dépense
              </button>
              <button
                type="button"
                onClick={() => setSign('revenu')}
                className={`rounded-full border px-3 py-1 text-caption font-bold ${
                  sign === 'revenu'
                    ? 'border-accent-border bg-accent-bg text-accent'
                    : 'border-border text-ink-muted'
                }`}
              >
                Revenu
              </button>
            </div>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Date</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className={formFieldClass}
            />
          </label>

          {isEditMode ? (
            <div className="flex flex-col gap-1">
              <span className="text-label text-ink-muted">Compte</span>
              <span className="text-body text-ink-muted">{accountName}</span>
            </div>
          ) : (
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
          )}

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">Libellé</span>
            <input
              ref={labelInputRef}
              type="text"
              value={label}
              onChange={(e) => {
                setLabel(e.target.value)
                if (e.target.value.trim() !== '') {
                  setLabelError(null)
                }
              }}
              aria-invalid={labelError !== null}
              aria-describedby={labelError !== null ? 'label-error' : undefined}
              className={formFieldClass}
            />
            {labelError && (
              <span id="label-error" className="text-caption text-alert">
                {labelError}
              </span>
            )}
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-label text-ink-muted">
              Tiers <span className="normal-case text-ink-faint">(optionnel)</span>
            </span>
            <input
              type="text"
              value={payee}
              onChange={(e) => setPayee(e.target.value)}
              className={formFieldClass}
            />
          </label>

          {isEditMode && transactionId !== undefined && (
            <TransactionTagEditor
              transactionId={transactionId}
              tags={transactionTags}
              allTags={allTags}
              allTagsLoading={allTagsLoading}
              onTagsChange={setTransactionTags}
            />
          )}

          {!isEditMode && (
            <label className="flex flex-col gap-1">
              <span className="text-label text-ink-muted">Tag</span>
              <TagSuggestionChip
                selectedTagId={effectiveTagId}
                isSuggestion={!tagManuallySet && suggestedResult?.tag_id != null}
                matchedRule={
                  suggestedResult?.condition_type
                    ? {
                        condition_type: suggestedResult.condition_type,
                        condition_value: suggestedResult.condition_value ?? '',
                      }
                    : null
                }
                allTags={allTags}
                allTagsLoading={allTagsLoading}
                onChange={(tagId) => {
                  setManualTagId(tagId)
                  setTagManuallySet(true)
                }}
              />
            </label>
          )}

          {submitError && (
            <div className="flex flex-col gap-2 rounded border border-alert-border bg-alert-bg p-3">
              <p className="text-body text-alert">{submitError}</p>
              <button
                type={tagAssociationRetry ? 'button' : 'submit'}
                onClick={tagAssociationRetry ? retryTagAssociation : undefined}
                disabled={submitting}
                className="self-start text-body-strong text-alert underline disabled:opacity-60"
              >
                Réessayer
              </button>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || loadingTransaction || (!isEditMode && suggestionPending)}
            className="rounded-lg bg-accent px-4 py-3 text-body-strong text-surface shadow-[0_6px_16px_rgba(37,99,235,0.35)] disabled:opacity-60"
          >
            Valider — {formatMontant(signedAmount)}
          </button>
        </form>
      )}
    </main>
  )
}

function NouvelleTransaction() {
  return <TransactionForm />
}

export default NouvelleTransaction
