import { useBeans, usePastRuns } from '../queries'
import { computeBeanStats } from '../stats'
import type { CountItem } from '../stats'
import Spinner from './Spinner'
import { formatCost } from './TraceRunList'

interface Props {
  userId: string
}

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="stat-tile">
      <span className="stat-tile__value">{value}</span>
      <span className="stat-tile__label">{label}</span>
    </div>
  )
}

function BarList({ items, unit }: { items: CountItem[]; unit: string }) {
  const max = items.reduce((acc, item) => Math.max(acc, item.count), 0)
  if (items.length === 0) return <p className="empty-state">None yet.</p>

  return (
    <div className="bar-list">
      {items.map(item => (
        <div
          key={item.label}
          className="bar-row"
          title={`${item.label}: ${item.count} ${item.count === 1 ? unit : `${unit}s`}`}
        >
          <span className="bar-row__label">{item.label}</span>
          <span className="bar-row__track">
            <span
              className="bar-row__fill"
              style={{ width: max === 0 ? '0%' : `${(item.count / max) * 100}%` }}
            />
          </span>
          <span className="bar-row__count">{item.count}</span>
        </div>
      ))}
    </div>
  )
}

function FlavorCloud({ items }: { items: CountItem[] }) {
  const max = items.reduce((acc, item) => Math.max(acc, item.count), 0)
  if (items.length === 0) return <p className="empty-state">None yet.</p>

  return (
    <div className="flavor-cloud">
      {items.map(item => {
        const ratio = max === 0 ? 0 : item.count / max
        const tier = ratio > 0.75 ? 4 : ratio > 0.5 ? 3 : ratio > 0.25 ? 2 : 1
        return (
          <span
            key={item.label}
            className={`chip flavor-chip--t${tier}`}
            title={`${item.label}: ${item.count} ${item.count === 1 ? 'bean' : 'beans'}`}
          >
            {item.label} <strong>{item.count}</strong>
          </span>
        )
      })}
    </div>
  )
}

function Missing({ count, field }: { count: number; field: string }) {
  if (count === 0) return null
  return (
    <p className="stats-panel__missing">
      {count} {count === 1 ? 'bean' : 'beans'} missing {field}
    </p>
  )
}

export default function StatsPanel({ userId }: Props) {
  const { data: beans, isLoading, isError } = useBeans(userId)
  const { data: runs, isError: runsError } = usePastRuns(userId)

  if (isLoading) return <div className="stats-panel"><Spinner /></div>
  if (isError) return <p className="inline-error">Could not load your beans.</p>

  const stats = computeBeanStats(beans ?? [])

  if (stats.totalBeans === 0) {
    return (
      <div className="stats-panel">
        <p className="empty-state">
          No beans logged yet — add a bean on the Dashboard and your origins, roasts, and
          flavors will show up here.
        </p>
      </div>
    )
  }

  const runsAvailable = !runsError && runs !== undefined
  const totalSpend = (runs ?? []).reduce(
    (sum, run) => sum + (run.total_cost_usd ?? 0),
    0,
  )

  return (
    <div className="stats-panel">
      <div className="stats-panel__tiles">
        <StatTile value={String(stats.totalBeans)} label="Beans logged" />
        <StatTile value={String(stats.distinctRoasters)} label="Roasters" />
        <StatTile value={String(stats.distinctOrigins)} label="Origins" />
        <StatTile
          value={runsAvailable ? String(runs.length) : '—'}
          label="Recommendation runs"
        />
        <StatTile value={runsAvailable ? formatCost(totalSpend) : '—'} label="LLM spend" />
      </div>

      <section className="stats-section">
        <h2>Origins tried</h2>
        <BarList items={stats.origins} unit="bean" />
        <Missing count={stats.missingOrigin} field="origin" />
      </section>

      <section className="stats-section">
        <h2>Roast levels</h2>
        <BarList items={stats.roastLevels} unit="bean" />
        <Missing count={stats.missingRoast} field="roast level" />
      </section>

      <section className="stats-section">
        <h2>Processes</h2>
        <BarList items={stats.processes} unit="bean" />
        <Missing count={stats.missingProcess} field="process" />
      </section>

      <section className="stats-section">
        <h2>Most common tasting notes</h2>
        <FlavorCloud items={stats.notes} />
      </section>
    </div>
  )
}
