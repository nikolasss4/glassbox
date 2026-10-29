import type { ReactNode } from 'react'
import type { RunStatus, RunSummary } from '../lib/api'

export function Pill({ tone, children }: { tone: 'sky' | 'emerald' | 'rose' | 'amber' | 'zinc'; children: ReactNode }) {
  const tones = {
    sky: 'bg-sky-500/10 text-sky-300 ring-sky-500/30',
    emerald: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
    rose: 'bg-rose-500/10 text-rose-300 ring-rose-500/30',
    amber: 'bg-amber-500/10 text-amber-300 ring-amber-500/30',
    zinc: 'bg-zinc-500/10 text-zinc-400 ring-zinc-500/30',
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${tones[tone]}`}>
      {children}
    </span>
  )
}

export function StatusPill({ status, run }: { status: RunStatus | null; run?: Pick<RunSummary, 'result'> | null }) {
  if (status === 'running')
    return (
      <Pill tone="sky">
        <span className="size-1.5 animate-pulse rounded-full bg-sky-400" /> live
      </Pill>
    )
  if (status === 'paused') return <Pill tone="amber">human in control</Pill>
  const r = run?.result
  if (!r) return <Pill tone="zinc">{status ?? '…'}</Pill>
  if (r.stop_reason === 'done') return r.success_claimed ? <Pill tone="emerald">done</Pill> : <Pill tone="rose">gave up</Pill>
  return <Pill tone="rose">{r.stop_reason.replace('_', ' ')}</Pill>
}

export function Button({
  children, onClick, tone = 'default', disabled, type = 'button', title,
}: {
  children: ReactNode
  onClick?: () => void
  tone?: 'default' | 'primary' | 'warn' | 'danger'
  disabled?: boolean
  type?: 'button' | 'submit'
  title?: string
}) {
  const tones = {
    default: 'bg-zinc-800 text-zinc-100 hover:bg-zinc-700 ring-zinc-700',
    primary: 'bg-sky-500 text-zinc-950 hover:bg-sky-400 ring-sky-400',
    warn: 'bg-amber-400 text-zinc-950 hover:bg-amber-300 ring-amber-300',
    danger: 'bg-zinc-800 text-rose-300 hover:bg-rose-500/20 ring-zinc-700',
  }
  return (
    <button
      type={type}
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ring-1 ring-inset transition disabled:cursor-not-allowed disabled:opacity-40 ${tones[tone]}`}
    >
      {children}
    </button>
  )
}
