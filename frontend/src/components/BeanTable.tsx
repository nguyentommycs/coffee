import type { BeanProfile } from '../types'

interface Props {
  beans: BeanProfile[]
}

function formatOrigin(bean: BeanProfile): string {
  const parts = [bean.origin_country, bean.origin_region].filter(Boolean)
  return parts.join(', ') || '—'
}

export default function BeanTable({ beans }: Props) {
  if (beans.length === 0) {
    return <p className="empty-state">No beans yet. Add your first one on the left.</p>
  }

  return (
    <div className="bean-table-wrapper">
      <table className="bean-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Roaster</th>
            <th>Origin</th>
            <th>Process</th>
            <th>Roast level</th>
            <th>Tasting notes</th>
            <th>Score</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {beans.map(bean => (
            <tr key={bean.id}>
              <td>{bean.name}</td>
              <td>{bean.roaster}</td>
              <td>{formatOrigin(bean)}</td>
              <td>{bean.process ?? '—'}</td>
              <td>{bean.roast_level ?? '—'}</td>
              <td>{bean.tasting_notes.join(', ') || '—'}</td>
              <td>{bean.user_score ?? '—'}</td>
              <td>{bean.user_notes ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
