import { clearUsername } from '../auth'

interface Props {
  username: string
  onSignOut: () => void
}

export default function Header({ username, onSignOut }: Props) {
  function handleSignOut() {
    clearUsername()
    onSignOut()
  }

  return (
    <header className="app-header">
      <span>
        Signed in as <strong>{username}</strong>
      </span>
      <button onClick={handleSignOut}>Sign out</button>
    </header>
  )
}
