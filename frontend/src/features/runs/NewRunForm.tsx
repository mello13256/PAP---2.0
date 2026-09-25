import { ArrowDown, ArrowUp, Check, Rocket } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useAgents, useCreateRun, useStrategies } from '../../api/hooks'
import { Avatar, Button, ErrorBox, Field, Textarea, cx } from '../../components/ui'
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
  const ordered = [...selected.map((id) => usable.find((a) => a.id === id)!).filter(Boolean), ...usable.filter((a) => !selected.includes(a.id))]

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate({ objective, strategy_key: strategy, agent_ids: selected }, { onSuccess: (run) => navigate(`/runs/${run.id}`) })
  }

  return (
    <form onSubmit={submit} className="space-y-5 p-5">
      <Field label={t.project.objective}>
        <Textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={4} required maxLength={4000} placeholder={t.project.objectivePlaceholder} />
      </Field>

      <div>
        <div className="mb-1.5 text-sm font-medium text-slate-700">{t.project.strategy}</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {strategies.map((s) => (
            <button
              type="button"
              key={s.key}
              onClick={() => setStrategy(s.key)}
              className={cx('relative rounded-xl border p-3 text-left transition', strategy === s.key ? 'border-indigo-400 bg-indigo-50/70 ring-2 ring-indigo-100' : 'border-slate-200 hover:border-slate-300')}
            >
              {strategy === s.key && <Check className="absolute right-2.5 top-2.5 h-4 w-4 text-indigo-600" />}
              <div className="pr-5 text-sm font-medium text-slate-900">{s.name}</div>
              <div className="mt-0.5 text-xs leading-snug text-slate-500">{s.description}</div>
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="text-sm font-medium text-slate-700">{t.project.participants}</div>
        <p className="mb-2 text-xs text-slate-500">{t.project.participantsHint}</p>
        <ul className="space-y-1.5">
          {ordered.map((agent) => {
            const position = selected.indexOf(agent.id)
            const on = position >= 0
            return (
              <li key={agent.id} className={cx('flex items-center gap-3 rounded-xl border px-3 py-2 transition', on ? 'border-indigo-200 bg-white shadow-sm' : 'border-dashed border-slate-200 opacity-60')}>
                <input type="checkbox" checked={on} onChange={() => toggle(agent.id)} className="h-4 w-4 accent-indigo-600" />
                <span className="w-4 text-xs font-bold text-indigo-500">{on ? position + 1 : ''}</span>
                <Avatar name={agent.name} index={agents.indexOf(agent)} size="sm" />
                <span className="text-sm font-medium">{agent.name}</span>
                <span className="truncate font-mono text-xs text-slate-400">{agent.model}</span>
                {on && (
                  <span className="ml-auto flex gap-0.5">
                    <button type="button" className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={() => move(agent.id, -1)}><ArrowUp className="h-3.5 w-3.5" /></button>
                    <button type="button" className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={() => move(agent.id, 1)}><ArrowDown className="h-3.5 w-3.5" /></button>
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      </div>
      {create.error && <ErrorBox error={create.error} />}
      <Button type="submit" className="w-full py-2.5 text-base" icon={<Rocket className="h-4 w-4" />} loading={create.isPending} disabled={notEnough || !objective.trim()}>
        {create.isPending ? t.project.starting : t.project.start}
      </Button>
    </form>
  )
}
