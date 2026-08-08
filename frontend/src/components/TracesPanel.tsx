import { useState } from 'react'
import type { TraceSpan } from '../types'
import TraceRunList from './TraceRunList'
import TraceWaterfall from './TraceWaterfall'
import SpanDetail from './SpanDetail'

interface Props {
  userId: string
}

export default function TracesPanel({ userId }: Props) {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selected, setSelected] = useState<{ key: string; span: TraceSpan } | null>(null)

  function selectRun(runId: string) {
    setSelectedRunId(runId)
    setSelected(null)
  }

  return (
    <section className="traces-panel">
      <div className="traces-panel__runs">
        <h2>Pipeline runs</h2>
        <TraceRunList userId={userId} selectedRunId={selectedRunId} onSelect={selectRun} />
      </div>

      <div className="traces-panel__waterfall">
        <h2>Waterfall</h2>
        {selectedRunId ? (
          <TraceWaterfall
            userId={userId}
            runId={selectedRunId}
            selectedSpanKey={selected?.key ?? null}
            onSelectSpan={(key, span) => setSelected({ key, span })}
          />
        ) : (
          <p className="empty-state">Select a run to see its spans.</p>
        )}
      </div>

      {selected && <SpanDetail span={selected.span} onClose={() => setSelected(null)} />}
    </section>
  )
}
