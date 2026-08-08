import { useTraces } from '../queries'
import Spinner from './Spinner'

interface Props {
  userId: string
  selectedRunId: string | null
  onSelect: (runId: string) => void
}

function relativeTime(iso: string): string {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`
}

export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return '—'
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`
}

export default function TraceRunList({ userId, selectedRunId, onSelect }: Props) {
  const { data, isLoading, isError } = useTraces(userId)

  if (isLoading) return <div className="trace-run-list"><Spinner /></div>
  if (isError) return <p className="inline-error">Could not load traces.</p>
  if (!data || data.length === 0) {
    return <p className="empty-state">No pipeline runs yet.</p>
  }

  return (
    <ul className="trace-run-list">
      {data.map(run => (
        <li key={run.run_id}>
          <button
            className={`trace-run-list__item${run.run_id === selectedRunId ? ' trace-run-list__item--selected' : ''}`}
            onClick={() => onSelect(run.run_id)}
          >
            <span className="trace-run-list__top">
              <span className={`trace-status-dot trace-status-dot--${run.status}`} />
              <span>{relativeTime(run.created_at)}</span>
              <span className="trace-run-list__duration">{formatDuration(run.total_duration_ms)}</span>
            </span>
            <span className="trace-run-list__meta">
              {run.llm_calls} llm call{run.llm_calls === 1 ? '' : 's'} ·{' '}
              {(run.total_input_tokens + run.total_output_tokens).toLocaleString()} tok
              {run.total_cost_usd !== null && run.total_cost_usd !== undefined
                ? ` · ${formatCost(run.total_cost_usd)}`
                : ''}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
