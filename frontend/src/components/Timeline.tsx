import {
  Check, ChevronRight, Clock, Coins, FileText, Hand, Keyboard, Link2, ListChecks, MousePointerClick,
  MoveVertical, NotebookPen, Timer, X,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Step, Trace } from '../lib/api'
import { actionLabel, fmtCost, fmtSecs, fmtTokens } from '../lib/format'

const ICONS: Record<string, typeof Check> = {
  click: MousePointerClick, type: Keyboard, select_option: ListChecks, navigate: Link2, press_key: Keyboard,
  scroll: MoveVertical, wait: Timer, extract: NotebookPen, done: Check,
}

export function Timeline({
  trace, selected, onSelect, follow,
}: {
  trace: Trace
  selected: number | null
  onSelect: (i: number) => void
  follow: boolean
}) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (follow) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [trace.steps.length, follow])

  const check = trace.events.find((e) => e.kind === 'check')
  return (
    <aside className="flex w-[420px] shrink-0 flex-col border-l border-zinc-800/80 bg-zinc-950">
      <div className="flex items-center justify-between border-b border-zinc-800/80 px-4 py-3">
        <h2 className="text-xs font-semibold tracking-wider text-zinc-400 uppercase">Timeline</h2>
        <span className="font-mono text-[11px] text-zinc-600">{trace.steps.length} steps</span>
      </div>
      <ol className="flex-1 space-y-2 overflow-y-auto p-3">
        {trace.steps.length === 0 && <li className="px-2 py-8 text-center text-sm text-zinc-600">The agent is looking at the page…</li>}
        {trace.steps.map((s) => (
          <StepCard key={s.index} step={s} active={s.index === selected} onClick={() => onSelect(s.index)} />
        ))}
        {trace.result && (
          <li className="rounded-lg bg-zinc-900/60 p-3 ring-1 ring-zinc-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold tracking-wider text-zinc-400 uppercase">Result</span>
              <span className="font-mono text-[11px] text-zinc-500">{trace.result.stop_reason.replace('_', ' ')}</span>
            </div>
            {trace.result.answer && <p className="mt-2 text-sm text-zinc-200">“{trace.result.answer}”</p>}
            {check && (
              <p className={`mt-2 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${check.success ? 'bg-emerald-500/10 text-emerald-300' : 'bg-rose-500/10 text-rose-300'}`}>
                {check.success ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                Eval check {check.success ? 'passed' : 'failed'}
              </p>
            )}
          </li>
        )}
        <div ref={end} />
      </ol>
    </aside>
  )
}

function StepCard({ step, active, onClick }: { step: Step; active: boolean; onClick: () => void }) {
  const [open, setOpen] = useState(false)
  const Icon = ICONS[step.action.name] ?? ChevronRight
  const ok = step.result.ok
  const tokensIn = step.usage.input_tokens + step.usage.cache_read_tokens + step.usage.cache_write_tokens
  return (
    <li
      onClick={onClick}
      className={`cursor-pointer rounded-lg p-3 ring-1 transition ${active ? 'bg-sky-500/[0.07] ring-sky-500/40' : 'bg-zinc-900/60 ring-zinc-800 hover:ring-zinc-700'}`}
    >
      <div className="flex items-start gap-2.5">
        <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-md ${ok ? 'bg-zinc-800 text-zinc-300' : 'bg-rose-500/15 text-rose-300'}`}>
          <Icon className="size-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <code className="truncate text-[12.5px] text-zinc-100">{actionLabel(step.action.name, step.action.args)}</code>
            <span className="shrink-0 font-mono text-[10px] text-zinc-600">#{step.index}</span>
          </div>
          {step.thought && <p className="mt-1 text-[13px] leading-snug text-zinc-400">{step.thought}</p>}
          {!ok && <p className="mt-1.5 text-xs leading-snug text-rose-300/90">{step.result.message}</p>}
          {step.human_note && (
            <p className="mt-1.5 inline-flex items-start gap-1.5 rounded bg-amber-400/10 px-2 py-1 text-xs text-amber-200">
              <Hand className="mt-px size-3 shrink-0" /> Human took over: {step.human_note}
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10.5px] text-zinc-500">
            {step.model && step.latency_s > 0 && (
              <Meta icon={<Clock className="size-3" />} title="model latency">{fmtSecs(step.latency_s)}</Meta>
            )}
            {tokensIn > 0 && (
              <Meta icon={<FileText className="size-3" />} title="input tokens (cached) → output tokens">
                {fmtTokens(tokensIn)}
                {step.usage.cache_read_tokens > 0 && <span className="text-zinc-600"> ({fmtTokens(step.usage.cache_read_tokens)})</span>}
                {' → '}
                {fmtTokens(step.usage.output_tokens)}
              </Meta>
            )}
            {step.cost_usd > 0 && <Meta icon={<Coins className="size-3" />} title="cost">{fmtCost(step.cost_usd)}</Meta>}
            <button
              onClick={(e) => { e.stopPropagation(); setOpen(!open) }}
              className="ml-auto inline-flex items-center gap-0.5 text-zinc-500 hover:text-zinc-300"
            >
              details <ChevronRight className={`size-3 transition ${open ? 'rotate-90' : ''}`} />
            </button>
          </div>
          {open && <StepDetails step={step} />}
        </div>
      </div>
    </li>
  )
}

function Meta({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return <span title={title} className="inline-flex items-center gap-1">{icon}{children}</span>
}

function StepDetails({ step }: { step: Step }) {
  return (
    <div className="mt-3 space-y-3 border-t border-zinc-800 pt-3" onClick={(e) => e.stopPropagation()}>
      <Detail label="URL"><span className="font-mono break-all">{step.url}</span></Detail>
      {step.feedback && <Detail label="Told the model">{step.feedback}</Detail>}
      {step.thinking && <Detail label="Thinking (summary)"><span className="whitespace-pre-wrap">{step.thinking}</span></Detail>}
      <Detail label="Result">{step.result.message}</Detail>
      {step.observation && (
        <Detail label="Page snapshot the model saw">
          <pre className="max-h-72 overflow-auto rounded-md bg-zinc-950 p-2 font-mono text-[10.5px] leading-relaxed text-zinc-400 ring-1 ring-zinc-800">
            {step.observation}
          </pre>
        </Detail>
      )}
      <p className="font-mono text-[10px] text-zinc-600">{step.model || 'no model'} · action took {fmtSecs(step.action_s)}</p>
    </div>
  )
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-semibold tracking-wider text-zinc-500 uppercase">{label}</div>
      <div className="text-xs leading-relaxed text-zinc-300">{children}</div>
    </div>
  )
}
