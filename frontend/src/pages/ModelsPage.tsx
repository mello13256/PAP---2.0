import { CheckCircle2, Cpu, Download, ExternalLink, HardDrive, RefreshCw, Server, Sparkles, Trash2, UserPlus, WifiOff } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useCreateAgent, useDeleteModel, useModelCatalog, useModelPulls, useModelStatus, usePullModel } from '../api/hooks'
import type { CatalogModel, PullState } from '../api/types'
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Input, Loading, PageHeader, Progress, cx, formatBytes } from '../components/ui'
import { useI18n } from '../i18n'

function PullProgress({ pull }: { pull: PullState }) {
  if (pull.error) return <p className="text-xs text-rose-600">{pull.error}</p>
  return (
    <div className="space-y-1">
      <Progress value={pull.done ? 100 : pull.percent} />
      <div className="flex justify-between text-[11px] text-slate-500">
        <span className="truncate">{pull.status}</span>
        <span className="tabular-nums">
          {pull.total ? `${formatBytes(pull.completed)} / ${formatBytes(pull.total)} · ${pull.percent}%` : ''}
        </span>
      </div>
    </div>
  )
}

function CatalogCard({ model, installed, pull, running }: { model: CatalogModel; installed: boolean; pull?: PullState; running: boolean }) {
  const { t, language } = useI18n()
  const start = usePullModel()
  const createAgent = useCreateAgent()
  const downloading = pull && !pull.done
  return (
    <div className={cx('flex flex-col gap-3 rounded-2xl border bg-white p-4 transition', model.recommended ? 'border-indigo-200 shadow-sm shadow-indigo-100' : 'border-slate-200')}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-mono text-sm font-semibold text-slate-900">{model.name}</div>
          <div className="text-xs text-slate-500">{model.family} · ~{model.size_gb} GB</div>
        </div>
        {model.recommended && <Badge className="bg-indigo-50 text-indigo-700"><Sparkles className="h-3 w-3" /> {t.modelsPage.recommendedBadge}</Badge>}
      </div>
      <p className="flex-1 text-sm text-slate-600">{language === 'pt' ? model.description_pt : model.description_en}</p>
      {pull && (downloading || pull.error) && <PullProgress pull={pull} />}
      <div className="flex items-center gap-2">
        {installed ? (
          <>
            <Badge className="bg-emerald-50 text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" /> {t.modelsPage.installedBadge}</Badge>
            <Button
              size="sm"
              variant="secondary"
              className="ml-auto"
              icon={<UserPlus className="h-3.5 w-3.5" />}
              loading={createAgent.isPending}
              disabled={createAgent.isSuccess}
              onClick={() =>
                createAgent.mutate({
                  name: model.name.split(':')[0].replace(/[^a-zA-Z0-9]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()).trim(),
                  provider: 'ollama',
                  model: model.name,
                  capabilities: ['coding', 'review', 'architecture'],
                  system_prompt:
                    'És um agente do MultiMind. Trabalhas em equipa com outros agentes através de um orquestrador. Responde em português de Portugal, de forma clara e objetiva.',
                  config: { temperature: 0.3, max_output_tokens: 4096 },
                  enabled: true,
                })
              }
            >
              {createAgent.isSuccess ? t.modelsPage.agentCreated : t.modelsPage.useInAgent}
            </Button>
          </>
        ) : (
          <Button
            size="sm"
            className="w-full"
            icon={<Download className="h-3.5 w-3.5" />}
            loading={start.isPending || downloading}
            disabled={!running}
            onClick={() => start.mutate(model.name)}
          >
            {downloading ? `${t.modelsPage.downloading}… ${pull!.percent}%` : t.modelsPage.download}
          </Button>
        )}
      </div>
    </div>
  )
}

