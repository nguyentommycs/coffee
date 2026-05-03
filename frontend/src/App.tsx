import { useState } from 'react'
import { getUsername } from './auth'
import LoginScreen from './components/LoginScreen'
import Header from './components/Header'
import BeansPanel from './components/BeansPanel'
import RecommendationsPanel from './components/RecommendationsPanel'
import TasteProfilePanel from './components/TasteProfilePanel'

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
        <div className="bottom-panels">
          <RecommendationsPanel userId={username} />
          <TasteProfilePanel userId={username} />
        </div>
      </main>
    </>
  )
}
