export const fmtCost = (usd: number) => (usd === 0 ? '$0' : usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(3)}`)
export const fmtSecs = (s: number) => (s < 1 ? `${Math.round(s * 1000)}ms` : `${s.toFixed(1)}s`)
export const fmtTokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`)

export function timeAgo(iso: string): string {
  const secs = (Date.now() - new Date(iso).getTime()) / 1000
  if (secs < 60) return 'just now'
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return new Date(iso).toLocaleDateString()
}

export function actionLabel(name: string, args: Record<string, unknown>): string {
  switch (name) {
    case 'click': return `click ${args.ref}`
    case 'type': return `type "${args.text}" → ${args.ref}${args.submit ? ' ⏎' : ''}`
    case 'select_option': return `select "${args.option}" in ${args.ref}`
    case 'navigate': return `open ${args.url}`
    case 'press_key': return `press ${args.key}`
    case 'scroll': return `scroll ${args.direction}`
    case 'wait': return `wait ${args.seconds}s`
    case 'extract': return `note: ${args.data}`
    case 'done': return args.success ? `done: ${args.answer || 'success'}` : `gave up: ${args.answer}`
    default: return name
  }
}