export function ModelsPage() {
  const { t } = useI18n()
  const status = useModelStatus()
  const catalog = useModelCatalog()
  const pulls = useModelPulls()
  const start = usePullModel()
  const remove = useDeleteModel()
  const [custom, setCustom] = useState('')

  const running = !!status.data?.ollama.running
  const installed = new Set(status.data?.installed.map((m) => m.name) ?? [])
  const pullOf = (name: string) => pulls.data?.find((p) => p.name === name)
  const customPulls = (pulls.data ?? []).filter((p) => !catalog.data?.some((m) => m.name === p.name))

  const submitCustom = (e: FormEvent) => {
    e.preventDefault()
    if (custom.trim()) start.mutate(custom.trim(), { onSuccess: () => setCustom('') })
  }

  return (
    <div>
      <PageHeader
        title={t.modelsPage.title}
        subtitle={t.modelsPage.subtitle}
        action={<Button variant="secondary" icon={<RefreshCw className="h-4 w-4" />} onClick={() => status.refetch()}>{t.modelsPage.refresh}</Button>}
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <Card className={cx('overflow-hidden', !running && status.data && 'border-amber-200')}>
            <div className="flex flex-wrap items-center gap-4 p-5">
              <div className={cx('grid h-12 w-12 place-items-center rounded-2xl', running ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600')}>
                {running ? <Server className="h-6 w-6" /> : <WifiOff className="h-6 w-6" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 font-semibold">
                  {t.modelsPage.ollama}
                  {status.isLoading ? null : running ? (
                    <Badge className="bg-emerald-50 text-emerald-700">{t.modelsPage.running} · v{status.data?.ollama.version}</Badge>
                  ) : (
                    <Badge className="bg-amber-50 text-amber-800">{t.modelsPage.notRunning}</Badge>
                  )}
                </div>
                <p className="mt-0.5 text-sm text-slate-500">{running ? status.data?.ollama.url : t.modelsPage.notRunningHelp}</p>
              </div>
              {!running && !status.isLoading && (
                <a href="https://ollama.com/download/windows" target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-800">
                  <ExternalLink className="h-4 w-4" /> {t.modelsPage.downloadOllama}
                </a>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title={t.modelsPage.catalog} icon={<Sparkles className="h-4 w-4" />} subtitle={t.modelsPage.needsInternet} />
            {catalog.isLoading ? <Loading /> : (
              <div className="grid gap-3 p-4 sm:grid-cols-2 2xl:grid-cols-3">
                {catalog.data?.map((m) => (
                  <CatalogCard key={m.name} model={m} installed={installed.has(m.name)} pull={pullOf(m.name)} running={running} />
                ))}
              </div>
            )}
            <form onSubmit={submitCustom} className="flex flex-wrap items-end gap-2 border-t border-slate-100 p-4">
              <label className="min-w-60 flex-1">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">{t.modelsPage.custom}</span>
                <Input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder={t.modelsPage.customPlaceholder} className="font-mono" />
              </label>
              <Button type="submit" icon={<Download className="h-4 w-4" />} disabled={!running || !custom.trim()} loading={start.isPending}>
                {t.modelsPage.download}
              </Button>
            </form>
            {customPulls.length > 0 && (
              <div className="space-y-3 border-t border-slate-100 p-4">
                {customPulls.map((p) => (
                  <div key={p.name}>
                    <div className="mb-1 font-mono text-xs font-semibold">{p.name}</div>
                    <PullProgress pull={p} />
                  </div>
                ))}
              </div>
            )}
            {start.error && <div className="px-4 pb-4"><ErrorBox error={start.error} /></div>}
          </Card>
        </div>

        <Card className="self-start">
          <CardHeader title={t.modelsPage.installed} icon={<HardDrive className="h-4 w-4" />} />
          {status.isLoading ? <Loading /> : status.error ? <div className="p-4"><ErrorBox error={status.error} /></div> : !status.data?.installed.length ? (
            <Empty icon={<Cpu className="h-5 w-5" />}>{t.modelsPage.noneInstalled}</Empty>
          ) : (
            <ul className="divide-y divide-slate-100">
              {status.data.installed.map((m) => (
                <li key={m.name} className="flex items-center gap-3 px-5 py-3">
                  <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-slate-500"><Cpu className="h-4 w-4" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-mono text-sm font-medium">{m.name}</div>
                    <div className="text-xs text-slate-500">
                      {formatBytes(m.size_bytes)}
                      {m.parameter_size && ` · ${m.parameter_size}`}
                      {m.quantization && ` · ${m.quantization}`}
                    </div>
                  </div>
                  <button
                    title={t.modelsPage.remove}
                    className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                    onClick={() => confirm(t.modelsPage.confirmRemove) && remove.mutate(m.name)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {remove.error && <div className="p-4"><ErrorBox error={remove.error} /></div>}
        </Card>
      </div>
    </div>
  )
}
