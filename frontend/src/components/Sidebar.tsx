import { FlaskConical, Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api, type RunSummary } from '../lib/api'
import { timeAgo } from '../lib/format'
import { goHome, goToRun } from '../lib/route'
import { StatusPill } from './ui'

export function Sidebar({ activeId }: { activeId: string | null }) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [query, setQuery] = useState('')
  const [showEvals, setShowEvals] = useState(false)

  useEffect(() => {
    let alive = true
    const load = () => api.runs().then((r) => alive && setRuns(r), () => {})
    load()
    const timer = setInterval(load, 3000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const shown = useMemo(() => {
    const q = query.toLowerCase()
    return runs.filter(
      (r) =>
        (showEvals || !r.eval) &&
        (!q || r.goal.toLowerCase().includes(q) || r.provider.includes(q) || (r.task_id ?? '').includes(q)),
    )
  }, [runs, query, showEvals])
  const evalCount = runs.filter((r) => r.eval).length

  return (
    <aside className="flex w-80 shrink-0 flex-col border-r border-zinc-800/80 bg-zinc-950">
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <a href="#/" className="flex items-center gap-2">
          <img src="/favicon.svg" alt="" className="size-6" />
          <span className="text-[15px] font-semibold tracking-tight text-zinc-50">glassbox</span>
        </a>
        <button
          onClick={goHome}
          className="inline-flex items-center gap-1 rounded-md bg-sky-500 px-2.5 py-1 text-xs font-semibold text-zinc-950 hover:bg-sky-400"
        >
          <Plus className="size-3.5" /> New run
        </button>
      </div>
      <div className="px-3 pb-2">
        <label className="flex items-center gap-2 rounded-md bg-zinc-900 px-2.5 py-1.5 ring-1 ring-zinc-800 focus-within:ring-sky-500/50">
          <Search className="size-3.5 text-zinc-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter runs"
            className="w-full bg-transparent text-sm placeholder:text-zinc-600 focus:outline-none"
          />
        </label>
        {evalCount > 0 && (
          <label className="mt-2 flex cursor-pointer items-center gap-2 px-1 text-xs text-zinc-500">
            <input type="checkbox" checked={showEvals} onChange={(e) => setShowEvals(e.target.checked)} className="accent-sky-500" />
            <FlaskConical className="size-3.5" /> Show eval runs ({evalCount})
          </label>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-4">
        {shown.length === 0 && <p className="px-3 py-6 text-center text-sm text-zinc-600">No runs yet.</p>}
        {shown.map((r) => (
          <button
            key={r.id}
            onClick={() => goToRun(r.id)}
            className={`group mb-1 block w-full rounded-lg px-3 py-2.5 text-left transition ${
              r.id === activeId ? 'bg-zinc-800/80 ring-1 ring-zinc-700' : 'hover:bg-zinc-900'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <StatusPill status={r.status} run={r} />
              <span className="text-[11px] text-zinc-600">{timeAgo(r.created_at)}</span>
            </div>
            <p className="mt-1.5 line-clamp-2 text-[13px] leading-snug text-zinc-300">{r.goal}</p>
            <p className="mt-1 flex items-center gap-1.5 font-mono text-[11px] text-zinc-500">
              {r.eval && <FlaskConical className="size-3" />}
              <span className="truncate">{r.provider}</span>
              <span>·</span>
              <span>{r.n_steps} steps</span>
            </p>
          </button>
        ))}
      </nav>
    </aside>
  )
}
