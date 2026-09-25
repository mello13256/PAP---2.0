import type { Review, Run, RunMetrics } from '../../api/types'
import { AgentName, Badge, Card, CardHeader, StatusBadge, formatDuration } from '../../components/ui'
import { useAgentIndex } from '../../hooks/useAgentIndex'
import { useT } from '../../i18n'

export function MetricsCard({ metrics }: { metrics?: RunMetrics }) {
  const t = useT()
  if (!metrics) return null
  const rows: [string, string][] = [
    [t.metrics.time, formatDuration(metrics.execution_time_s)],
    [t.metrics.calls, `${metrics.api_calls}${metrics.failed_calls ? ` (${metrics.failed_calls} ${t.metrics.failedCalls.toLowerCase()})` : ''}`],
    [t.metrics.tokens, `${metrics.input_tokens.toLocaleString()} → ${metrics.output_tokens.toLocaleString()}`],
    [t.metrics.tasks, `${metrics.tasks_completed} / ${metrics.tasks_total}`],
    [t.metrics.reviews, String(metrics.reviews)],
    [t.metrics.revisions, String(metrics.revisions)],
    [t.metrics.cost, metrics.estimated_cost_usd === null ? '—' : `$${metrics.estimated_cost_usd.toFixed(4)}`],
  ]
  return (
    <Card>
      <CardHeader title={t.run.metrics} />
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 p-4 text-sm">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
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
      <CardHeader title={`${t.run.reviews} (${reviews.length})`} />
      <ul className="divide-y divide-slate-100">
        {reviews.map((r) => (
          <li key={r.id} className="space-y-1 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-slate-800 font-mono text-white">{r.task_key}</Badge>
              <span className="text-xs text-slate-400">{t.run.round} {r.round}</span>
              <StatusBadge status={r.verdict} />
            </div>
            <div className="text-xs">
              <AgentName name={agents.name(r.reviewer_agent_id) ?? '?'} index={agents.index(r.reviewer_agent_id)} />
              <span className="text-slate-400"> → </span>
              <AgentName name={agents.name(r.author_agent_id) ?? '?'} index={agents.index(r.author_agent_id)} />
            </div>
            <p className="text-slate-700">{r.summary}</p>
            {r.issues.length > 0 && (
              <ul className="space-y-1">
                {r.issues.map((issue) => (
                  <li key={issue.id} className="text-xs text-slate-600">
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
  return (
    <Card className={run.status === 'COMPLETED' ? 'border-emerald-200' : 'border-rose-200'}>
      <CardHeader title={run.final_result ? t.run.finalResult : t.run.failure} action={<StatusBadge status={run.status} />} />
      {run.failure_reason && <p className="px-4 pt-3 text-sm text-rose-700">{run.failure_reason}</p>}
      {run.final_result && <p className="whitespace-pre-wrap p-4 text-sm leading-relaxed">{run.final_result}</p>}
    </Card>
  )
}
