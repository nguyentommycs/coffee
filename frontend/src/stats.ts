import type { BeanProfile } from './types'

export interface CountItem {
  label: string
  count: number
}

export interface BeanStats {
  totalBeans: number
  distinctRoasters: number
  distinctOrigins: number
  origins: CountItem[]
  roastLevels: CountItem[]
  processes: CountItem[]
  notes: CountItem[]
  missingOrigin: number
  missingRoast: number
  missingProcess: number
}

const ROAST_ORDER = ['Light', 'Medium-Light', 'Medium', 'Dark']
const PROCESS_ORDER = ['Washed', 'Natural', 'Honey', 'Anaerobic']

/** Trimmed value, or null when the field is absent/blank. */
function clean(value: string | null | undefined): string | null {
  if (value === null || value === undefined) return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/** Case-insensitive counter that remembers the first-seen casing as the label. */
class Tally {
  private entries = new Map<string, CountItem>()

  add(value: string) {
    const key = value.toLowerCase()
    const existing = this.entries.get(key)
    if (existing) existing.count += 1
    else this.entries.set(key, { label: value, count: 1 })
  }

  get(key: string): CountItem | undefined {
    return this.entries.get(key.toLowerCase())
  }

  size(): number {
    return this.entries.size
  }

  /** Count desc, then label asc — deterministic for ties. */
  sorted(): CountItem[] {
    return [...this.entries.values()].sort(
      (a, b) => b.count - a.count || a.label.localeCompare(b.label),
    )
  }
}

/** Fixed-order buckets first (always present), then anything unexpected by count desc. */
function orderedDistribution(tally: Tally, order: string[]): CountItem[] {
  const known = new Set(order.map(label => label.toLowerCase()))
  const fixed = order.map(label => ({ label, count: tally.get(label)?.count ?? 0 }))
  const extra = tally.sorted().filter(item => !known.has(item.label.toLowerCase()))
  return [...fixed, ...extra]
}

export function computeBeanStats(beans: BeanProfile[]): BeanStats {
  const origins = new Tally()
  const roastLevels = new Tally()
  const processes = new Tally()
  const notes = new Tally()
  const roasters = new Set<string>()

  let missingOrigin = 0
  let missingRoast = 0
  let missingProcess = 0

  for (const bean of beans) {
    const roaster = clean(bean.roaster)
    if (roaster) roasters.add(roaster.toLowerCase())

    const origin = clean(bean.origin_country)
    if (origin) origins.add(origin)
    else missingOrigin += 1

    const roast = clean(bean.roast_level)
    if (roast) roastLevels.add(roast)
    else missingRoast += 1

    const process = clean(bean.process)
    if (process) processes.add(process)
    else missingProcess += 1

    // A note repeated on one bean counts once for that bean.
    const seen = new Set<string>()
    for (const raw of bean.tasting_notes ?? []) {
      const note = clean(raw)
      if (!note) continue
      const key = note.toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      notes.add(note)
    }
  }

  return {
    totalBeans: beans.length,
    distinctRoasters: roasters.size,
    distinctOrigins: origins.size(),
    origins: origins.sorted(),
    roastLevels: orderedDistribution(roastLevels, ROAST_ORDER),
    processes: orderedDistribution(processes, PROCESS_ORDER),
    notes: notes.sorted().slice(0, 20),
    missingOrigin,
    missingRoast,
    missingProcess,
  }
}
