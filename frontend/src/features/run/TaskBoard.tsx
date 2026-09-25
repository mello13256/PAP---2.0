import { CheckCircle2, CircleDashed, Loader2, ShieldCheck, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Task, TaskStatus } from '../../api/types'
import { Avatar, Badge, cx } from '../../components/ui'
import { useAgentIndex } from '../../hooks/useAgentIndex'
import { useT } from '../../i18n'

type ColumnKey = 'PENDING' | 'RUNNING' | 'REVIEW' | 'COMPLETED' | 'FAILED'
const COLUMNS: { key: ColumnKey; statuses: TaskStatus[]; tone: string; icon: ReactNode }[] = [
  { key: 'PENDING', statuses: ['PENDING', 'WAITING'], tone: 'text-slate-500', icon: <CircleDashed className="h-3.5 w-3.5" /> },
  { key: 'RUNNING', statuses: ['RUNNING'], tone: 'text-indigo-600', icon: <Loader2 className="h-3.5 w-3.5 animate-spin" /> },
  { key: 'REVIEW', statuses: ['REVIEW'], tone: 'text-amber-600', icon: <ShieldCheck className="h-3.5 w-3.5" /> },
  { key: 'COMPLETED', statuses: ['COMPLETED'], tone: 'text-emerald-600', icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
  { key: 'FAILED', statuses: ['FAILED', 'CANCELLED'], tone: 'text-rose-600', icon: <XCircle className="h-3.5 w-3.5" /> },
]

export function TaskBoard({ tasks }: { tasks: Task[] }) {
  const t = useT()
  const agents = useAgentIndex()
  if (!tasks.length) return <div className="p-6 text-center text-sm text-slate-400">{t.run.noTasks}</div>
  return (
    <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-5">
      {COLUMNS.map((col) => {
        const items = tasks.filter((task) => col.statuses.includes(task.status))
        return (
          <div key={col.key} className="rounded-xl bg-slate-50 p-2 ring-1 ring-slate-200/70">
            <div className={cx('flex items-center gap-1.5 px-1.5 pb-2 pt-1 text-xs font-semibold', col.tone)}>
              {col.icon} {t.columns[col.key]}
              <span className="ml-auto rounded-full bg-white px-1.5 text-slate-500 ring-1 ring-slate-200">{items.length}</span>
            </div>
            <ul className="space-y-2">
              {items.map((task) => (
                <li
                  key={task.id}
                  className={cx(
                    'animate-in rounded-lg border bg-white p-2.5 shadow-sm transition',
                    task.status === 'RUNNING' ? 'border-indigo-300 ring-2 ring-indigo-100' : task.status === 'REVIEW' ? 'border-amber-300 ring-2 ring-amber-100' : 'border-slate-200',
                  )}
                >
                  <div className="flex items-start gap-1.5">
                    <Badge className="shrink-0 bg-slate-800 font-mono text-white">{task.key}</Badge>
                    <span className="text-sm font-medium leading-snug text-slate-800">{task.title}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                    {task.assigned_agent_id && (
                      <span className="inline-flex items-center gap-1 font-medium text-slate-700">
                        <Avatar name={agents.name(task.assigned_agent_id) ?? '?'} index={agents.index(task.assigned_agent_id)} size="sm" />
                        {agents.name(task.assigned_agent_id)}
                      </span>
                    )}
                    {task.required_capability && <Badge>{task.required_capability}</Badge>}
                    {task.iteration_count > 1 && <Badge className="bg-amber-100 text-amber-800">×{task.iteration_count}</Badge>}
                  </div>
                  {task.depends_on.length > 0 && <div className="mt-1 text-[11px] text-slate-400">{t.run.dependsOn} {task.depends_on.join(', ')}</div>}
                  {task.status !== 'PENDING' && task.result && (
                    <details className="mt-1.5 text-xs text-slate-600">
                      <summary className="cursor-pointer select-none text-slate-400 hover:text-slate-600">{t.kinds.TASK_RESULT}</summary>
                      <p className="mt-1 whitespace-pre-wrap">{task.result}</p>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
