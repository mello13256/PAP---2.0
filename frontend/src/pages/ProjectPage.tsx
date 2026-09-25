import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useProject, useRuns } from '../api/hooks'
import { Card, CardHeader, Empty, ErrorBox, Loading, StatusBadge, cx, formatDate } from '../components/ui'
import { FileExplorer } from '../features/files/FileExplorer'
import { NewRunForm } from '../features/runs/NewRunForm'
import { useT } from '../i18n'

export function ProjectPage() {
  const t = useT()
  const { projectId = '' } = useParams()
  const project = useProject(projectId)
  const runs = useRuns(projectId)
  const [tab, setTab] = useState<'runs' | 'files'>('runs')

  if (project.isLoading) return <Loading />
  if (project.error) return <ErrorBox error={project.error} />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-slate-500 hover:text-slate-800">← {t.common.back}</Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{project.data!.name}</h1>
          {project.data!.description && <p className="mt-1 text-sm text-slate-500">{project.data!.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-sm font-medium">
            {(['runs', 'files'] as const).map((key) => (
              <button key={key} onClick={() => setTab(key)} className={cx('rounded-md px-3 py-1.5', tab === key ? 'bg-white shadow-sm' : 'text-slate-500')}>
                {key === 'runs' ? t.project.runs : t.project.files}
              </button>
            ))}
          </div>
          <a href={`/api/projects/${projectId}/files/export`} className="rounded-lg px-3 py-1.5 text-sm text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50">
            ⬇ {t.project.export}
          </a>
        </div>
      </div>

      {tab === 'runs' ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,480px)_1fr]">
          <Card>
            <CardHeader title={t.project.newRun} />
            <NewRunForm projectId={projectId} />
          </Card>
          <Card>
            <CardHeader title={t.project.runs} />
            {runs.isLoading ? <Loading /> : runs.data?.length === 0 ? <Empty>{t.project.noRuns}</Empty> : (
              <ul className="divide-y divide-slate-100">
                {runs.data?.map((r) => (
                  <li key={r.id}>
                    <Link to={`/runs/${r.id}`} className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50">
                      <div className="min-w-0 flex-1">
                        <div className="line-clamp-2 text-sm">{r.objective}</div>
                        <div className="mt-1 text-xs text-slate-400">{r.strategy_config.name ?? r.strategy_key} · {formatDate(r.created_at)}</div>
                      </div>
                      <StatusBadge status={r.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      ) : (
        <Card>
          <FileExplorer projectId={projectId} />
        </Card>
      )}
    </div>
  )
}
