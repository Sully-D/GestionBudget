import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getAccounts } from '../api/accounts'
import type { Account } from '../api/accounts'
import { getDisponibleEvolution, getTagSpending, getTagTracking } from '../api/budget'
import type { Disponible, TagSpending, TagTracking } from '../api/budget'
import { getProjection } from '../api/projections'
import type { ProjectionItem } from '../api/projections'
import { getTransactions } from '../api/transactions'
import AccountCard from '../components/AccountCard'
import { formatDate, formatMontant, shiftDate } from '../lib/format'

// Ordre catégoriel fixe (jamais cyclé), validé CVD/contraste — voir index.css.
const CATEGORICAL_COLORS = [
  'var(--chart-cat-1)',
  'var(--chart-cat-2)',
  'var(--chart-cat-3)',
  'var(--chart-cat-4)',
  'var(--chart-cat-5)',
  'var(--chart-cat-6)',
]
const AUTRES_COLOR = 'var(--color-ink-faint)'

const tooltipStyle = {
  backgroundColor: 'var(--color-surface-panel)',
  border: '1px solid var(--color-border)',
  borderRadius: 6,
  fontSize: 12.5,
  color: 'var(--color-ink)',
}
const axisTick = { fill: 'var(--color-ink-muted)', fontSize: 10.5 }

interface PieSlice {
  key: string
  name: string
  value: number
  color: string
}

// Seuls les tags racine (parent_id null) entrent dans le camembert : le "spent"
// d'un tag parent inclut déjà celui de ses descendants (rollup serveur), les
// additionner aux enfants doublerait la part de chaque branche. Le netting
// sans plancher peut rendre le "spent" d'un tag nul ou négatif (remboursements
// > dépenses) : un camembert ne représente pas de part négative, ces tags sont
// exclus plutôt que de produire une part invalide ou un "Autres" tronqué.
// Couleur assignée par tag_id (stable dans le temps), pas par rang affiché
// (qui varie d'une période à l'autre selon les montants).
function buildPieSlices(tagSpending: TagSpending[]): PieSlice[] {
  const roots = tagSpending
    .filter((r) => r.parent_id === null && r.spent > 0)
    .sort((a, b) => b.spent - a.spent)
  const top = roots.slice(0, CATEGORICAL_COLORS.length)
  const rest = roots.slice(CATEGORICAL_COLORS.length).reduce((sum, r) => sum + r.spent, 0)
  const topSlices: PieSlice[] = top.map((r) => ({
    key: `tag-${r.tag_id}`,
    name: r.tag_name,
    value: r.spent,
    color: CATEGORICAL_COLORS[r.tag_id % CATEGORICAL_COLORS.length],
  }))
  return rest > 0
    ? [...topSlices, { key: 'autres', name: 'Autres', value: rest, color: AUTRES_COLOR }]
    : topSlices
}

interface CumulativePoint {
  date: string
  total: number
}

// Ancré sur le disponible courant (dernière entrée de l'évolution du
// disponible) plutôt que sur 0, pour représenter une trajectoire de
// trésorerie réelle et non un simple delta flottant sans repère.
function buildCumulativeProjection(items: ProjectionItem[], startingBalance: number): CumulativePoint[] {
  const sorted = [...items].sort((a, b) => a.date.localeCompare(b.date))
  let running = startingBalance
  return sorted.map((item) => {
    running += item.amount
    return { date: item.date, total: running }
  })
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded border border-border bg-surface p-4">
      <h2 className="text-label uppercase text-ink-muted">{title}</h2>
      <div className="mt-4 h-64">{children}</div>
    </section>
  )
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Erreur inattendue'
}

