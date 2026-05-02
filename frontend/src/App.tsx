import { useState } from 'react'
import { getUsername } from './auth'
import LoginScreen from './components/LoginScreen'
import Header from './components/Header'
import BeansPanel from './components/BeansPanel'

export default function App() {
  const [username, setUsername] = useState<string | null>(() => getUsername())

  if (!username) {
    return <LoginScreen onLogin={setUsername} />
  }

  return (
    <>
      <Header username={username} onSignOut={() => setUsername(null)} />
      <main>
        <BeansPanel userId={username} />
      </main>
    </>
  )
}
