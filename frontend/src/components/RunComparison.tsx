import type { RecommendationCandidate, RecommendationRun, TasteProfile } from '../types'
import { formatCost, relativeTime } from './TraceRunList'

interface Props {
  /** The older of the two runs. */
  runA: RecommendationRun
  /** The newer of the two runs. */
  runB: RecommendationRun
}

function candidateKey(c: RecommendationCandidate): string {
  const url = c.product_url?.trim().toLowerCase() ?? ''
  return url !== '' ? url : `${c.roaster}::${c.name}`.trim().toLowerCase()
}

function pct(score: number): string {
  return `${Math.round(score * 100)}%`
}

function Chip({ label, variant }: { label: string; variant: 'added' | 'removed' }) {
  return <span className={`chip chip--${variant}`}>{label}</span>
}

function RunMeta({ run, label }: { run: RecommendationRun; label: string }) {
  const count = run.recommendations.length
  const cost =
    run.total_cost_usd !== null && run.total_cost_usd !== undefined
      ? formatCost(run.total_cost_usd)
      : null
  return (
    <div className="run-comparison__meta">
      <span className="run-comparison__meta-label">{label}</span>
      <span className="run-comparison__meta-when">{relativeTime(run.created_at)}</span>
      <span className="run-comparison__muted">
        {new Date(run.created_at).toLocaleString()}
      </span>
      <span className="run-comparison__muted">
        {count} candidate{count === 1 ? '' : 's'}
        {cost ? ` · ${cost}` : ''}
      </span>
    </div>
  )
}

function CandidateLine({ candidate }: { candidate: RecommendationCandidate }) {
  return (
    <li className="run-comparison__candidate">
      <span className="run-comparison__candidate-name">
        {candidate.product_url ? (
          <a href={candidate.product_url} target="_blank" rel="noreferrer">
            {candidate.name}
          </a>
        ) : (
          candidate.name
        )}
      </span>
      <span className="run-comparison__muted">{candidate.roaster}</span>
      <span className="run-comparison__score">{pct(candidate.match_score)}</span>
    </li>
  )
}

function SharedLine({ a, b }: { a: RecommendationCandidate; b: RecommendationCandidate }) {
  const delta = b.match_score - a.match_score
  const points = Math.abs(Math.round(delta * 100))

  let deltaEl
  if (delta > 0.005) {
    deltaEl = <span className="run-comparison__delta-up">{`▲ +${points} pts`}</span>
  } else if (delta < -0.005) {
    deltaEl = <span className="run-comparison__delta-down">{`▼ −${points} pts`}</span>
  } else {
    deltaEl = <span className="run-comparison__muted">no change</span>
  }

  return (
    <li className="run-comparison__candidate">
      <span className="run-comparison__candidate-name">
        {b.product_url ? (
          <a href={b.product_url} target="_blank" rel="noreferrer">
            {b.name}
          </a>
        ) : (
          b.name
        )}
      </span>
      <span className="run-comparison__muted">{b.roaster}</span>
      <span className="run-comparison__score">
        {pct(a.match_score)} → {pct(b.match_score)}
      </span>
      {deltaEl}
    </li>
  )
}

const PROFILE_FIELDS: { key: keyof TasteProfile; label: string }[] = [
  { key: 'flavor_affinities', label: 'Flavor affinities' },
  { key: 'avoided_flavors', label: 'Avoided flavors' },
  { key: 'preferred_roast_levels', label: 'Preferred roast levels' },
  { key: 'preferred_origins', label: 'Preferred origins' },
  { key: 'preferred_processes', label: 'Preferred processes' },
]

function diffList(a: string[], b: string[]): { added: string[]; removed: string[] } {
  const norm = (s: string) => s.trim().toLowerCase()
  const aSet = new Set(a.map(norm))
  const bSet = new Set(b.map(norm))
  return {
    added: b.filter(item => !aSet.has(norm(item))),
    removed: a.filter(item => !bSet.has(norm(item))),
  }
}

function ProfileDrift({ a, b }: { a: TasteProfile | null; b: TasteProfile | null }) {
  if (!a || !b) {
    return (
      <p className="run-comparison__muted">
        Taste profile snapshot not available for one or both runs.
      </p>
    )
  }

  const rows = PROFILE_FIELDS.map(({ key, label }) => {
    const listA = (a[key] as string[] | undefined) ?? []
    const listB = (b[key] as string[] | undefined) ?? []
    return { label, ...diffList(listA, listB) }
  }).filter(row => row.added.length > 0 || row.removed.length > 0)

  if (rows.length === 0) {
    return <p className="run-comparison__muted">No taste-profile changes between these runs.</p>
  }

  return (
    <div className="run-comparison__drift">
      {rows.map(row => (
        <div key={row.label} className="run-comparison__drift-row">
          <span className="run-comparison__drift-label">{row.label}</span>
          <div className="chip-row">
            {row.added.map((item, i) => (
              <Chip key={`add-${item}-${i}`} label={item} variant="added" />
            ))}
            {row.removed.map((item, i) => (
              <Chip key={`rm-${item}-${i}`} label={item} variant="removed" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function RunComparison({ runA, runB }: Props) {
  const byKeyA = new Map(runA.recommendations.map(c => [candidateKey(c), c]))
  const byKeyB = new Map(runB.recommendations.map(c => [candidateKey(c), c]))

  const newInB = runB.recommendations.filter(c => !byKeyA.has(candidateKey(c)))
  const droppedFromA = runA.recommendations.filter(c => !byKeyB.has(candidateKey(c)))
  const shared = runB.recommendations
    .filter(c => byKeyA.has(candidateKey(c)))
    .map(c => ({ a: byKeyA.get(candidateKey(c))!, b: c }))

  return (
    <div className="run-comparison">
      <div className="run-comparison__header">
        <RunMeta run={runA} label="Earlier run" />
        <RunMeta run={runB} label="Later run" />
      </div>

      <h3 className="run-comparison__heading">New in this run ({newInB.length})</h3>
      {newInB.length === 0 ? (
        <p className="run-comparison__muted">None</p>
      ) : (
        <ul className="run-comparison__list">
          {newInB.map(c => (
            <CandidateLine key={candidateKey(c)} candidate={c} />
          ))}
        </ul>
      )}

      <h3 className="run-comparison__heading">Dropped ({droppedFromA.length})</h3>
      {droppedFromA.length === 0 ? (
        <p className="run-comparison__muted">None</p>
      ) : (
        <ul className="run-comparison__list">
          {droppedFromA.map(c => (
            <CandidateLine key={candidateKey(c)} candidate={c} />
          ))}
        </ul>
      )}

      <h3 className="run-comparison__heading">In both ({shared.length})</h3>
      {shared.length === 0 ? (
        <p className="run-comparison__muted">None</p>
      ) : (
        <ul className="run-comparison__list">
          {shared.map(({ a, b }) => (
            <SharedLine key={candidateKey(b)} a={a} b={b} />
          ))}
        </ul>
      )}

      <h3 className="run-comparison__heading">Taste profile drift</h3>
      <ProfileDrift a={runA.taste_profile_snapshot} b={runB.taste_profile_snapshot} />
    </div>
  )
}
