import { clearUsername } from '../auth'

export type View = 'dashboard' | 'stats' | 'history' | 'traces'

const TAB_LABELS: Record<View, string> = {
  dashboard: 'Dashboard',
  stats: 'Stats',
  history: 'History',
  traces: 'Traces',
}

interface Props {
  username: string
  view: View
  onViewChange: (view: View) => void
  onSignOut: () => void
}

export default function Header({ username, view, onViewChange, onSignOut }: Props) {
  function handleSignOut() {
    clearUsername()
    onSignOut()
  }

  return (
    <header className="app-header">
      <nav className="app-header__tabs">
        {(['dashboard', 'stats', 'history', 'traces'] as View[]).map(tab => (
          <button
            key={tab}
            className={`app-header__tab${view === tab ? ' app-header__tab--active' : ''}`}
            onClick={() => onViewChange(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </nav>
      <span>
        Signed in as <strong>{username}</strong>
      </span>
      <button onClick={handleSignOut}>Sign out</button>
    </header>
  )
}
