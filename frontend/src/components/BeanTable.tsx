import { useState } from 'react'
import type { BeanEditableFields } from '../api'
import { useUpdateBean } from '../queries'
import type { BeanProfile } from '../types'

interface Props {
  userId: string
  beans: BeanProfile[]
}

const PROCESS_OPTIONS: NonNullable<BeanProfile['process']>[] = ['Washed', 'Natural', 'Honey', 'Anaerobic']
const ROAST_LEVEL_OPTIONS: NonNullable<BeanProfile['roast_level']>[] = [
  'Light',
  'Medium-Light',
  'Medium',
  'Dark',
]

function formatOrigin(bean: BeanProfile): string {
  const parts = [bean.origin_country, bean.origin_region].filter(Boolean)
  return parts.join(', ') || '—'
}

function toEditableFields(bean: BeanProfile): BeanEditableFields {
  return {
    name: bean.name,
    roaster: bean.roaster,
    origin_country: bean.origin_country ?? null,
    origin_region: bean.origin_region ?? null,
    farm_or_cooperative: bean.farm_or_cooperative ?? null,
    process: bean.process ?? null,
    variety: bean.variety ?? null,
    roast_level: bean.roast_level ?? null,
    tasting_notes: bean.tasting_notes,
    user_score: bean.user_score ?? null,
    user_notes: bean.user_notes ?? null,
  }
}

export default function BeanTable({ userId, beans }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<BeanEditableFields | null>(null)
  const mutation = useUpdateBean(userId)

  if (beans.length === 0) {
    return <p className="empty-state">No beans yet. Add your first one on the left.</p>
  }

  function startEdit(bean: BeanProfile) {
    setEditingId(bean.id)
    setDraft(toEditableFields(bean))
    mutation.reset()
  }

  function cancelEdit() {
    setEditingId(null)
    setDraft(null)
    mutation.reset()
  }

  function saveEdit(beanId: string) {
    if (!draft) return
    if (draft.name.trim() === '' || draft.roaster.trim() === '') return
    mutation.mutate(
      { beanId, fields: draft },
      { onSuccess: () => { setEditingId(null); setDraft(null) } },
    )
  }

  function updateDraft<K extends keyof BeanEditableFields>(key: K, value: BeanEditableFields[K]) {
    setDraft(d => (d ? { ...d, [key]: value } : d))
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
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {beans.map(bean => {
            const isEditing = editingId === bean.id

            if (!isEditing || !draft) {
              return (
                <tr key={bean.id}>
                  <td>{bean.name}</td>
                  <td>{bean.roaster}</td>
                  <td>{formatOrigin(bean)}</td>
                  <td>{bean.process ?? '—'}</td>
                  <td>{bean.roast_level ?? '—'}</td>
                  <td>{bean.tasting_notes.join(', ') || '—'}</td>
                  <td>{bean.user_score != null ? `${bean.user_score}/10` : '—'}</td>
                  <td>
                    <button type="button" onClick={() => startEdit(bean)}>
                      Edit
                    </button>
                  </td>
                </tr>
              )
            }

            return (
              <tr key={bean.id} className="bean-table__row--editing">
                <td>
                  <input
                    type="text"
                    value={draft.name}
                    onChange={e => updateDraft('name', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    value={draft.roaster}
                    onChange={e => updateDraft('roaster', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    placeholder="Country"
                    value={draft.origin_country ?? ''}
                    onChange={e => updateDraft('origin_country', e.target.value || null)}
                  />
                  <input
                    type="text"
                    placeholder="Region"
                    value={draft.origin_region ?? ''}
                    onChange={e => updateDraft('origin_region', e.target.value || null)}
                  />
                </td>
                <td>
                  <select
                    value={draft.process ?? ''}
                    onChange={e => updateDraft('process', (e.target.value || null) as BeanEditableFields['process'])}
                  >
                    <option value="">—</option>
                    {PROCESS_OPTIONS.map(option => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    value={draft.roast_level ?? ''}
                    onChange={e =>
                      updateDraft('roast_level', (e.target.value || null) as BeanEditableFields['roast_level'])
                    }
                  >
                    <option value="">—</option>
                    {ROAST_LEVEL_OPTIONS.map(option => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="text"
                    placeholder="comma, separated, notes"
                    value={draft.tasting_notes.join(', ')}
                    onChange={e =>
                      updateDraft(
                        'tasting_notes',
                        e.target.value
                          .split(',')
                          .map(note => note.trim())
                          .filter(Boolean),
                      )
                    }
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    step={1}
                    value={draft.user_score ?? ''}
                    onChange={e => {
                      const raw = e.target.value
                      if (raw === '') {
                        updateDraft('user_score', null)
                        return
                      }
                      const clamped = Math.min(10, Math.max(1, Number(raw)))
                      updateDraft('user_score', clamped)
                    }}
                  />
                </td>
                <td className="bean-table__actions">
                  <button
                    type="button"
                    onClick={() => saveEdit(bean.id)}
                    disabled={mutation.isPending || draft.name.trim() === '' || draft.roaster.trim() === ''}
                  >
                    Save
                  </button>
                  <button type="button" onClick={cancelEdit} disabled={mutation.isPending}>
                    Cancel
                  </button>
                  {mutation.isError && editingId === bean.id && (
                    <p className="inline-error">Couldn't save. Try again.</p>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
