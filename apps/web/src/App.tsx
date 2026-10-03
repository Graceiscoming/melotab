import { useEffect } from 'react'
import { Library } from './features/library/Library'
import { StatusBar } from './features/status/StatusBar'
import { Workspace } from './features/workspace/Workspace'
import { useStore } from './store/store'

export default function App() {
  const { currentId, song, error, setError, connect, refreshProjects } = useStore()

  useEffect(() => {
    const disconnect = connect()
    void refreshProjects()
    return disconnect
  }, [connect, refreshProjects])

  return (
    <div className="app">
      <header className="topbar"><span className="logo">🎸 MeloTab</span></header>
      {error && (
        <div className="errorbar" role="alert" data-testid="error">
          {error} <button onClick={() => setError(null)}>ปิด</button>
        </div>
      )}
      <main>{currentId && song ? <Workspace /> : <Library />}</main>
      <StatusBar />
    </div>
  )
}
