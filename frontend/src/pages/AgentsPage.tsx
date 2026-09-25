import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useAgents, useCreateAgent, usePingAgent, useProviderModels, useRemoveAgent, useRestoreDefaultAgents, useUpdateAgent } from '../api/hooks'
import type { Agent, PingResult } from '../api/types'
import { Bot, FlaskConical, Pencil, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { Avatar, Badge, Button, Card, ErrorBox, Field, Input, Loading, PageHeader, Select, Textarea, cx } from '../components/ui'
import { useQuery } from '@tanstack/react-query'
import { useT } from '../i18n'

const CAPABILITIES = ['planning', 'architecture', 'coding', 'review', 'testing', 'documentation', 'synthesis']

type Draft = {
  name: string
  provider: string
  model: string
  capabilities: string[]
  system_prompt: string
  temperature: string
  max_output_tokens: string
  enabled: boolean
}

const toDraft = (a?: Agent): Draft => ({
  name: a?.name ?? '',
  provider: a?.provider ?? 'ollama',
  model: a?.model ?? '',
  capabilities: a?.capabilities ?? [],
  system_prompt: a?.system_prompt ?? '',
  temperature: a?.config.temperature?.toString() ?? '',
  max_output_tokens: (a?.config.max_output_tokens ?? 4096).toString(),
  enabled: a?.enabled ?? true,
})

function AgentForm({ agent, onDone }: { agent?: Agent; onDone: () => void }) {
  const t = useT()
  const [draft, setDraft] = useState<Draft>(toDraft(agent))
  const providers = useQuery({ queryKey: ['providers'], queryFn: () => api.get<{ key: string }[]>('/providers') })
  const models = useProviderModels(draft.provider)
  const update = useUpdateAgent()
  const create = useCreateAgent()
  const mutation = agent ? update : create
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const payload = {
      name: draft.name,
      provider: draft.provider,
      model: draft.model,
      capabilities: draft.capabilities,
      system_prompt: draft.system_prompt,
      enabled: draft.enabled,
      config: {
        ...(draft.temperature !== '' ? { temperature: Number(draft.temperature) } : {}),
        max_output_tokens: Number(draft.max_output_tokens),
      },
    }
    if (agent) update.mutate({ id: agent.id, ...payload }, { onSuccess: onDone })
    else create.mutate(payload, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} className="space-y-3 border-t border-slate-100 p-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t.agents.name}>
          <Input value={draft.name} onChange={(e) => set('name', e.target.value)} required maxLength={80} />
        </Field>
        <Field label={t.agents.provider}>
          <Select value={draft.provider} onChange={(e) => set('provider', e.target.value)}>
            {(providers.data ?? [{ key: draft.provider }]).map((p) => <option key={p.key}>{p.key}</option>)}
          </Select>
        </Field>
        <Field label={t.agents.model} hint={models.data?.length ? `${t.agents.installedModels}: ${models.data.join(', ')}` : undefined}>
          <Input value={draft.model} onChange={(e) => set('model', e.target.value)} required list={`models-${agent?.id ?? 'new'}`} />
          <datalist id={`models-${agent?.id ?? 'new'}`}>
            {models.data?.map((m) => <option key={m} value={m} />)}
          </datalist>
        </Field>
      </div>
      <div>
        <div className="mb-1 text-sm font-medium text-slate-700">{t.agents.capabilities}</div>
        <div className="flex flex-wrap gap-2">
          {CAPABILITIES.map((cap) => {
            const on = draft.capabilities.includes(cap)
            return (
              <button
                type="button"
                key={cap}
                onClick={() => set('capabilities', on ? draft.capabilities.filter((c) => c !== cap) : [...draft.capabilities, cap])}
                className={cx('rounded-full px-2.5 py-1 text-xs font-medium ring-1', on ? 'bg-indigo-600 text-white ring-indigo-600' : 'text-slate-600 ring-slate-300')}
              >
                {cap}
              </button>
            )
          })}
        </div>
      </div>
      <Field label={t.agents.systemPrompt}>
        <Textarea value={draft.system_prompt} onChange={(e) => set('system_prompt', e.target.value)} rows={4} maxLength={8000} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t.agents.temperature}>
          <Input type="number" step="0.1" min="0" max="2" value={draft.temperature} onChange={(e) => set('temperature', e.target.value)} />
        </Field>
        <Field label={t.agents.maxTokens}>
          <Input type="number" min="256" max="65536" value={draft.max_output_tokens} onChange={(e) => set('max_output_tokens', e.target.value)} />
        </Field>
        <label className="flex items-center gap-2 pt-6 text-sm">
          <input type="checkbox" checked={draft.enabled} onChange={(e) => set('enabled', e.target.checked)} className="h-4 w-4 accent-indigo-600" />
          {t.agents.enabled}
        </label>
      </div>
      {mutation.error && <ErrorBox error={mutation.error} />}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>{t.common.cancel}</Button>
        <Button type="submit" loading={mutation.isPending}>{agent ? t.common.save : t.common.create}</Button>
      </div>
    </form>
  )
}

