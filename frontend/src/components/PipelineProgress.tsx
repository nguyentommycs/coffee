import type { PipelineProgress as Progress, StageStatus } from '../types'
import Spinner from './Spinner'

interface Props {
  progress: Progress | undefined
}

const BASE_STAGES = ['profiler', 'recommendation', 'critic']

const LABELS: Record<string, string> = {
  profiler: 'Building your taste profile',
  recommendation: 'Searching roaster catalogs & scoring candidates',
  critic: 'Critic reviewing picks',
  recommendation_revision: 'Revising rejected picks',
  critic_review_2: 'Critic re-reviewing',
}

type RowStatus = StageStatus | 'pending'

interface Row {
  key: string
  status: RowStatus
  elapsedMs: number | null
}

function buildRows(progress: Progress | undefined): Row[] {
  const stages = progress?.stages ?? []
  const byKey = new Map(stages.map(s => [s.key, s]))

  const base: Row[] = BASE_STAGES.map(key => {
    const stage = byKey.get(key)
    return {
      key,
      status: stage ? stage.status : ('pending' as RowStatus),
      elapsedMs: stage ? stage.elapsed_ms : null,
    }
  })

  // Revision stages only exist on runs where the critic pruned hard; append in
  // the order the backend reported them.
  const extra: Row[] = stages
    .filter(s => !BASE_STAGES.includes(s.key))
    .map(s => ({ key: s.key, status: s.status as RowStatus, elapsedMs: s.elapsed_ms }))

  return [...base, ...extra]
}

function marker(status: RowStatus) {
  if (status === 'running') return <Spinner />
  if (status === 'done') return <span className="pipeline-progress__check">✓</span>
  if (status === 'error') return <span className="pipeline-progress__error-mark">✕</span>
  return <span className="pipeline-progress__dot">•</span>
}

export default function PipelineProgress({ progress }: Props) {
  const rows = buildRows(progress)

  return (
    <div className="pipeline-progress">
      {progress === undefined && (
        <p className="pipeline-progress__starting">Starting…</p>
      )}
      <ul className="pipeline-progress__list">
        {rows.map(row => (
          <li
            key={row.key}
            className={`pipeline-progress__stage pipeline-progress__stage--${row.status}`}
          >
            <span className="pipeline-progress__marker">{marker(row.status)}</span>
            <span className="pipeline-progress__label">{LABELS[row.key] ?? row.key}</span>
            {row.elapsedMs !== null && row.status !== 'pending' && (
              <span className="pipeline-progress__elapsed">
                ({(row.elapsedMs / 1000).toFixed(1)}s)
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
