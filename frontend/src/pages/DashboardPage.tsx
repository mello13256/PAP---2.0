import { ArrowRight, Bot, CheckCircle2, CircleDashed, Cpu, FolderGit2, History, Play, Plus, Server, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useAgents, useCreateProject, useMe, useModelStatus, useProjects, useRecentRuns } from '../api/hooks'
import { Avatar, Button, Card, CardHeader, Empty, ErrorBox, Field, Input, Loading, StatusBadge, Textarea, cx, formatDate } from '../components/ui'
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
    <form onSubmit={submit} className="space-y-3 p-5">
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

function SetupCheck({ ok, label, to }: { ok: boolean; label: string; to: string }) {
  const t = useT()
  return (
    <li className="flex items-center gap-2.5 text-sm">
      {ok ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <CircleDashed className="h-4 w-4 text-amber-500" />}
      <span className={ok ? 'text-slate-700' : 'text-slate-900'}>{label}</span>
      {!ok && <Link to={to} className="ml-auto text-xs font-medium text-indigo-600 hover:underline">{t.home.setupFix} →</Link>}
    </li>
  )
}

export function DashboardPage() {
  const t = useT()
  const { data: me } = useMe()
  const projects = useProjects()
  const runs = useRecentRuns()
  const models = useModelStatus()
  const { data: agents = [] } = useAgents()
  const [creating, setCreating] = useState(false)
  const active = agents.filter((a) => a.enabled && a.provider !== 'fake')
  const installed = new Set(models.data?.installed.map((m) => m.name) ?? [])
  const agentsReady = active.filter((a) => a.provider !== 'ollama' || installed.has(a.model))
  const completed = runs.data?.filter((r) => r.status === 'COMPLETED').length ?? 0
  const firstProject = projects.data?.[0]

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="relative overflow-hidden rounded-3xl bg-slate-950 bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-7 text-white shadow-xl shadow-indigo-500/20">
          <div className="absolute -right-10 -top-10 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
          <div className="relative">
            <p className="text-sm font-medium text-indigo-100">{t.home.greeting}, {me?.display_name} 👋</p>
            <h1 className="mt-2 max-w-2xl text-3xl font-semibold leading-tight tracking-tight">{t.home.heroTitle}</h1>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-indigo-100">{t.home.heroText}</p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              {firstProject ? (
                <Link to={`/projects/${firstProject.id}`} className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-indigo-700 shadow-sm hover:bg-indigo-50">
                  <Play className="h-4 w-4" /> {t.home.heroCta}
                </Link>
              ) : (
                <button onClick={() => setCreating(true)} className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-indigo-700 shadow-sm hover:bg-indigo-50">
                  <Plus className="h-4 w-4" /> {t.dashboard.newProject}
                </button>
              )}
              <div className="flex -space-x-2">
                {active.map((a) => <span key={a.id} className="rounded-full ring-2 ring-violet-600"><Avatar name={a.name} index={agents.indexOf(a)} /></span>)}
              </div>
              <span className="text-sm text-indigo-100">{active.length} {t.dashboard.activeAgents}</span>
            </div>
          </div>
        </div>

        <Card>
          <CardHeader title={t.home.setup} icon={<Sparkles className="h-4 w-4" />} />
          <ul className="space-y-3 p-5">
            <SetupCheck ok={!!models.data?.ollama.running} label={t.home.setupOllama} to="/models" />
            <SetupCheck ok={installed.size > 0} label={`${t.home.setupModels} (${installed.size})`} to="/models" />
            <SetupCheck ok={agentsReady.length >= 2} label={`${t.home.setupAgents} (${agentsReady.length})`} to="/agents" />
          </ul>
          <div className="grid grid-cols-3 border-t border-slate-100 text-center">
            {[
              [t.home.statProjects, projects.data?.length ?? '—', FolderGit2],
              [t.home.statRuns, runs.data?.length ?? '—', History],
              [t.home.statCompleted, completed, CheckCircle2],
            ].map(([label, value, Icon]) => {
              const I = Icon as typeof Server
              return (
                <div key={label as string} className="px-2 py-3">
                  <I className="mx-auto h-4 w-4 text-slate-400" />
                  <div className="mt-1 text-lg font-semibold tabular-nums">{value as string}</div>
                  <div className="text-[11px] text-slate-500">{label as string}</div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <Card>
          <CardHeader
            title={t.dashboard.projects}
            icon={<FolderGit2 className="h-4 w-4" />}
            action={<Button size="sm" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setCreating(true)}>{t.dashboard.newProject}</Button>}
          />
          {creating && <div className="border-b border-slate-100 bg-slate-50/60"><NewProject onDone={() => setCreating(false)} /></div>}
          {projects.isLoading ? <Loading /> : projects.error ? <div className="p-4"><ErrorBox error={projects.error} /></div> : projects.data!.length === 0 ? (
            <Empty icon={<FolderGit2 className="h-5 w-5" />}>{t.dashboard.noProjects}</Empty>
          ) : (
            <ul className="grid gap-3 p-4 sm:grid-cols-2">
              {projects.data!.map((p) => (
                <li key={p.id}>
                  <Link to={`/projects/${p.id}`} className="group flex h-full items-start gap-3 rounded-xl border border-slate-200 p-4 transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md hover:shadow-indigo-100">
                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-indigo-50 to-violet-100 text-indigo-600"><FolderGit2 className="h-5 w-5" /></div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-slate-900">{p.name}</div>
                      {p.description && <div className="mt-0.5 line-clamp-2 text-sm text-slate-500">{p.description}</div>}
                      <div className="mt-1.5 text-xs text-slate-400">{formatDate(p.updated_at)}</div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-indigo-500" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title={t.dashboard.recentRuns} icon={<History className="h-4 w-4" />} />
          {runs.isLoading ? <Loading /> : runs.data?.length === 0 ? <Empty icon={<Bot className="h-5 w-5" />}>{t.dashboard.noRuns}</Empty> : (
            <ul className="divide-y divide-slate-100">
              {runs.data?.map((r) => (
                <li key={r.id}>
                  <Link to={`/runs/${r.id}`} className="block px-5 py-3 transition hover:bg-slate-50">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium text-slate-500">{r.project_name}</span>
                      <StatusBadge status={r.status} />
                    </div>
                    <div className="mt-1 line-clamp-2 text-sm text-slate-800">{r.objective}</div>
                    <div className="mt-1 flex items-center gap-1 text-xs text-slate-400"><Cpu className="h-3 w-3" /> {r.strategy_config.name ?? r.strategy_key} · {formatDate(r.created_at)}</div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <p className={cx('text-center text-xs text-slate-400')}>MultiMind · PAP</p>
    </div>
  )
}
