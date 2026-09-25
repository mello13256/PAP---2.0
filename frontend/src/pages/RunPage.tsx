import { ChevronLeft, FileCode2, KanbanSquare, MessagesSquare, Pause, Play, Send, Square } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { useMetrics, useReviews, useRun, useRunControl, useSendInstruction, useStrategies, useTasks } from '../api/hooks'
import type { RunStatus } from '../api/types'
import { Avatar, Button, Card, CardHeader, ErrorBox, Input, Loading, Progress, StatusBadge, cx } from '../components/ui'
import { FileExplorer } from '../features/files/FileExplorer'
import { AgentRoom } from '../features/run/AgentRoom'
import { MetricsCard, ResultCard, ReviewsCard } from '../features/run/RunSidebar'
import { TaskBoard } from '../features/run/TaskBoard'
import { useAgentIndex } from '../hooks/useAgentIndex'
import { useRunStream } from '../hooks/useRunStream'
import { useT } from '../i18n'

const ACTIVE = new Set<RunStatus>(['PLANNING', 'RUNNING', 'FINALIZING', 'PAUSED'])

function phaseIndex(status: RunStatus, hasTasks: boolean): number {
  if (status === 'PENDING' || status === 'PLANNING') return 0
  if (status === 'FINALIZING') return 2
  if (status === 'COMPLETED') return 3
  return hasTasks ? 1 : 0
}

