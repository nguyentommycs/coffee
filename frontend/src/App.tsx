import { useState } from 'react'
import { getUsername } from './auth'
import LoginScreen from './components/LoginScreen'
import Header from './components/Header'
import type { View } from './components/Header'
import BeansPanel from './components/BeansPanel'
import RecommendationsPanel from './components/RecommendationsPanel'
import TasteProfilePanel from './components/TasteProfilePanel'
import TracesPanel from './components/TracesPanel'

export default function App() {
  const [username, setUsername] = useState<string | null>(() => getUsername())
  const [view, setView] = useState<View>('dashboard')

  if (!username) {
    return <LoginScreen onLogin={setUsername} />
  }

  return (
    <>
      <Header
        username={username}
        view={view}
        onViewChange={setView}
        onSignOut={() => setUsername(null)}
      />
      <main>
        {view === 'traces' ? (
          <TracesPanel userId={username} />
        ) : (
          <>
            <BeansPanel userId={username} />
            <div className="bottom-panels">
              <RecommendationsPanel userId={username} />
              <TasteProfilePanel userId={username} />
            </div>
          </>
        )}
      </main>
    </>
  )
}
