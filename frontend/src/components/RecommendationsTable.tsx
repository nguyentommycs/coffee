import type { RecommendationCandidate } from '../types'

interface Props {
  recommendations: RecommendationCandidate[]
}

function formatOrigin(c: RecommendationCandidate): string {
  const parts = [c.origin_country, c.origin_region].filter(Boolean)
  return parts.join(', ') || '—'
}

function formatInStock(val: boolean | null | undefined): string {
  if (val === true) return 'Yes'
  if (val === false) return 'No'
  return '—'
}

export default function RecommendationsTable({ recommendations }: Props) {
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
            <th>Price</th>
            <th>In stock</th>
            <th>Match score</th>
            <th>Rationale</th>
          </tr>
        </thead>
        <tbody>
          {recommendations.map((c, i) => (
            <tr key={i}>
              <td>
                <a href={c.product_url} target="_blank" rel="noreferrer">{c.name}</a>
              </td>
              <td>{c.roaster}</td>
              <td>{formatOrigin(c)}</td>
              <td>{c.process ?? '—'}</td>
              <td>{c.roast_level ?? '—'}</td>
              <td>{c.tasting_notes.join(', ') || '—'}</td>
              <td>{c.price_usd != null ? `$${c.price_usd.toFixed(2)}` : '—'}</td>
              <td>{formatInStock(c.in_stock)}</td>
              <td>{Math.round(c.match_score * 100)}%</td>
              <td>{c.match_rationale}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
