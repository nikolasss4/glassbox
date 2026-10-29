import { useRun } from '../lib/useRun'
import { fmtCost, fmtSecs } from '../lib/format'
import { StatusPill } from './ui'
import { Viewport } from './Viewport'

export function RunView({ runId }: { runId: string }) {
  const { trace, frame, status, error } = useRun(runId)

  if (error) return <div className="p-10 text-rose-300">Could not load run: {error}</div>
  if (!trace) return <div className="p-10 text-zinc-500">Loading…</div>

  const last = trace.steps.at(-1)
  const totalCost = trace.steps.reduce((a, s) => a + (s.cost_usd ?? 0), 0)

  return (
    <div className="flex h-full min-w-0 flex-col">
      <header className="flex items-start justify-between gap-6 border-b border-zinc-800/80 px-6 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <StatusPill status={status} run={trace} />
            <span className="font-mono text-xs text-zinc-500">{trace.provider}</span>
            {trace.task_id && <span className="font-mono text-xs text-zinc-600">· {trace.task_id}</span>}
          </div>
          <h1 className="mt-1.5 text-[15px] leading-snug font-medium text-zinc-100">{trace.goal}</h1>
          {trace.result?.error && (
            <p className="mt-2 rounded-md bg-rose-500/10 px-2.5 py-1.5 font-mono text-xs text-rose-300 ring-1 ring-rose-500/20">
              {trace.result.error}
            </p>
          )}
        </div>
        <dl className="flex shrink-0 gap-6 text-right">
          <Stat label="steps" value={String(trace.steps.length)} />
          <Stat label="cost" value={fmtCost(totalCost)} />
          {trace.result && <Stat label="time" value={fmtSecs(trace.result.duration_s)} />}
        </dl>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <Viewport frame={status !== 'finished' ? frame : null} imageUrl={last?.screenshot_url} url={last?.url ?? trace.start_url ?? ''} />
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] tracking-wider text-zinc-500 uppercase">{label}</dt>
      <dd className="font-mono text-sm text-zinc-200">{value}</dd>
    </div>
  )
}
