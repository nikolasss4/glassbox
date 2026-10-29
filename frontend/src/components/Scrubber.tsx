import { ChevronLeft, ChevronRight, Pause, Play, Radio } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Step } from '../lib/api'
import { actionLabel } from '../lib/format'

function tone(s: Step): string {
  if (s.human_note) return 'bg-amber-400'
  if (!s.result.ok) return 'bg-rose-400'
  if (s.action.name === 'done') return s.action.args.success ? 'bg-emerald-400' : 'bg-rose-400'
  return 'bg-zinc-500'
}

/** Replay control: scrub, step or play through a run's recorded steps. */
export function Scrubber({
  steps, selected, onSelect, live,
}: {
  steps: Step[]
  selected: number | null
  onSelect: (i: number | null) => void
  live: boolean
}) {
  const [playing, setPlaying] = useState(false)
  const last = steps.length - 1
  const current = selected ?? last
  const pos = Math.max(0, steps.findIndex((s) => s.index === current))

  const go = (p: number) => onSelect(steps[Math.min(Math.max(p, 0), last)]?.index ?? null)

  // Playback stops by itself at the last step.
  const isPlaying = playing && pos < last
  useEffect(() => {
    if (!isPlaying) return
    const t = setTimeout(() => onSelect(steps[pos + 1].index), 900)
    return () => clearTimeout(t)
  }, [isPlaying, pos, steps, onSelect])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if ((e.target as HTMLElement | null)?.getAttribute('tabindex') === '0') return // takeover layer
      if (e.key === 'ArrowLeft') go(pos - 1)
      else if (e.key === 'ArrowRight') go(pos + 1)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (steps.length === 0) return null
  const step = steps[pos]
  const btn = 'grid size-8 place-items-center rounded-md text-zinc-300 hover:bg-zinc-800 disabled:opacity-30'

  return (
    <div className="mt-4 rounded-xl bg-zinc-900/60 px-4 py-3 ring-1 ring-zinc-800">
      <div className="flex items-center gap-2">
        <button className={btn} onClick={() => go(pos - 1)} disabled={pos === 0} aria-label="Previous step">
          <ChevronLeft className="size-4" />
        </button>
        <button
          className={btn}
          onClick={() => {
            if (pos >= last) go(0)
            setPlaying(!isPlaying)
          }}
          aria-label={isPlaying ? 'Pause replay' : 'Play replay'}
        >
          {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
        </button>
        <button className={btn} onClick={() => go(pos + 1)} disabled={pos >= last} aria-label="Next step">
          <ChevronRight className="size-4" />
        </button>

        <div className="relative mx-2 flex-1">
          <div className="pointer-events-none absolute inset-x-0 top-1/2 flex -translate-y-1/2 justify-between px-[7px]">
            {steps.map((s) => (
              <span key={s.index} className={`h-2.5 w-1 rounded-full ${tone(s)} ${s.index === current ? 'opacity-0' : 'opacity-70'}`} />
            ))}
          </div>
          <input
            type="range"
            className="scrubber relative"
            min={0}
            max={Math.max(last, 0)}
            value={pos}
            onChange={(e) => go(Number(e.target.value))}
            aria-label="Replay position"
          />
        </div>

        <span className="w-16 text-right font-mono text-xs text-zinc-400">
          {pos + 1} / {steps.length}
        </span>
        {live && (
          <button
            onClick={() => onSelect(null)}
            className={`ml-1 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
              selected === null ? 'bg-sky-500/15 text-sky-300' : 'text-zinc-400 hover:bg-zinc-800'
            }`}
          >
            <Radio className="size-3.5" /> Live
          </button>
        )}
      </div>
      <p className="mt-1.5 truncate pl-[7.5rem] font-mono text-[11px] text-zinc-500">
        #{step.index} · {actionLabel(step.action.name, step.action.args)}
      </p>
    </div>
  )
}
