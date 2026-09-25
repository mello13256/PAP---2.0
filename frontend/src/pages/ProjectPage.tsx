import { ChevronLeft, Download, FileCode2, History, Play, Rocket } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useProject, useRuns } from '../api/hooks'
import { Card, CardHeader, Empty, ErrorBox, Loading, PageHeader, StatusBadge, cx, formatDate } from '../components/ui'
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

  const tabs = [
    { key: 'runs' as const, label: t.project.runs, icon: Play },
    { key: 'files' as const, label: t.project.files, icon: FileCode2 },
  ]

  return (
    <div>
      <PageHeader
        back={<Link to="/" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ChevronLeft className="h-4 w-4" />{t.common.back}</Link>}
        title={project.data!.name}
        subtitle={project.data!.description}
        action={
          <>
            <div className="inline-flex rounded-xl bg-white p-1 text-sm font-medium shadow-sm ring-1 ring-slate-200">
              {tabs.map(({ key, label, icon: Icon }) => (
                <button key={key} onClick={() => setTab(key)} className={cx('inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition', tab === key ? 'bg-indigo-600 text-white shadow' : 'text-slate-500 hover:text-slate-800')}>
                  <Icon className="h-4 w-4" /> {label}
                </button>
              ))}
            </div>
            <a href={`/api/projects/${projectId}/files/export`} className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-slate-200 hover:bg-slate-50">
              <Download className="h-4 w-4" /> {t.project.export}
            </a>
          </>
        }
      />

      {tab === 'runs' ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,520px)_1fr]">
          <Card>
            <CardHeader title={t.project.newRun} icon={<Rocket className="h-4 w-4" />} />
            <NewRunForm projectId={projectId} />
          </Card>
          <Card className="self-start">
            <CardHeader title={t.project.runs} icon={<History className="h-4 w-4" />} />
            {runs.isLoading ? <Loading /> : runs.data?.length === 0 ? <Empty icon={<Play className="h-5 w-5" />}>{t.project.noRuns}</Empty> : (
              <ul className="divide-y divide-slate-100">
                {runs.data?.map((r) => (
                  <li key={r.id}>
                    <Link to={`/runs/${r.id}`} className="flex items-start gap-3 px-5 py-3.5 transition hover:bg-slate-50">
                      <div className="min-w-0 flex-1">
                        <div className="line-clamp-2 text-sm text-slate-800">{r.objective}</div>
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
        <Card className="overflow-hidden">
          <FileExplorer projectId={projectId} />
        </Card>
      )}
    </div>
  )
}
