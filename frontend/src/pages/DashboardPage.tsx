import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useAgents, useCreateProject, useProjects, useRecentRuns } from '../api/hooks'
import { AgentName, Button, Card, CardHeader, Empty, ErrorBox, Field, Input, Loading, StatusBadge, Textarea, formatDate } from '../components/ui'
import { useT } from '../i18n'

function NewProject({ onDone }: { onDone: () => void }) {
  const t = useT()
  const navigate = useNavigate()
  const create = useCreateProject()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate({ name, description }, { onSuccess: (p) => { onDone(); navigate(`/projects/${p.id}`) } })
  }
  return (
    <form onSubmit={submit} className="space-y-3 p-4">
      <Field label={t.dashboard.projectName}>
        <Input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus />
      </Field>
      <Field label={t.dashboard.projectDescription}>
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} maxLength={2000} />
      </Field>
      {create.error && <ErrorBox error={create.error} />}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>{t.common.cancel}</Button>
        <Button type="submit" loading={create.isPending}>{t.common.create}</Button>
      </div>
    </form>
  )
}

export function DashboardPage() {
  const t = useT()
  const projects = useProjects()
  const runs = useRecentRuns()
  const { data: agents = [] } = useAgents()
  const [creating, setCreating] = useState(false)
  const active = agents.filter((a) => a.enabled && a.provider !== 'fake')

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t.dashboard.title}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-500">
            {active.length} {t.dashboard.activeAgents}:
            {active.map((a) => <AgentName key={a.id} name={a.name} index={agents.indexOf(a)} />)}
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>+ {t.dashboard.newProject}</Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {creating && (
            <Card>
              <CardHeader title={t.dashboard.newProject} />
              <NewProject onDone={() => setCreating(false)} />
            </Card>
          )}
          <Card>
            <CardHeader title={t.dashboard.projects} />
            {projects.isLoading ? <Loading /> : projects.error ? <div className="p-4"><ErrorBox error={projects.error} /></div> : (
              projects.data!.length === 0 ? <Empty>{t.dashboard.noProjects}</Empty> : (
                <ul className="grid gap-3 p-4 sm:grid-cols-2">
                  {projects.data!.map((p) => (
                    <li key={p.id}>
                      <Link to={`/projects/${p.id}`} className="block rounded-lg border border-slate-200 p-4 transition hover:border-indigo-300 hover:shadow-sm">
                        <div className="font-medium">{p.name}</div>
                        {p.description && <div className="mt-1 line-clamp-2 text-sm text-slate-500">{p.description}</div>}
                        <div className="mt-2 text-xs text-slate-400">{formatDate(p.updated_at)}</div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )
            )}
          </Card>
        </div>

        <Card>
          <CardHeader title={t.dashboard.recentRuns} />
          {runs.isLoading ? <Loading /> : runs.data?.length === 0 ? <Empty>{t.dashboard.noRuns}</Empty> : (
            <ul className="divide-y divide-slate-100">
              {runs.data?.map((r) => (
                <li key={r.id}>
                  <Link to={`/runs/${r.id}`} className="block px-4 py-3 hover:bg-slate-50">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium text-slate-500">{r.project_name}</span>
                      <StatusBadge status={r.status} />
                    </div>
                    <div className="mt-1 line-clamp-2 text-sm">{r.objective}</div>
                    <div className="mt-1 text-xs text-slate-400">{formatDate(r.created_at)}</div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