function PingBox({ result }: { result: PingResult }) {
  return (
    <div className={cx('border-t px-4 py-3 text-sm', result.ok ? 'border-emerald-100 bg-emerald-50/50' : 'border-rose-100 bg-rose-50')}>
      {result.ok ? (
        <>
          <p className="whitespace-pre-wrap">{result.text}</p>
          <p className="mt-1 text-xs text-slate-500">
            {result.model} · {(result.latency_ms / 1000).toFixed(1)} s · {result.input_tokens} → {result.output_tokens} tokens
          </p>
        </>
      ) : (
        <p className="text-rose-700">{result.error_kind}: {result.error}</p>
      )}
    </div>
  )
}

function AgentCard({ agent, index }: { agent: Agent; index: number }) {
  const t = useT()
  const [editing, setEditing] = useState(false)
  const ping = usePingAgent()
  const remove = useRemoveAgent()
  return (
    <Card className={cx(!agent.enabled && 'opacity-70')}>
      <div className="flex flex-wrap items-start gap-4 p-5">
        <Avatar name={agent.name} index={index} size="lg" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold text-slate-900">{agent.name}</span>
            <Badge>{agent.provider}</Badge>
            <span className="font-mono text-xs text-slate-500">{agent.model}</span>
            {!agent.enabled && <Badge className="bg-slate-200 text-slate-600">{t.agents.disabled}</Badge>}
            {!agent.provider_available && <Badge className="bg-rose-100 text-rose-700">{t.agents.unavailable}</Badge>}
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {agent.capabilities.map((c) => <Badge key={c} className="bg-indigo-50 text-indigo-700">{c}</Badge>)}
          </div>
          <p className="mt-2 line-clamp-2 text-xs text-slate-500">{agent.system_prompt}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" icon={<FlaskConical className="h-4 w-4" />} loading={ping.isPending} onClick={() => ping.mutate(agent.id)}>
            {ping.isPending ? t.agents.testing : t.agents.test}
          </Button>
          <Button variant="secondary" icon={<Pencil className="h-4 w-4" />} onClick={() => setEditing((e) => !e)}>{t.agents.edit}</Button>
          <Button
            variant="danger"
            icon={<Trash2 className="h-4 w-4" />}
            loading={remove.isPending}
            onClick={() => confirm(t.agents.confirmRemove) && remove.mutate(agent.id)}
          >
            {t.agents.remove}
          </Button>
        </div>
      </div>
      {remove.data && !remove.data.deleted && (
        <p className="border-t border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-800">{t.agents.keptDisabled}</p>
      )}
      {remove.error && <div className="px-4 pb-3"><ErrorBox error={remove.error} /></div>}
      {ping.data && <PingBox result={ping.data} />}
      {editing && <AgentForm agent={agent} onDone={() => setEditing(false)} />}
    </Card>
  )
}

export function AgentsPage() {
  const t = useT()
  const { data: agents, isLoading, error } = useAgents()
  const restore = useRestoreDefaultAgents()
  const [creating, setCreating] = useState(false)
  if (isLoading) return <Loading />
  if (error) return <ErrorBox error={error} />
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHeader
        title={<span className="inline-flex items-center gap-2"><Bot className="h-6 w-6 text-indigo-500" />{t.agents.title}</span>}
        subtitle={t.agents.subtitle}
        action={
          <>
            <Button variant="ghost" icon={<RotateCcw className="h-4 w-4" />} loading={restore.isPending} onClick={() => restore.mutate()}>{t.agents.restoreDefaults}</Button>
            <Button icon={<Plus className="h-4 w-4" />} onClick={() => setCreating(true)}>{t.agents.new}</Button>
          </>
        }
      />
      {creating && (
        <Card>
          <div className="px-4 pt-4 text-sm font-semibold">{t.agents.new}</div>
          <AgentForm onDone={() => setCreating(false)} />
        </Card>
      )}
      {agents!.map((agent, index) => <AgentCard key={agent.id} agent={agent} index={index} />)}
    </div>
  )
}
