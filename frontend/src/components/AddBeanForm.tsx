import { useState } from 'react'
import { ApiError } from '../api'
import { useAddBean } from '../queries'
import Spinner from './Spinner'

interface Props {
  userId: string
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      const body = error.body as { fields_missing?: string[] } | null
      const fields = body?.fields_missing
      if (fields && fields.length > 0) {
        return `We couldn't parse this — missing fields: ${fields.join(', ')}. Try adding more detail.`
      }
      return "We couldn't parse this. Try adding more detail."
    }
    if (error.status === 500) {
      return 'Parsing took too long. Try a simpler description or a direct product URL.'
    }
  }
  return 'Something went wrong. Please try again.'
}

export default function AddBeanForm({ userId }: Props) {
  const [value, setValue] = useState('')
  const [score, setScore] = useState<number | null>(null)
  const mutation = useAddBean(userId)

  const canSubmit = !mutation.isPending && value.trim() !== '' && score !== null

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    mutation.mutate(
      { input: value.trim(), score: score! },
      { onSuccess: () => { setValue(''); setScore(null) } },
    )
  }

  return (
    <form className="add-bean-form" onSubmit={handleSubmit}>
      <h2>Add a bean</h2>
      <textarea
        value={value}
        onChange={e => setValue(e.target.value)}
        disabled={mutation.isPending}
        placeholder="Paste a URL, product name, or describe a bean you've tried…"
        rows={6}
      />
      <div className="score-field">
        <label htmlFor="bean-score">
          Your score{' '}
          <span className="score-value">
            {score !== null ? score : <span className="score-empty">— required</span>}
          </span>
        </label>
        <input
          id="bean-score"
          type="range"
          min={1}
          max={10}
          step={1}
          value={score ?? ''}
          onChange={e => setScore(Number(e.target.value))}
          disabled={mutation.isPending}
          className={score === null ? 'slider-unset' : ''}
        />
        <div className="score-ticks" aria-hidden>
          {Array.from({ length: 10 }, (_, i) => (
            <span key={i + 1}>{i + 1}</span>
          ))}
        </div>
      </div>
      <div className="add-bean-form__actions">
        <button type="submit" disabled={!canSubmit}>
          Add new bean
        </button>
        {mutation.isPending && <Spinner />}
      </div>
      {mutation.isError && (
        <p className="inline-error">{getErrorMessage(mutation.error)}</p>
      )}
    </form>
  )
}
