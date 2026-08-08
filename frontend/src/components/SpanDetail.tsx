import type { TraceSpan } from '../types'
import { formatDuration } from './TraceRunList'

interface Props {
  span: TraceSpan
  onClose: () => void
}

const TEXT_ATTRS = ['prompt', 'response']

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value) || typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export default function SpanDetail({ span, onClose }: Props) {
  const attrs = span.attrs ?? {}
  const tokenLine =
    span.type === 'llm'
      ? `${(Number(attrs.input_tokens) || 0).toLocaleString()} in / ${(Number(attrs.output_tokens) || 0).toLocaleString()} out`
      : null
  const rows = Object.entries(attrs).filter(
    ([key]) => !TEXT_ATTRS.includes(key) && !(tokenLine && (key === 'input_tokens' || key === 'output_tokens')),
  )

  return (
    <aside className="span-detail">
      <div className="span-detail__header">
        <h3>{span.name}</h3>
        <button onClick={onClose}>Close</button>
      </div>

      <table className="span-detail__table">
        <tbody>
          <tr>
            <th>Type</th>
            <td>{span.type ?? 'agent'}</td>
          </tr>
          <tr>
            <th>Status</th>
            <td>{span.status ?? 'unknown'}</td>
          </tr>
          <tr>
            <th>Duration</th>
            <td>{formatDuration(span.duration_ms)}</td>
          </tr>
          {tokenLine && (
            <tr>
              <th>Tokens</th>
              <td>{tokenLine}</td>
            </tr>
          )}
          {rows.map(([key, value]) => (
            <tr key={key}>
              <th>{key}</th>
              <td>{renderValue(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {span.error && <p className="span-detail__error">{span.error}</p>}

      {TEXT_ATTRS.map(key =>
        typeof attrs[key] === 'string' ? (
          <div key={key} className="span-detail__text">
            <h4>{key}</h4>
            <pre>{attrs[key] as string}</pre>
          </div>
        ) : null,
      )}
    </aside>
  )
}
