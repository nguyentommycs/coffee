import type { TasteProfile } from '../types'

interface Props {
  profile: TasteProfile
  compact?: boolean
}

const ROAST_STOPS = ['Light', 'Medium-Light', 'Medium', 'Medium-Dark', 'Dark']

function normalize(value: string): string {
  return value.trim().toLowerCase()
}

function Chip({ label, variant }: { label: string; variant?: 'strong' | 'avoided' }) {
  return <span className={`chip${variant ? ` chip--${variant}` : ''}`}>{label}</span>
}

function EmptyValue() {
  return <span className="taste-profile-view__empty-value">None yet</span>
}

function Group({
  label,
  items,
  strongCount = 0,
  variant,
}: {
  label: string
  items: string[]
  strongCount?: number
  variant?: 'avoided'
}) {
  return (
    <div className="taste-profile-view__group">
      <span className="taste-profile-view__label">{label}</span>
      {items.length === 0 ? (
        <EmptyValue />
      ) : (
        <div className="chip-row">
          {items.map((item, i) => (
            <Chip
              key={`${item}-${i}`}
              label={item}
              variant={variant ?? (i < strongCount ? 'strong' : undefined)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function RoastScale({ levels }: { levels: string[] }) {
  const normalized = levels.map(normalize)
  const matched = ROAST_STOPS.filter(stop => normalized.includes(normalize(stop)))
  const stopNames = new Set(ROAST_STOPS.map(normalize))
  const extras = levels.filter(level => !stopNames.has(normalize(level)))

  return (
    <div className="taste-profile-view__group">
      <span className="taste-profile-view__label">Preferred roast levels</span>
      {levels.length === 0 ? (
        <EmptyValue />
      ) : (
        <>
          <div className="roast-scale">
            <span className="roast-scale__end">Light</span>
            <div className="roast-scale__track">
              {ROAST_STOPS.map(stop => (
                <span
                  key={stop}
                  className={`roast-scale__dot${
                    normalized.includes(normalize(stop)) ? ' roast-scale__dot--filled' : ''
                  }`}
                  title={stop}
                />
              ))}
            </div>
            <span className="roast-scale__end">Dark</span>
          </div>
          {matched.length > 0 && (
            <span className="roast-scale__caption">{matched.join(' · ')}</span>
          )}
          {extras.length > 0 && (
            <div className="chip-row">
              {extras.map((extra, i) => (
                <Chip key={`${extra}-${i}`} label={extra} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function TasteProfileView({ profile, compact = false }: Props) {
  const rawConfidence = profile.profile_confidence
  const confidence =
    typeof rawConfidence === 'number' && Number.isFinite(rawConfidence)
      ? Math.min(1, Math.max(0, rawConfidence))
      : 0
  const beans = profile.total_beans_logged ?? 0

  return (
    <div className={`taste-profile-view${compact ? ' taste-profile-view--compact' : ''}`}>
      {!compact && profile.narrative_summary && (
        <p className="taste-profile-view__summary">{profile.narrative_summary}</p>
      )}

      <Group label="Flavor affinities" items={profile.flavor_affinities} strongCount={3} />
      <Group label="Avoided flavors" items={profile.avoided_flavors} variant="avoided" />
      <RoastScale levels={profile.preferred_roast_levels} />
      <Group label="Preferred origins" items={profile.preferred_origins} />
      <Group label="Preferred processes" items={profile.preferred_processes} />

      <div className="taste-profile-view__footer">
        <div className="confidence-bar">
          <div
            className="confidence-bar__fill"
            style={{ width: `${Math.round(confidence * 100)}%` }}
          />
        </div>
        <span className="taste-profile-view__label">
          {Math.round(confidence * 100)}% confidence · {beans} bean{beans === 1 ? '' : 's'} logged
        </span>
      </div>
    </div>
  )
}
