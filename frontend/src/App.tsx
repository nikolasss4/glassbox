import { NewRun } from './components/NewRun'
import { RunView } from './components/RunView'
import { Sidebar } from './components/Sidebar'
import { useRoute } from './lib/route'

export default function App() {
  const { runId } = useRoute()
  return (
    <div className="flex h-full">
      <Sidebar activeId={runId} />
      <main className="min-w-0 flex-1">{runId ? <RunView key={runId} runId={runId} /> : <NewRun />}</main>
    </div>
  )
}
