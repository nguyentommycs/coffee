import { clearUsername } from '../auth'

export type View = 'dashboard' | 'traces'

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
        {(['dashboard', 'traces'] as View[]).map(tab => (
          <button
            key={tab}
            className={`app-header__tab${view === tab ? ' app-header__tab--active' : ''}`}
            onClick={() => onViewChange(tab)}
          >
            {tab === 'dashboard' ? 'Dashboard' : 'Traces'}
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
