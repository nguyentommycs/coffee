import { useState } from 'react'
import { getUsername } from './auth'
import LoginScreen from './components/LoginScreen'
import Header from './components/Header'

function MainView() {
  return <p style={{ padding: '1.5rem' }}>Main view coming soon.</p>
}

export default function App() {
  const [username, setUsername] = useState<string | null>(() => getUsername())

  if (!username) {
    return <LoginScreen onLogin={setUsername} />
  }

  return (
    <>
      <Header username={username} onSignOut={() => setUsername(null)} />
      <main>
        <MainView />
      </main>
    </>
  )
}
