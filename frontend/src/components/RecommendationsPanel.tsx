import { useState } from 'react'
import { useBeans, useRunRecommendations } from '../queries'
import type { RecommendationResponse } from '../types'
import Spinner from './Spinner'
import CriticNotes from './CriticNotes'
import RecommendationsTable from './RecommendationsTable'

interface Props {
  userId: string
}

export default function RecommendationsPanel({ userId }: Props) {
  const { data: beans } = useBeans(userId)
  const mutation = useRunRecommendations(userId)
  const [result, setResult] = useState<RecommendationResponse | null>(null)

  const beanCount = beans?.length ?? 0
  const isDisabled = beanCount < 3 || mutation.isPending

  function handleClick() {
    mutation.mutate(undefined, { onSuccess: data => setResult(data) })
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
        {mutation.isPending && (
          <>
            <Spinner />
            <span>Running pipeline — this takes ~30 seconds</span>
          </>
        )}
      </div>
      {mutation.isError && (
        <p className="inline-error">Something went wrong. Please try again.</p>
      )}
      {result && (
        <div className="recommendations-panel__results">
          <CriticNotes notes={result.critic_notes} />
          <RecommendationsTable recommendations={result.recommendations} />
        </div>
      )}
    </section>
  )
}