export function RunPage() {
  const t = useT()
  const { runId = '' } = useParams()
  const run = useRun(runId)
  const tasks = useTasks(runId)
  const reviews = useReviews(runId)
  const metrics = useMetrics(runId)
  const { data: strategies = [] } = useStrategies()
  const agents = useAgentIndex()
  const control = useRunControl(runId)
  const instruction = useSendInstruction(runId)
  const [text, setText] = useState('')
  const [tab, setTab] = useState<'room' | 'files'>('room')
  const stream = useRunStream(runId, run.data?.project_id)

  const changedFiles = useMemo(
    () => new Set(stream.timeline.flatMap((i) => (i.type === 'tool' && i.tool.name === 'write_file' && i.tool.ok ? [i.tool.arguments.path] : []))),
    [stream.timeline],
  )

  if (run.isLoading) return <Loading />
  if (run.error) return <ErrorBox error={run.error} />
  const r = run.data!
  const taskList = tasks.data ?? []
  const done = taskList.filter((x) => x.status === 'COMPLETED').length
  const active = ACTIVE.has(r.status)
  const strategy = strategies.find((s) => s.key === r.strategy_key)
  const phase = phaseIndex(r.status, taskList.length > 0)
  const phases = [t.run.phasePlanning, t.run.phaseExecution, t.run.phaseFinal]

  const send = (e: FormEvent) => {
    e.preventDefault()
    if (text.trim()) instruction.mutate(text, { onSuccess: () => setText('') })
  }

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-start gap-4 p-5">
          <div className="min-w-0 flex-1">
            <Link to={`/projects/${r.project_id}`} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ChevronLeft className="h-4 w-4" />{t.common.back}</Link>
            <div className="mt-2 flex flex-wrap items-center gap-2.5">
              <StatusBadge status={r.status} />
              <span className={cx('inline-flex items-center gap-1 text-xs', stream.connected ? 'text-emerald-600' : 'text-slate-400')}>
                <span className={cx('h-1.5 w-1.5 rounded-full', stream.connected ? 'bg-emerald-500' : 'bg-slate-300')} />
                {stream.connected ? t.run.live : t.run.disconnected}
              </span>
            </div>
            <h1 className="mt-2 max-w-4xl text-lg font-semibold leading-snug text-slate-900">{r.objective}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>{t.run.strategy}: <span className="font-medium text-slate-700">{strategy?.name ?? r.strategy_key}</span></span>
              <span className="text-slate-300">|</span>
              {(r.strategy_config.agent_ids ?? []).map((id) => (
                <span key={id} className="inline-flex items-center gap-1 font-medium text-slate-700">
                  <Avatar name={agents.name(id) ?? '?'} index={agents.index(id)} size="sm" /> {agents.name(id)}
                </span>
              ))}
            </div>
          </div>
          {active && (
            <div className="flex gap-2">
              {r.status === 'PAUSED' ? (
                <Button variant="secondary" icon={<Play className="h-4 w-4" />} loading={control.isPending} onClick={() => control.mutate('resume')}>{t.run.resume}</Button>
              ) : (
                <Button variant="secondary" icon={<Pause className="h-4 w-4" />} loading={control.isPending} onClick={() => control.mutate('pause')}>{t.run.pause}</Button>
              )}
              <Button variant="danger" icon={<Square className="h-4 w-4" />} disabled={control.isPending} onClick={() => confirm(t.run.confirmCancel) && control.mutate('cancel')}>{t.run.cancel}</Button>
            </div>
          )}
        </div>
        <div className="grid gap-4 border-t border-slate-100 bg-slate-50/60 px-5 py-3 md:grid-cols-[1fr_280px] md:items-center">
          <ol className="flex flex-wrap items-center gap-2 text-xs">
            {phases.map((label, i) => (
              <li key={label} className="flex items-center gap-2">
                <span className={cx('grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold', i < phase ? 'bg-emerald-500 text-white' : i === phase && active ? 'bg-indigo-600 text-white ring-4 ring-indigo-100' : 'bg-slate-200 text-slate-500')}>{i + 1}</span>
                <span className={cx(i === phase && active ? 'font-semibold text-indigo-700' : i < phase ? 'text-slate-700' : 'text-slate-400')}>{label}</span>
                {i < phases.length - 1 && <span className="mx-1 h-px w-6 bg-slate-300" />}
              </li>
            ))}
          </ol>
          <div>
            <div className="mb-1 flex justify-between text-xs text-slate-500"><span>{t.run.progress}</span><span className="tabular-nums">{done} / {taskList.length}</span></div>
            <Progress value={taskList.length ? (100 * done) / taskList.length : 0} />
          </div>
        </div>
      </Card>
      {control.error && <ErrorBox error={control.error} />}

      <Card>
        <CardHeader title={t.run.taskBoard} icon={<KanbanSquare className="h-4 w-4" />} />
        <TaskBoard tasks={taskList} />
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Card className="min-w-0 overflow-hidden">
          <div className="flex items-center gap-1 border-b border-slate-100 px-3 py-2">
            {([['room', t.run.agentRoom, MessagesSquare], ['files', t.project.files, FileCode2]] as const).map(([key, label, Icon]) => (
              <button key={key} onClick={() => setTab(key)} className={cx('inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition', tab === key ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500 hover:text-slate-800')}>
                <Icon className="h-4 w-4" /> {label}
                {key === 'files' && changedFiles.size > 0 && <span className="rounded-full bg-indigo-600 px-1.5 text-[10px] text-white">{changedFiles.size}</span>}
              </button>
            ))}
          </div>
          {tab === 'room' ? (
            <>
              <AgentRoom timeline={stream.timeline} live={stream.live} tasks={taskList} />
              {active && (
                <form onSubmit={send} className="flex gap-2 border-t border-slate-100 bg-white p-3">
                  <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={t.run.instruction} title={t.run.instructionHint} maxLength={8000} />
                  <Button type="submit" icon={<Send className="h-4 w-4" />} loading={instruction.isPending}>{t.run.send}</Button>
                </form>
              )}
            </>
          ) : (
            <FileExplorer projectId={r.project_id} highlight={changedFiles} />
          )}
        </Card>

        <div className="space-y-5">
          <ResultCard run={r} />
          <MetricsCard metrics={metrics.data} />
          <ReviewsCard reviews={reviews.data ?? []} />
        </div>
      </div>
    </div>
  )
}
