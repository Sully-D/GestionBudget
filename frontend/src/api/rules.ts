import { unwrap } from './http'

export type RuleConditionType = 'label_contains' | 'payee_exact'

export interface Rule {
  rule_id: number
  condition_type: RuleConditionType
  condition_value: string
  tag_id: number
  sort_order: number
}

export interface RuleCreatePayload {
  condition_type: RuleConditionType
  condition_value: string
  tag_id: number
}

export type RuleUpdatePayload = RuleCreatePayload

export async function getRules(): Promise<Rule[]> {
  const response = await fetch('/rules')
  return unwrap<Rule[]>(response)
}

export async function createRule(payload: RuleCreatePayload): Promise<Rule> {
  const response = await fetch('/rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Rule>(response)
}

export async function updateRule(ruleId: number, payload: RuleUpdatePayload): Promise<Rule> {
  const response = await fetch(`/rules/${ruleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Rule>(response)
}

export async function deleteRule(ruleId: number): Promise<void> {
  const response = await fetch(`/rules/${ruleId}`, { method: 'DELETE' })
  await unwrap<null>(response)
}

export async function reorderRules(ruleIds: number[]): Promise<Rule[]> {
  const response = await fetch('/rules/reorder', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rule_ids: ruleIds }),
  })
  return unwrap<Rule[]>(response)
}

export interface RuleEvaluateResult {
  tag_id: number | null
  condition_type: RuleConditionType | null
  condition_value: string | null
}

export async function evaluateRules(
  label: string,
  payee: string | null,
): Promise<RuleEvaluateResult> {
  const response = await fetch('/rules/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label, payee }),
  })
  return unwrap<RuleEvaluateResult>(response)
}
