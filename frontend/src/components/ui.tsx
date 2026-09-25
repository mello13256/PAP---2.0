import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { useT } from '../i18n'

const cx = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(' ')
export { cx }

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
const variants: Record<Variant, string> = {
  primary:
    'bg-gradient-to-b from-indigo-500 to-indigo-600 text-white shadow-sm shadow-indigo-500/30 hover:from-indigo-500 hover:to-indigo-500 disabled:opacity-50',
  secondary: 'bg-white text-slate-700 ring-1 ring-slate-200 shadow-sm hover:bg-slate-50 disabled:text-slate-400',
  danger: 'bg-white text-rose-600 ring-1 ring-rose-200 hover:bg-rose-50 disabled:text-rose-300',
  ghost: 'text-slate-600 hover:bg-slate-900/5 disabled:text-slate-300',
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  loading,
  icon,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md'; loading?: boolean; icon?: ReactNode }) {
  return (
    <button
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100',
        size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3.5 py-2 text-sm',
        variants[variant],
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cx('rounded-2xl border border-slate-200/80 bg-white/90 shadow-sm shadow-slate-200/50 backdrop-blur', className)}>
      {children}
    </div>
  )
}

export function CardHeader({ title, icon, action, subtitle }: { title: ReactNode; icon?: ReactNode; action?: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
      <div className="flex items-center gap-2.5">
        {icon && <span className="text-indigo-500">{icon}</span>}
        <div>
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}

export function PageHeader({ title, subtitle, action, back }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; back?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {back}
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <div className="mt-1 max-w-3xl text-sm text-slate-500">{subtitle}</div>}
      </div>
      {action && <div className="flex flex-wrap items-center gap-2">{action}</div>}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx('animate-spin', className ?? 'h-5 w-5')} />
}

export function Loading() {
  const t = useT()
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-slate-500">
      <Spinner className="h-4 w-4" /> {t.common.loading}
    </div>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  const t = useT()
  const message = error instanceof Error ? error.message : t.common.error
  return <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{message}</div>
}

export function Empty({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-10 text-center text-sm text-slate-500">
      {icon && <div className="grid h-11 w-11 place-items-center rounded-2xl bg-slate-100 text-slate-400">{icon}</div>}
      {children}
    </div>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100'

export const Input = (props: InputHTMLAttributes<HTMLInputElement>) => <input {...props} className={cx(inputClass, props.className)} />
export const Textarea = (props: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...props} className={cx(inputClass, props.className)} />
export const Select = (props: SelectHTMLAttributes<HTMLSelectElement>) => <select {...props} className={cx(inputClass, props.className)} />

const statusColors: Record<string, string> = {
  PENDING: 'bg-slate-100 text-slate-600 ring-slate-200',
  PLANNING: 'bg-sky-50 text-sky-700 ring-sky-200',
  RUNNING: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  REVIEW: 'bg-amber-50 text-amber-800 ring-amber-200',
  PAUSED: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  WAITING: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  WAITING_USER: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  AWAITING_PLAN_APPROVAL: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  FINALIZING: 'bg-violet-50 text-violet-700 ring-violet-200',
  COMPLETED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  FAILED: 'bg-rose-50 text-rose-700 ring-rose-200',
  CANCELLED: 'bg-slate-100 text-slate-600 ring-slate-200',
  APPROVED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  NEEDS_REVISION: 'bg-amber-50 text-amber-800 ring-amber-200',
}
const ACTIVE = new Set(['PLANNING', 'RUNNING', 'REVIEW', 'FINALIZING'])

export function StatusBadge({ status }: { status: string }) {
  const t = useT()
  const label = (t.status as Record<string, string>)[status] ?? status
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', statusColors[status] ?? 'bg-slate-100')}>
      {ACTIVE.has(status) && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {label}
    </span>
  )
}

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium', className ?? 'bg-slate-100 text-slate-600')}>{children}</span>
}

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cx('h-2 overflow-hidden rounded-full bg-slate-100', className)}>
      <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  )
}

export function Stat({ label, value, icon }: { label: string; value: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      {icon && <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-600">{icon}</div>}
      <div className="min-w-0">
        <div className="text-xs text-slate-500">{label}</div>
        <div className="truncate text-base font-semibold tabular-nums text-slate-900">{value}</div>
      </div>
    </div>
  )
}

// Cores consistentes por agente (pela ordem em que aparecem na lista de agentes).
const AGENT_PALETTE = [
  { dot: 'bg-sky-500', text: 'text-sky-700', soft: 'bg-sky-50', ring: 'ring-sky-200', grad: 'from-sky-400 to-blue-600' },
  { dot: 'bg-violet-500', text: 'text-violet-700', soft: 'bg-violet-50', ring: 'ring-violet-200', grad: 'from-violet-400 to-fuchsia-600' },
  { dot: 'bg-amber-500', text: 'text-amber-700', soft: 'bg-amber-50', ring: 'ring-amber-200', grad: 'from-amber-400 to-orange-600' },
  { dot: 'bg-emerald-500', text: 'text-emerald-700', soft: 'bg-emerald-50', ring: 'ring-emerald-200', grad: 'from-emerald-400 to-teal-600' },
  { dot: 'bg-rose-500', text: 'text-rose-700', soft: 'bg-rose-50', ring: 'ring-rose-200', grad: 'from-rose-400 to-pink-600' },
]
export function agentColor(index: number) {
  return AGENT_PALETTE[(index < 0 ? 0 : index) % AGENT_PALETTE.length]
}

export function Avatar({ name, index, size = 'md' }: { name: string; index: number; size?: 'sm' | 'md' | 'lg' }) {
  const color = agentColor(index)
  const dims = { sm: 'h-6 w-6 text-[10px]', md: 'h-8 w-8 text-xs', lg: 'h-11 w-11 text-sm' }[size]
  return (
    <span className={cx('grid shrink-0 place-items-center rounded-full bg-gradient-to-br font-bold text-white shadow-sm', color.grad, dims)}>
      {name.slice(0, 2).toUpperCase()}
    </span>
  )
}

export function AgentName({ name, index, avatar }: { name: string; index: number; avatar?: boolean }) {
  const color = agentColor(index)
  return (
    <span className={cx('inline-flex items-center gap-1.5 font-semibold', color.text)}>
      {avatar ? <Avatar name={name} index={index} size="sm" /> : <span className={cx('h-2 w-2 rounded-full', color.dot)} />}
      {name}
    </span>
  )
}

export function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

export function formatDuration(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)} s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m} min ${s.toString().padStart(2, '0')} s`
}

export function formatBytes(bytes: number) {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(0)} MB`
  return `${Math.round(bytes / 1e3)} KB`
}