function Synthese() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountsError, setAccountsError] = useState<string | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)

  const [referenceDate, setReferenceDate] = useState<string | undefined>(undefined)
  const [periodStart, setPeriodStart] = useState<string | null>(null)
  const [periodEnd, setPeriodEnd] = useState<string | null>(null)
  const [periodLoading, setPeriodLoading] = useState(false)
  const [periodError, setPeriodError] = useState<string | null>(null)

  const [tagSpending, setTagSpending] = useState<TagSpending[]>([])
  const [tagSpendingError, setTagSpendingError] = useState<string | null>(null)

  const [tagTracking, setTagTracking] = useState<TagTracking[]>([])
  const [tagTrackingError, setTagTrackingError] = useState<string | null>(null)

  const [projection, setProjection] = useState<ProjectionItem[]>([])
  const [projectionError, setProjectionError] = useState<string | null>(null)

  const [disponibleEvolution, setDisponibleEvolution] = useState<Disponible[]>([])
  const [disponibleEvolutionError, setDisponibleEvolutionError] = useState<string | null>(null)

  useEffect(() => {
    getAccounts()
      .then((data) => {
        setAccounts(data)
        setSelectedAccountId(
          (current) => current ?? data.find((a) => !a.is_common)?.account_id ?? data[0]?.account_id ?? null,
        )
        setAccountsError(null)
      })
      .catch((err) => {
        setAccountsError(errorMessage(err))
      })
  }, [])

  const selectedAccount = accounts.find((a) => a.account_id === selectedAccountId) ?? null

  // Changer de Compte réinitialise la Période affichée — ajustement pendant le
  // rendu, même pattern que Comparaison.tsx/Dashboard.tsx.
  const [previousAccountId, setPreviousAccountId] = useState(selectedAccountId)
  if (selectedAccountId !== previousAccountId) {
    setPreviousAccountId(selectedAccountId)
    setReferenceDate(undefined)
  }

  // Graphiques mono-période : répartition par tag (tout compte), réel vs cible
  // et projection (comptes personnels uniquement, cf. CAP-6).
  useEffect(() => {
    setPeriodStart(null)
    setPeriodEnd(null)
    setPeriodError(null)
    setTagSpending([])
    setTagSpendingError(null)
    setTagTracking([])
    setTagTrackingError(null)
    setProjection([])
    setProjectionError(null)

    if (!selectedAccount) return

    let cancelled = false
    setPeriodLoading(true)

    getTransactions(selectedAccount.account_id, referenceDate)
      .then((result) => {
        if (cancelled) return
        setPeriodStart(result.period_start)
        setPeriodEnd(result.period_end)
        setPeriodError(null)

        const targetPeriodStart = referenceDate ?? selectedAccount.period_start

        getTagSpending(selectedAccount.account_id, targetPeriodStart)
          .then((data) => {
            if (!cancelled) setTagSpending(data)
          })
          .catch((err) => {
            if (!cancelled) setTagSpendingError(errorMessage(err))
          })

        if (!selectedAccount.is_common) {
          getTagTracking(selectedAccount.account_id, targetPeriodStart)
            .then((data) => {
              if (!cancelled) setTagTracking(data)
            })
            .catch((err) => {
              if (!cancelled) setTagTrackingError(errorMessage(err))
            })

          getProjection(selectedAccount.account_id)
            .then((data) => {
              if (!cancelled) setProjection(data)
            })
            .catch((err) => {
              if (!cancelled) setProjectionError(errorMessage(err))
            })
        }
      })
      .catch((err) => {
        if (!cancelled) setPeriodError(errorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setPeriodLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedAccount, referenceDate])

  // Évolution du disponible : fenêtre fixe de 6 mois glissants, indépendante de
  // la Période affichée (CAP-5) — ne dépend que du Compte sélectionné.
  useEffect(() => {
    setDisponibleEvolution([])
    setDisponibleEvolutionError(null)

    if (!selectedAccount || selectedAccount.is_common) return

    let cancelled = false
    getDisponibleEvolution(selectedAccount.account_id)
      .then((data) => {
        if (!cancelled) setDisponibleEvolution(data)
      })
      .catch((err) => {
        if (!cancelled) setDisponibleEvolutionError(errorMessage(err))
      })

    return () => {
      cancelled = true
    }
  }, [selectedAccount])

  function goToPreviousPeriod() {
    if (periodStart) setReferenceDate(shiftDate(periodStart, -1))
  }
  function goToNextPeriod() {
    if (periodEnd) setReferenceDate(shiftDate(periodEnd, 1))
  }

  const pieSlices = buildPieSlices(tagSpending)
  const trackingRows = tagTracking.filter((r) => r.parent_id === null && r.target_amount !== null)
  const currentDisponible = disponibleEvolution.at(-1)?.disponible ?? 0
  const cumulativeProjection = buildCumulativeProjection(projection, currentDisponible)

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-4 lg:px-7">
      <h1 className="text-title font-bold text-ink">Synthèse</h1>

      {accountsError && <p className="mt-4 text-body text-alert">{accountsError}</p>}

      {selectedAccount && (
        <div className="mt-6 flex items-center justify-between gap-2">
          <span className="text-label uppercase text-ink-muted">Période</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={goToPreviousPeriod}
              aria-label="Période précédente"
              className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
            >
              ‹
            </button>
            <span className="text-body text-ink">
              {periodStart && periodEnd ? `${formatDate(periodStart)} – ${formatDate(periodEnd)}` : ''}
            </span>
            <button
              type="button"
              onClick={goToNextPeriod}
              aria-label="Période suivante"
              className="rounded border border-border px-2 py-1 text-body text-ink-muted hover:text-ink"
            >
              ›
            </button>
          </div>
        </div>
      )}

      {selectedAccount && periodLoading && (
        <p className="mt-6 px-4 py-8 text-center text-body text-ink-muted">Chargement…</p>
      )}

      {selectedAccount && !periodLoading && periodError && <p className="mt-4 text-body text-alert">{periodError}</p>}

      {selectedAccount && !periodLoading && !periodError && (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <ChartCard title="Répartition des dépenses par tag">
            {tagSpendingError ? (
              <p className="text-body text-alert">{tagSpendingError}</p>
            ) : pieSlices.length === 0 ? (
              <p className="text-body text-ink-muted">Aucune dépense taguée sur cette Période.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieSlices}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={50}
                    outerRadius={90}
                    paddingAngle={2}
                    label={(props: { name?: string; value?: number }) =>
                      `${props.name ?? ''} : ${formatMontant(props.value ?? 0)}`
                    }
                  >
                    {pieSlices.map((slice) => (
                      <Cell key={slice.key} fill={slice.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} formatter={(value: number) => formatMontant(value)} />
                  <Legend wrapperStyle={{ fontSize: 11, color: 'var(--color-ink-muted)' }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          {!selectedAccount.is_common && (
            <ChartCard title="Réel vs cible par tag">
              {tagTrackingError ? (
                <p className="text-body text-alert">{tagTrackingError}</p>
              ) : trackingRows.length === 0 ? (
                <p className="text-body text-ink-muted">Aucune cible budgétaire définie.</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height="85%">
                    <BarChart data={trackingRows} margin={{ left: 0, right: 8 }}>
                      <CartesianGrid stroke="var(--color-border-subtle)" vertical={false} />
                      <XAxis dataKey="tag_name" tick={axisTick} />
                      <YAxis tick={axisTick} />
                      <Tooltip contentStyle={tooltipStyle} formatter={(value: number) => formatMontant(value)} />
                      <Bar dataKey="target_amount" name="Cible" fill="var(--color-border)" radius={[4, 4, 0, 0]} maxBarSize={24} />
                      <Bar dataKey="spent" name="Réel" radius={[4, 4, 0, 0]} maxBarSize={24}>
                        {trackingRows.map((row) => (
                          <Cell
                            key={row.tag_id}
                            fill={
                              row.target_amount !== null && row.spent > row.target_amount
                                ? 'var(--color-alert)'
                                : 'var(--color-positive)'
                            }
                          />
                        ))}
                        <LabelList
                          dataKey="spent"
                          position="top"
                          formatter={(value: number) => formatMontant(value)}
                          style={{ fill: 'var(--color-ink-muted)', fontSize: 10 }}
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="mt-2 flex items-center gap-4 text-caption text-ink-muted">
                    <span className="inline-flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: 'var(--color-positive)' }} />
                      Sous cible
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: 'var(--color-alert)' }} />
                      Au-dessus
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: 'var(--color-border)' }} />
                      Cible
                    </span>
                  </div>
                </>
              )}
            </ChartCard>
          )}

          {!selectedAccount.is_common && (
            <ChartCard title="Projection de trésorerie">
              {projectionError ? (
                <p className="text-body text-alert">{projectionError}</p>
              ) : cumulativeProjection.length === 0 ? (
                <p className="text-body text-ink-muted">Aucun événement de projection.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={cumulativeProjection}>
                    <CartesianGrid stroke="var(--color-border-subtle)" vertical={false} />
                    <XAxis dataKey="date" tickFormatter={formatDate} tick={axisTick} />
                    <YAxis tick={axisTick} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelFormatter={(value: string) => formatDate(value)}
                      formatter={(value: number) => formatMontant(value)}
                    />
                    <Area
                      type="monotone"
                      dataKey="total"
                      name="Disponible projeté"
                      stroke="var(--color-accent)"
                      strokeWidth={2}
                      fill="var(--color-accent)"
                      fillOpacity={0.1}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          )}

          {!selectedAccount.is_common && (
            <ChartCard title="Évolution du disponible (6 derniers mois)">
              {disponibleEvolutionError ? (
                <p className="text-body text-alert">{disponibleEvolutionError}</p>
              ) : disponibleEvolution.length === 0 ? (
                <p className="text-body text-ink-muted">Chargement…</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={disponibleEvolution}>
                    <CartesianGrid stroke="var(--color-border-subtle)" vertical={false} />
                    <XAxis dataKey="period_start" tickFormatter={formatDate} tick={axisTick} />
                    <YAxis tick={axisTick} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelFormatter={(value: string) => formatDate(value)}
                      formatter={(value: number) => formatMontant(value)}
                    />
                    <Line
                      type="monotone"
                      dataKey="disponible"
                      name="Disponible"
                      stroke="var(--color-accent)"
                      strokeWidth={2}
                      dot={{ r: 4, fill: 'var(--color-accent)', stroke: 'var(--color-surface)', strokeWidth: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          )}

          {selectedAccount.is_common && (
            <div className="rounded border border-border bg-surface-panel p-4 text-body text-ink-muted lg:col-span-2">
              Réel vs cible, projection de trésorerie et évolution du disponible ne sont disponibles que pour un
              compte personnel.
            </div>
          )}
        </div>
      )}

      <div className="mt-8 flex flex-col gap-3">
        {accounts.map((account) => (
          <AccountCard
            key={account.account_id}
            account={account}
            selected={account.account_id === selectedAccountId}
            onSelect={setSelectedAccountId}
          />
        ))}
      </div>
    </main>
  )
}

export default Synthese
