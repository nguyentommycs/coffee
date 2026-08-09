import { useState } from 'react'
import { ApiError } from '../api'
import { useAddBean } from '../queries'
import type { BeanProfile } from '../types'
import ErrorBanner from './ErrorBanner'
import Spinner from './Spinner'

interface Props {
  userId: string
}

type Mode = 'url' | 'text'

const URL_PATTERN = /^https?:\/\/\S+\.\S+/

function getErrorMessage(error: unknown, mode: Mode): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      if (mode === 'url') {
        return "We couldn't read that page. Make sure the link points to a roaster's product page."
      }
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
  const [mode, setMode] = useState<Mode>('url')
  const [value, setValue] = useState('')
  const [score, setScore] = useState<number | null>(null)
  const [hint, setHint] = useState<string | null>(null)
  const [added, setAdded] = useState<BeanProfile | null>(null)
  const mutation = useAddBean(userId)

  const canSubmit = !mutation.isPending && value.trim() !== '' && score !== null

  function switchMode(next: Mode) {
    if (next === mode) return
    setMode(next)
    setValue('')
    setHint(null)
    setAdded(null)
    mutation.reset()
  }

  function handleChange(next: string) {
    setValue(next)
    setHint(null)
    setAdded(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    const input = value.trim()
    if (mode === 'url' && !URL_PATTERN.test(input)) {
      setHint('That doesn’t look like a link. Paste the full product URL, starting with https://')
      return
    }
    setHint(null)
    setAdded(null)
    mutation.mutate(
      { input, score: score! },
      {
        onSuccess: data => {
          setValue('')
          setScore(null)
          if (mode === 'url') setAdded(data.parsed[0] ?? null)
        },
      },
    )
  }

  const noneParsed = mode === 'url' && mutation.isSuccess && added === null

  return (
    <form className="add-bean-form" onSubmit={handleSubmit}>
      <h2>Add a bean</h2>

      <div className="mode-toggle" role="group" aria-label="Input mode">
        <button
          type="button"
          className={mode === 'url' ? 'mode-toggle__option is-active' : 'mode-toggle__option'}
          onClick={() => switchMode('url')}
          aria-pressed={mode === 'url'}
        >
          From URL
        </button>
        <button
          type="button"
          className={mode === 'text' ? 'mode-toggle__option is-active' : 'mode-toggle__option'}
          onClick={() => switchMode('text')}
          aria-pressed={mode === 'text'}
        >
          Describe it
        </button>
      </div>

      {mode === 'url' ? (
        <input
          className="url-input"
          type="url"
          value={value}
          onChange={e => handleChange(e.target.value)}
          disabled={mutation.isPending}
          placeholder="https://roaster.com/products/…"
        />
      ) : (
        <textarea
          value={value}
          onChange={e => handleChange(e.target.value)}
          disabled={mutation.isPending}
          placeholder="Paste a URL, product name, or describe a bean you've tried…"
          rows={6}
        />
      )}

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
          value={score ?? 5}
          onChange={e => setScore(Number(e.target.value))}
          onClick={e => setScore(Number((e.currentTarget as HTMLInputElement).value))}
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
          {mode === 'url' ? 'Fetch & add bean' : 'Add new bean'}
        </button>
        {mutation.isPending && (
          <>
            <Spinner />
            {mode === 'url' && <span className="pending-note">Fetching the product page…</span>}
          </>
        )}
      </div>

      {hint && <p className="inline-error">{hint}</p>}

      {mutation.isError && (
        <ErrorBanner
          message={getErrorMessage(mutation.error, mode)}
          onDismiss={() => mutation.reset()}
        />
      )}

      {noneParsed && (
        <ErrorBanner
          message="We couldn't read that page. Make sure the link points to a roaster's product page."
          onDismiss={() => mutation.reset()}
        />
      )}

      {added && (
        <div className="added-bean-card">
          <h3>{added.name}</h3>
          <p className="added-bean-card__meta">
            {[added.roaster, added.origin_country, added.roast_level].filter(Boolean).join(' · ')}
          </p>
          {added.tasting_notes.length > 0 && (
            <ul className="note-chips">
              {added.tasting_notes.map(note => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}
          <p className="added-bean-card__hint">Something off? Edit it in your beans table.</p>
        </div>
      )}
    </form>
  )
}
