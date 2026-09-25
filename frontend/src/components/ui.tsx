import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { useT } from '../i18n'

const cx = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(' ')
export { cx }

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
const variants: Record<Variant, string> = {
  primary: 'bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-indigo-300',
  secondary: 'bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 disabled:text-slate-400',
  danger: 'bg-white text-rose-600 ring-1 ring-rose-200 hover:bg-rose-50 disabled:text-rose-300',
  ghost: 'text-slate-600 hover:bg-slate-100 disabled:text-slate-300',
}

export function Button({
  variant = 'primary',
  className,
  loading,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed',
        variants[variant],
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>{children}</div>
}

export function CardHeader({ title, action, subtitle }: { title: ReactNode; action?: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cx('animate-spin text-current', className ?? 'h-5 w-5')} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
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
  return <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{message}</div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="px-4 py-8 text-center text-sm text-slate-500">{children}</div>
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100'

export const Input = (props: InputHTMLAttributes<HTMLInputElement>) => (
  <input {...props} className={cx(inputClass, props.className)} />
)
export const Textarea = (props: TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea {...props} className={cx(inputClass, props.className)} />
)
export const Select = (props: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...props} className={cx(inputClass, props.className)} />
)

const statusColors: Record<string, string> = {
  PENDING: 'bg-slate-100 text-slate-600',
  PLANNING: 'bg-sky-100 text-sky-700',
  RUNNING: 'bg-indigo-100 text-indigo-700',
  REVIEW: 'bg-amber-100 text-amber-800',
  PAUSED: 'bg-yellow-100 text-yellow-800',
  WAITING: 'bg-yellow-100 text-yellow-800',
  WAITING_USER: 'bg-yellow-100 text-yellow-800',
  AWAITING_PLAN_APPROVAL: 'bg-yellow-100 text-yellow-800',
  FINALIZING: 'bg-violet-100 text-violet-700',
  COMPLETED: 'bg-emerald-100 text-emerald-700',
  FAILED: 'bg-rose-100 text-rose-700',
  CANCELLED: 'bg-slate-200 text-slate-600',
  APPROVED: 'bg-emerald-100 text-emerald-700',
  NEEDS_REVISION: 'bg-amber-100 text-amber-800',
}
const ACTIVE = new Set(['PLANNING', 'RUNNING', 'REVIEW', 'FINALIZING'])

export function StatusBadge({ status }: { status: string }) {
  const t = useT()
  const label = (t.status as Record<string, string>)[status] ?? status
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium', statusColors[status] ?? 'bg-slate-100')}>
      {ACTIVE.has(status) && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {label}
    </span>
  )
}

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-medium', className ?? 'bg-slate-100 text-slate-600')}>{children}</span>
}

// Cores consistentes por agente (pela ordem em que aparecem na lista de agentes).
const AGENT_PALETTE = [
  { dot: 'bg-sky-500', text: 'text-sky-700', soft: 'bg-sky-50 border-sky-200' },
  { dot: 'bg-violet-500', text: 'text-violet-700', soft: 'bg-violet-50 border-violet-200' },
  { dot: 'bg-amber-500', text: 'text-amber-700', soft: 'bg-amber-50 border-amber-200' },
  { dot: 'bg-emerald-500', text: 'text-emerald-700', soft: 'bg-emerald-50 border-emerald-200' },
  { dot: 'bg-rose-500', text: 'text-rose-700', soft: 'bg-rose-50 border-rose-200' },
]
export function agentColor(index: number) {
  return AGENT_PALETTE[(index < 0 ? 0 : index) % AGENT_PALETTE.length]
}

export function AgentName({ name, index }: { name: string; index: number }) {
  const color = agentColor(index)
  return (
    <span className={cx('inline-flex items-center gap-1.5 font-semibold', color.text)}>
      <span className={cx('h-2 w-2 rounded-full', color.dot)} />
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
