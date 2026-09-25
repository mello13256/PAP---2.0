import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { useMetrics, useReviews, useRun, useRunControl, useSendInstruction, useStrategies, useTasks } from '../api/hooks'
import { AgentName, Button, Card, CardHeader, ErrorBox, Input, Loading, StatusBadge, cx } from '../components/ui'
import { AgentRoom } from '../features/run/AgentRoom'
import { MetricsCard, ResultCard, ReviewsCard } from '../features/run/RunSidebar'
import { TaskBoard } from '../features/run/TaskBoard'
import { FileExplorer } from '../features/files/FileExplorer'
import { useAgentIndex } from '../hooks/useAgentIndex'
import { useRunStream } from '../hooks/useRunStream'
import { useT } from '../i18n'

const ACTIVE = new Set(['PLANNING', 'RUNNING', 'FINALIZING', 'PAUSED'])

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
  const active = ACTIVE.has(r.status)
  const strategy = strategies.find((s) => s.key === r.strategy_key)

  const send = (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    instruction.mutate(text, { onSuccess: () => setText('') })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <Link to={`/projects/${r.project_id}`} className="text-sm text-slate-500 hover:text-slate-800">← {t.common.back}</Link>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight">{t.run.objective}</h1>
            <StatusBadge status={r.status} />
            <span className={cx('text-xs', stream.connected ? 'text-emerald-600' : 'text-slate-400')}>
              ● {stream.connected ? t.run.live : t.run.disconnected}
            </span>
          </div>
          <p className="mt-1 max-w-4xl text-sm text-slate-700">{r.objective}</p>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {t.run.strategy}: <span className="font-medium text-slate-700">{strategy?.name ?? r.strategy_key}</span> ·
            {(r.strategy_config.agent_ids ?? []).map((id) => (
              <AgentName key={id} name={agents.name(id) ?? '?'} index={agents.index(id)} />
            ))}
          </p>
        </div>
        {active && (
          <div className="flex gap-2">
            {r.status === 'PAUSED' ? (
              <Button variant="secondary" loading={control.isPending} onClick={() => control.mutate('resume')}>▶ {t.run.resume}</Button>
            ) : (
              <Button variant="secondary" loading={control.isPending} onClick={() => control.mutate('pause')}>⏸ {t.run.pause}</Button>
            )}
            <Button variant="danger" disabled={control.isPending} onClick={() => confirm(t.run.confirmCancel) && control.mutate('cancel')}>■ {t.run.cancel}</Button>
          </div>
        )}
      </div>
      {control.error && <ErrorBox error={control.error} />}

      <Card>
        <CardHeader title={t.run.taskBoard} />
        <TaskBoard tasks={tasks.data ?? []} />
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card className="min-w-0">
          <div className="flex items-center gap-1 border-b border-slate-100 px-2 py-1.5">
            {(['room', 'files'] as const).map((key) => (
              <button key={key} onClick={() => setTab(key)} className={cx('rounded-md px-3 py-1.5 text-sm font-medium', tab === key ? 'bg-slate-100' : 'text-slate-500')}>
                {key === 'room' ? t.run.agentRoom : t.project.files}
              </button>
            ))}
          </div>
          {tab === 'room' ? (
            <>
              <AgentRoom timeline={stream.timeline} live={stream.live} tasks={tasks.data ?? []} />
              {active && (
                <form onSubmit={send} className="flex gap-2 border-t border-slate-100 p-3">
                  <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={t.run.instruction} title={t.run.instructionHint} maxLength={8000} />
                  <Button type="submit" loading={instruction.isPending}>{t.run.send}</Button>
                </form>
              )}
            </>
          ) : (
            <FileExplorer projectId={r.project_id} highlight={changedFiles} />
          )}
        </Card>

        <div className="space-y-4">
          <ResultCard run={r} />
          <MetricsCard metrics={metrics.data} />
          <ReviewsCard reviews={reviews.data ?? []} />
        </div>
      </div>
    </div>
  )
}
