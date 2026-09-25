import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useAgents, useCreateRun, useStrategies } from '../../api/hooks'
import { AgentName, Button, ErrorBox, Field, Select, Textarea, cx } from '../../components/ui'
import { useT } from '../../i18n'

export function NewRunForm({ projectId }: { projectId: string }) {
  const t = useT()
  const navigate = useNavigate()
  const { data: agents = [] } = useAgents()
  const { data: strategies = [] } = useStrategies()
  const create = useCreateRun(projectId)
  const [objective, setObjective] = useState('')
  const [strategy, setStrategy] = useState('collaborative')
  const usable = agents.filter((a) => a.enabled)
  // Por defeito: todos os agentes reais ativos, pela ordem da lista.
  const [picked, setSelected] = useState<string[] | null>(null)
  const selected = picked ?? usable.filter((a) => a.provider !== 'fake').map((a) => a.id)

  const toggle = (id: string) =>
    setSelected((s) => {
      const current = s ?? selected
      return current.includes(id) ? current.filter((x) => x !== id) : [...current, id]
    })
  const move = (id: string, delta: number) =>
    setSelected((prev) => {
      const s = prev ?? selected
      const i = s.indexOf(id)
      const j = i + delta
      if (i < 0 || j < 0 || j >= s.length) return s
      const copy = [...s]
      ;[copy[i], copy[j]] = [copy[j], copy[i]]
      return copy
    })

  const chosen = strategies.find((s) => s.key === strategy)
  const notEnough = chosen ? selected.length < chosen.min_agents : false

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(
      { objective, strategy_key: strategy, agent_ids: selected },
      { onSuccess: (run) => navigate(`/runs/${run.id}`) },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4 p-4">
      <Field label={t.project.objective}>
        <Textarea
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          rows={4}
          required
          maxLength={4000}
          placeholder={t.project.objectivePlaceholder}
        />
      </Field>
      <Field label={t.project.strategy} hint={chosen?.description}>
        <Select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          {strategies.map((s) => (
            <option key={s.key} value={s.key}>{s.name}</option>
          ))}
        </Select>
      </Field>
      <div>
        <div className="mb-1 text-sm font-medium text-slate-700">{t.project.participants}</div>
        <p className="mb-2 text-xs text-slate-500">{t.project.participantsHint}</p>
        <ul className="space-y-1.5">
          {[...selected.map((id) => usable.find((a) => a.id === id)!).filter(Boolean),
            ...usable.filter((a) => !selected.includes(a.id))].map((agent) => {
            const position = selected.indexOf(agent.id)
            const on = position >= 0
            return (
              <li key={agent.id} className={cx('flex items-center gap-3 rounded-lg border px-3 py-2', on ? 'border-indigo-200 bg-indigo-50/50' : 'border-slate-200')}>
                <input type="checkbox" checked={on} onChange={() => toggle(agent.id)} className="h-4 w-4 accent-indigo-600" />
                <span className="w-5 text-xs font-semibold text-slate-400">{on ? `${position + 1}.` : ''}</span>
                <AgentName name={agent.name} index={agents.indexOf(agent)} />
                <span className="truncate text-xs text-slate-500">{agent.provider} · {agent.model}</span>
                {on && (
                  <span className="ml-auto flex gap-1">
                    <button type="button" className="rounded px-1.5 text-slate-500 hover:bg-white" onClick={() => move(agent.id, -1)}>↑</button>
                    <button type="button" className="rounded px-1.5 text-slate-500 hover:bg-white" onClick={() => move(agent.id, 1)}>↓</button>
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      </div>
      {create.error && <ErrorBox error={create.error} />}
      <Button type="submit" className="w-full" loading={create.isPending} disabled={notEnough || !objective.trim()}>
        {create.isPending ? t.project.starting : `▶ ${t.project.start}`}
      </Button>
    </form>
  )
}
