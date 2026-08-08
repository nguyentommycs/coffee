import { useState } from 'react'
import { useFeedback, usePastRuns, useSetFeedback } from '../queries'
import type { FeedbackVerdict, RecommendationCandidate } from '../types'
import Spinner from './Spinner'
import CriticNotes from './CriticNotes'
import RecommendationsTable, { feedbackKey } from './RecommendationsTable'
import TasteProfileView from './TasteProfileView'
import { formatCost, relativeTime } from './TraceRunList'

interface Props {
  userId: string
}

export default function HistoryPanel({ userId }: Props) {
  const { data: runs, isLoading, isError } = usePastRuns(userId)
  const { data: feedbackList } = useFeedback(userId)
  const setFeedback = useSetFeedback(userId)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const feedback = new Map<string, FeedbackVerdict>(
    (feedbackList ?? []).map(fb => [feedbackKey(fb.roaster, fb.name), fb.verdict]),
  )

  function handleFeedback(c: RecommendationCandidate, verdict: FeedbackVerdict | null) {
    setFeedback.mutate({
      roaster: c.roaster,
      name: c.name,
      product_url: c.product_url,
      verdict,
    })
  }

  const selectedRun = runs?.find(run => run.id === selectedRunId) ?? null

  return (
    <section className="history-panel">
      <div className="history-panel__runs">
        <h2>Past runs</h2>
        {isLoading && <div className="trace-run-list"><Spinner /></div>}
        {isError && <p className="inline-error">Could not load past runs.</p>}
        {!isLoading && !isError && (!runs || runs.length === 0) && (
          <p className="empty-state">No recommendation runs yet.</p>
        )}
        {runs && runs.length > 0 && (
          <ul className="trace-run-list">
            {runs.map(run => (
              <li key={run.id}>
                <button
                  className={`trace-run-list__item${run.id === selectedRunId ? ' trace-run-list__item--selected' : ''}`}
                  onClick={() => setSelectedRunId(run.id)}
                >
                  <span className="trace-run-list__top">
                    <span>{relativeTime(run.created_at)}</span>
                  </span>
                  <span className="trace-run-list__meta">
                    {run.recommendations.length} candidate
                    {run.recommendations.length === 1 ? '' : 's'}
                    {run.total_cost_usd !== null && run.total_cost_usd !== undefined
                      ? ` · ${formatCost(run.total_cost_usd)}`
                      : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="history-panel__detail">
        <h2>Recommendations</h2>
        {selectedRun ? (
          <>
            {selectedRun.taste_profile_snapshot && (
              <details className="history-panel__profile">
                <summary>Taste profile at time of run</summary>
                <TasteProfileView profile={selectedRun.taste_profile_snapshot} compact />
              </details>
            )}
            <CriticNotes notes={selectedRun.critic_notes} />
            <RecommendationsTable
              recommendations={selectedRun.recommendations}
              feedback={feedback}
              onFeedback={handleFeedback}
            />
          </>
        ) : (
          <p className="empty-state">Select a run to see its recommendations.</p>
        )}
      </div>
    </section>
  )
}
