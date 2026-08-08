import { useTrace } from '../queries'
import type { TraceSpan } from '../types'
import Spinner from './Spinner'
import { formatCost, formatDuration } from './TraceRunList'

interface Props {
  userId: string
  runId: string
  selectedSpanKey: string | null
  onSelectSpan: (key: string, span: TraceSpan) => void
}

interface Row {
  key: string
  span: TraceSpan
  depth: number
}

/**
 * Rebuilds the span tree from parent_id. Legacy traces have no id/parent_id —
 * every span then falls through to the root level, which is exactly right.
 */
function buildRows(spans: TraceSpan[]): Row[] {
  const keyed = spans.map((span, i) => ({ span, key: span.id ?? `span-${i}`, depth: 0 }))
  const knownIds = new Set(spans.map(s => s.id).filter((id): id is string => !!id))

  const children = new Map<string, Row[]>()
  const roots: Row[] = []
  for (const item of keyed) {
    const parentId = item.span.parent_id
    if (parentId && knownIds.has(parentId)) {
      const siblings = children.get(parentId) ?? []
      siblings.push(item)
      children.set(parentId, siblings)
    } else {
      roots.push(item)
    }
  }

  const byStart = (a: Row, b: Row) => (a.span.start ?? 0) - (b.span.start ?? 0)
  const rows: Row[] = []
  function walk(row: Row, depth: number) {
    rows.push({ ...row, depth })
    const kids = children.get(row.span.id ?? '') ?? []
    kids.sort(byStart).forEach(kid => walk(kid, depth + 1))
  }
  roots.sort(byStart).forEach(root => walk(root, 0))
  return rows
}

/** Sums cost_usd across spans that carry it; null when none do. */
function totalCost(spans: TraceSpan[]): number | null {
  const costs = spans
    .map(s => s.attrs?.cost_usd)
    .filter((c): c is number => typeof c === 'number')
  return costs.length ? costs.reduce((a, b) => a + b, 0) : null
}

/** Compact "100→20 tok" label for llm spans that recorded token counts. */
function tokenLabel(span: TraceSpan): string | null {
  if (span.type !== 'llm') return null
  const input = span.attrs?.input_tokens
  const output = span.attrs?.output_tokens
  if (typeof input !== 'number' || typeof output !== 'number') return null
  return `${input.toLocaleString()}→${output.toLocaleString()} tok`
}

export default function TraceWaterfall({ userId, runId, selectedSpanKey, onSelectSpan }: Props) {
  const { data, isLoading, isError } = useTrace(userId, runId)

  if (isLoading) return <div className="trace-waterfall"><Spinner /></div>
  if (isError) return <p className="inline-error">Could not load this trace.</p>

  const spans = data?.trace?.spans ?? []
  if (spans.length === 0) return <p className="empty-state">This run has no spans recorded.</p>

  const rows = buildRows(spans)
  const cost = totalCost(spans)
  const t0 = Math.min(...spans.map(s => s.start ?? 0))
  const totalMs =
    data?.trace?.total_duration_ms ||
    Math.max(...spans.map(s => ((s.start ?? 0) - t0) * 1000 + (s.duration_ms ?? 0))) ||
    1

  return (
    <div className="trace-waterfall">
      <div className="trace-waterfall__total">
        Total {formatDuration(data?.trace?.total_duration_ms)}
        {cost !== null ? ` · ${formatCost(cost)}` : ''}
      </div>
      {rows.map(row => {
        const { span } = row
        const left = Math.max(0, Math.min(100, (((span.start ?? 0) - t0) * 1000 * 100) / totalMs))
        const width = Math.max(0.5, Math.min(100 - left, ((span.duration_ms ?? 0) * 100) / totalMs))
        const kind = span.status === 'error' ? 'error' : span.type ?? 'agent'
        return (
          <button
            key={row.key}
            className={`trace-row${row.key === selectedSpanKey ? ' trace-row--selected' : ''}`}
            onClick={() => onSelectSpan(row.key, span)}
          >
            <span className="trace-row__name" style={{ paddingLeft: `${row.depth * 1.1}rem` }}>
              {span.name}
            </span>
            <span className="trace-row__track">
              <span
                className={`trace-row__bar trace-row__bar--${kind}`}
                style={{ left: `${left}%`, width: `${width}%` }}
              />
            </span>
            <span className="trace-row__duration">
              {tokenLabel(span) && <span className="trace-row__tokens">{tokenLabel(span)}</span>}
              {formatDuration(span.duration_ms)}
            </span>
          </button>
        )
      })}
    </div>
  )
}
