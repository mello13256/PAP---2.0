import type { Task, TaskStatus } from '../../api/types'
import { AgentName, Badge, cx } from '../../components/ui'
import { useAgentIndex } from '../../hooks/useAgentIndex'
import { useT } from '../../i18n'

const COLUMNS: { key: keyof ReturnType<typeof useT>['columns']; statuses: TaskStatus[]; tone: string }[] = [
  { key: 'PENDING', statuses: ['PENDING', 'WAITING'], tone: 'border-t-slate-300' },
  { key: 'RUNNING', statuses: ['RUNNING'], tone: 'border-t-indigo-400' },
  { key: 'REVIEW', statuses: ['REVIEW'], tone: 'border-t-amber-400' },
  { key: 'COMPLETED', statuses: ['COMPLETED'], tone: 'border-t-emerald-400' },
  { key: 'FAILED', statuses: ['FAILED', 'CANCELLED'], tone: 'border-t-rose-400' },
]

export function TaskBoard({ tasks }: { tasks: Task[] }) {
  const t = useT()
  const agents = useAgentIndex()
  if (!tasks.length) return <div className="p-6 text-center text-sm text-slate-400">{t.run.noTasks}</div>
  return (
    <div className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-5">
      {COLUMNS.map((col) => {
        const items = tasks.filter((task) => col.statuses.includes(task.status))
        return (
          <div key={col.key} className={cx('rounded-lg border border-t-4 border-slate-200 bg-slate-50/70', col.tone)}>
            <div className="flex items-center justify-between px-2.5 py-1.5 text-xs font-semibold text-slate-600">
              {t.columns[col.key]} <span className="text-slate-400">{items.length}</span>
            </div>
            <ul className="space-y-2 p-2 pt-0">
              {items.map((task) => (
                <li key={task.id} className="rounded-md border border-slate-200 bg-white p-2 shadow-sm">
                  <div className="flex items-start gap-1.5">
                    <Badge className="shrink-0 bg-slate-800 font-mono text-white">{task.key}</Badge>
                    <span className="text-sm font-medium leading-snug">{task.title}</span>
                  </div>
                  {task.assigned_agent_id && (
                    <div className="mt-1.5 text-xs">
                      <AgentName name={agents.name(task.assigned_agent_id) ?? '?'} index={agents.index(task.assigned_agent_id)} />
                    </div>
                  )}
                  <div className="mt-1 flex flex-wrap gap-1 text-[11px] text-slate-500">
                    {task.required_capability && <Badge>{task.required_capability}</Badge>}
                    {task.depends_on.length > 0 && <span>{t.run.dependsOn} {task.depends_on.join(', ')}</span>}
                    {task.iteration_count > 1 && <Badge className="bg-amber-100 text-amber-800">{task.iteration_count} {t.run.iterations}</Badge>}
                  </div>
                  {task.status !== 'PENDING' && task.result && (
                    <details className="mt-1 text-xs text-slate-600">
                      <summary className="cursor-pointer text-slate-400">{t.kinds.TASK_RESULT}</summary>
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
