import type { FeedbackVerdict, RecommendationCandidate } from '../types'

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

export function feedbackKey(roaster: string, name: string): string {
  return `${roaster}::${name}`
}

export default function RecommendationsTable({ recommendations, feedback, onFeedback }: Props) {
  if (recommendations.length === 0) {
    return <p className="empty-state">No recommendations yet.</p>
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
            return (
              <tr key={i}>
                <td>
                  <a href={c.product_url} target="_blank" rel="noreferrer">{c.name}</a>
                </td>
                <td>{c.roaster}</td>
                <td>{formatOrigin(c)}</td>
                <td>{c.process ?? '—'}</td>
                <td>{c.roast_level ?? '—'}</td>
                <td>{c.tasting_notes.join(', ') || '—'}</td>
                <td>{Math.round(c.match_score * 100)}% – {c.match_rationale}</td>
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
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
