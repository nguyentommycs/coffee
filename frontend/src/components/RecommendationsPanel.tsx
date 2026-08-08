import { useState } from 'react'
import {
  useBeans,
  useFeedback,
  usePipelineProgress,
  useRunRecommendations,
  useSetFeedback,
} from '../queries'
import type { FeedbackVerdict, RecommendationCandidate, RecommendationResponse } from '../types'
import CriticNotes from './CriticNotes'
import PipelineProgress from './PipelineProgress'
import RecommendationsTable, { feedbackKey } from './RecommendationsTable'

interface Props {
  userId: string
}

export default function RecommendationsPanel({ userId }: Props) {
  const { data: beans } = useBeans(userId)
  const mutation = useRunRecommendations(userId)
  const { data: feedbackList } = useFeedback(userId)
  const setFeedback = useSetFeedback(userId)
  const [result, setResult] = useState<RecommendationResponse | null>(null)
  const [progressId, setProgressId] = useState<string | null>(null)
  const progressQuery = usePipelineProgress(mutation.isPending ? progressId : null)

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

  const beanCount = beans?.length ?? 0
  const isDisabled = beanCount < 3 || mutation.isPending

  function handleClick() {
    const id = crypto.randomUUID()
    setProgressId(id)
    mutation.mutate({ progressId: id }, { onSuccess: data => setResult(data) })
  }

  return (
    <section className="recommendations-panel">
      <div className="recommendations-panel__header">
        <button
          disabled={isDisabled}
          title={`You have ${beanCount} bean(s). Need at least 3 to run.`}
          onClick={handleClick}
        >
          Get recommendations
        </button>
      </div>
      {mutation.isPending && <PipelineProgress progress={progressQuery.data} />}
      {mutation.isError && (
        <p className="inline-error">Something went wrong. Please try again.</p>
      )}
      {result && (
        <div className="recommendations-panel__results">
          <CriticNotes notes={result.critic_notes} />
          <RecommendationsTable
            recommendations={result.recommendations}
            feedback={feedback}
            onFeedback={handleFeedback}
          />
        </div>
      )}
    </section>
  )
}
