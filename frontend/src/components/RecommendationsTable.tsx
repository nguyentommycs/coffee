import { Fragment, useState } from 'react'
import type { FeedbackVerdict, RecommendationCandidate, ScoreComponent } from '../types'

interface Props {
  recommendations: RecommendationCandidate[]
  /** Verdict per candidate, keyed by `${roaster}::${name}`. */
  feedback: Map<string, FeedbackVerdict>
  onFeedback: (candidate: RecommendationCandidate, verdict: FeedbackVerdict | null) => void
}

function formatOrigin(c: RecommendationCandidate): string {
  const parts = [c.origin_country, c.origin_region].filter(Boolean)
  return parts.join(', ') || '—'
}

function formatPoints(points: number): string {
  const magnitude = String(Math.abs(Number(points.toFixed(3))))
  return points >= 0 ? `+${magnitude}` : `−${magnitude}`
}

export function feedbackKey(roaster: string, name: string): string {
  return `${roaster}::${name}`
}

export default function RecommendationsTable({ recommendations, feedback, onFeedback }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  if (recommendations.length === 0) {
    return <p className="empty-state">No recommendations yet.</p>
  }

  const toggle = (i: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  return (
    <div className="recommendations-table-wrapper">
      <table className="recommendations-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Roaster</th>
            <th>Origin</th>
            <th>Process</th>
            <th>Roast level</th>
            <th>Tasting notes</th>
            <th>Match score</th>
            <th>Feedback</th>
          </tr>
        </thead>
        <tbody>
          {recommendations.map((c, i) => {
            const current = feedback.get(feedbackKey(c.roaster, c.name)) ?? null
            const breakdown: ScoreComponent[] = c.score_breakdown ?? []
            const isOpen = expanded.has(i)
            const pct = Math.round(c.match_score * 100)
            return (
              <Fragment key={i}>
                <tr>
                  <td>
                    <a href={c.product_url} target="_blank" rel="noreferrer">{c.name}</a>
                  </td>
                  <td>{c.roaster}</td>
                  <td>{formatOrigin(c)}</td>
                  <td>{c.process ?? '—'}</td>
                  <td>{c.roast_level ?? '—'}</td>
                  <td>{c.tasting_notes.join(', ') || '—'}</td>
                  <td>
                    {breakdown.length > 0 ? (
                      <button
                        className="score-toggle"
                        aria-expanded={isOpen}
                        title="Why this match?"
                        onClick={() => toggle(i)}
                      >
                        {pct}% {isOpen ? '▾' : '▸'}
                      </button>
                    ) : (
                      <>{pct}%</>
                    )}
                    {' – '}{c.match_rationale}
                  </td>
                  <td>
                    <button
                      className={`feedback-btn${current === 'up' ? ' feedback-btn--active' : ''}`}
                      aria-pressed={current === 'up'}
                      title="Interested"
                      onClick={() => onFeedback(c, current === 'up' ? null : 'up')}
                    >
                      👍
                    </button>
                    <button
                      className={`feedback-btn${current === 'down' ? ' feedback-btn--active' : ''}`}
                      aria-pressed={current === 'down'}
                      title="Not interested"
                      onClick={() => onFeedback(c, current === 'down' ? null : 'down')}
                    >
                      👎
                    </button>
                  </td>
                </tr>
                {isOpen && breakdown.length > 0 && (
                  <tr className="score-breakdown-row">
                    <td colSpan={8}>
                      <ul className="score-breakdown-list">
                        {breakdown.map((comp, j) => (
                          <li key={j}>
                            <span className="score-breakdown-label">{comp.label}:</span>{' '}
                            {comp.value}{' '}
                            <span className={comp.points >= 0 ? 'points-pos' : 'points-neg'}>
                              {formatPoints(comp.points)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
