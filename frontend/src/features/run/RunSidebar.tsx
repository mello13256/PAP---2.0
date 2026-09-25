import { Activity, Clock, Coins, Flag, GitPullRequestArrow, ListChecks, MessagesSquare, ShieldCheck, XCircle, Zap } from 'lucide-react'
import type { Review, Run, RunMetrics } from '../../api/types'
import { Avatar, Badge, Card, CardHeader, Stat, StatusBadge, cx, formatDuration } from '../../components/ui'
import { useAgentIndex } from '../../hooks/useAgentIndex'
import { useT } from '../../i18n'

export function MetricsCard({ metrics }: { metrics?: RunMetrics }) {
  const t = useT()
  if (!metrics) return null
  return (
    <Card>
      <CardHeader title={t.run.metrics} icon={<Activity className="h-4 w-4" />} />
      <div className="grid grid-cols-2 gap-4 p-5">
        <Stat icon={<Clock className="h-4 w-4" />} label={t.metrics.time} value={formatDuration(metrics.execution_time_s)} />
        <Stat icon={<Zap className="h-4 w-4" />} label={t.metrics.calls} value={`${metrics.api_calls}${metrics.failed_calls ? ` (${metrics.failed_calls}✗)` : ''}`} />
        <Stat icon={<MessagesSquare className="h-4 w-4" />} label={t.metrics.tokens} value={`${metrics.input_tokens.toLocaleString()} → ${metrics.output_tokens.toLocaleString()}`} />
        <Stat icon={<ListChecks className="h-4 w-4" />} label={t.metrics.tasks} value={`${metrics.tasks_completed} / ${metrics.tasks_total}`} />
        <Stat icon={<ShieldCheck className="h-4 w-4" />} label={t.metrics.reviews} value={metrics.reviews} />
        <Stat icon={<GitPullRequestArrow className="h-4 w-4" />} label={t.metrics.revisions} value={metrics.revisions} />
        <Stat icon={<Coins className="h-4 w-4" />} label={t.metrics.cost} value={metrics.estimated_cost_usd === null ? '—' : `$${metrics.estimated_cost_usd.toFixed(4)}`} />
      </div>
    </Card>
  )
}

const severityColor: Record<string, string> = {
  CRITICAL: 'bg-rose-100 text-rose-700',
  MAJOR: 'bg-orange-100 text-orange-700',
  MINOR: 'bg-sky-100 text-sky-700',
  INFO: 'bg-slate-100 text-slate-600',
}

export function ReviewsCard({ reviews }: { reviews: Review[] }) {
  const t = useT()
  const agents = useAgentIndex()
  if (!reviews.length) return null
  return (
    <Card>
      <CardHeader title={`${t.run.reviews} (${reviews.length})`} icon={<ShieldCheck className="h-4 w-4" />} />
      <ul className="divide-y divide-slate-100">
        {reviews.map((r) => (
          <li key={r.id} className="space-y-1.5 px-5 py-3.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-slate-800 font-mono text-white">{r.task_key}</Badge>
              <span className="text-xs text-slate-400">{t.run.round} {r.round}</span>
              <span className="ml-auto"><StatusBadge status={r.verdict} /></span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Avatar name={agents.name(r.reviewer_agent_id) ?? '?'} index={agents.index(r.reviewer_agent_id)} size="sm" />
              {agents.name(r.reviewer_agent_id)} → {agents.name(r.author_agent_id)}
            </div>
            <p className="text-slate-700">{r.summary}</p>
            {r.issues.length > 0 && (
              <ul className="space-y-1">
                {r.issues.map((issue) => (
                  <li key={issue.id} className="text-xs leading-relaxed text-slate-600">
                    <Badge className={severityColor[issue.severity]}>{issue.severity}</Badge>{' '}
                    {issue.file_path && <span className="font-mono">{issue.file_path}: </span>}
                    {issue.description}
                    {issue.suggestion && <span className="text-slate-400"> → {issue.suggestion}</span>}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function ResultCard({ run }: { run: Run }) {
  const t = useT()
  if (!run.final_result && !run.failure_reason) return null
  const ok = run.status === 'COMPLETED'
  return (
    <Card className={cx('overflow-hidden', ok ? 'border-emerald-200' : 'border-rose-200')}>
      <div className={cx('flex items-center gap-2 px-5 py-3.5', ok ? 'bg-gradient-to-r from-emerald-50 to-teal-50' : 'bg-rose-50')}>
        {ok ? <Flag className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-rose-600" />}
        <h2 className="text-sm font-semibold">{run.final_result ? t.run.finalResult : t.run.failure}</h2>
        <span className="ml-auto"><StatusBadge status={run.status} /></span>
      </div>
      {run.failure_reason && <p className="px-5 pt-3 text-sm text-rose-700">{run.failure_reason}</p>}
      {run.final_result && <p className="whitespace-pre-wrap p-5 text-sm leading-relaxed text-slate-700">{run.final_result}</p>}
    </Card>
  )
}
