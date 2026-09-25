import { useEffect, useRef } from 'react'
import type { Message, Task } from '../../api/types'
import { AgentName, Badge, cx } from '../../components/ui'
import { useAgentIndex } from '../../hooks/useAgentIndex'
import type { LiveTurn, TimelineItem, ToolEvent } from '../../hooks/useRunStream'
import { useT } from '../../i18n'

const kindStyle: Record<string, string> = {
  ORCHESTRATOR: 'border-indigo-200 bg-indigo-50/60',
  SYSTEM: 'border-rose-200 bg-rose-50',
  REVIEW: 'border-amber-200 bg-amber-50',
  TASK_RESULT: 'border-emerald-200 bg-emerald-50/60',
  USER: 'border-slate-300 bg-white',
  DECISION: 'border-violet-200 bg-violet-50',
}

function time(at: string) {
  return new Date(at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function ToolLine({ tool }: { tool: ToolEvent }) {
  const agents = useAgentIndex()
  const target = tool.arguments.path ?? tool.arguments.to ?? ''
  return (
    <div className="flex items-start gap-2 pl-4 font-mono text-xs text-slate-500">
      <span className={tool.ok ? 'text-emerald-600' : 'text-rose-600'}>{tool.ok ? '✓' : '✗'}</span>
      <span className="min-w-0">
        <span className={agents.index(tool.agent_id) >= 0 ? '' : ''}>{tool.agent_name}</span> →{' '}
        <span className="font-semibold text-slate-700">{tool.name}</span>
        {target && <span className="text-slate-600">({target})</span>}{' '}
        <span className="text-slate-400">{tool.output}</span>
      </span>
    </div>
  )
}

function MessageCard({ message, tasks }: { message: Message; tasks: Task[] }) {
  const t = useT()
  const agents = useAgentIndex()
  const task = tasks.find((x) => x.id === message.task_id)
  const sender = message.sender_agent_id
  const recipient = message.recipient_agent_id
  const isAgent = message.kind === 'AGENT'
  return (
    <div className={cx('rounded-lg border px-3 py-2', isAgent ? 'border-slate-200 bg-white' : kindStyle[message.kind])}>
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
        {sender ? (
          <AgentName name={agents.name(sender) ?? '?'} index={agents.index(sender)} />
        ) : (
          <span className="font-semibold text-slate-700">{t.kinds[message.kind]}</span>
        )}
        {sender && !isAgent && <Badge>{t.kinds[message.kind]}</Badge>}
        {recipient && (
          <span className="text-slate-400">
            → <AgentName name={agents.name(recipient) ?? '?'} index={agents.index(recipient)} />
          </span>
        )}
        {task && <Badge className="bg-slate-100 font-mono text-slate-600">{task.key}</Badge>}
        <span className="ml-auto text-slate-400">{time(message.created_at)}</span>
      </div>
      <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-800">{message.content}</div>
    </div>
  )
}

function LiveBubble({ live, tasks }: { live: LiveTurn; tasks: Task[] }) {
  const t = useT()
  const agents = useAgentIndex()
  const task = tasks.find((x) => x.id === live.task_id)
  return (
    <div className="rounded-lg border border-dashed border-indigo-300 bg-white px-3 py-2">
      <div className="mb-1 flex items-center gap-2 text-xs">
        <AgentName name={live.agent_name} index={agents.index(live.agent_id)} />
        {live.label && <Badge>{live.label}</Badge>}
        {task && <Badge className="font-mono">{task.key}</Badge>}
        <span className="ml-auto flex items-center gap-1 text-indigo-600">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" /> {t.run.live}
        </span>
      </div>
      <div className="caret whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-800">
        {live.text || <span className="italic text-slate-400">{t.run.thinking}</span>}
      </div>
    </div>
  )
}

/** Conversa entre agentes, mediada pelo orquestrador, com a resposta em curso ao vivo. */
export function AgentRoom({ timeline, live, tasks }: { timeline: TimelineItem[]; live: LiveTurn | null; tasks: Task[] }) {
  const t = useT()
  const container = useRef<HTMLDivElement>(null)

  // Acompanha o fim da conversa, mas só se o utilizador já estiver lá em baixo
  // (se subiu para ler algo, não o arrastamos). Faz scroll só desta caixa, não da página.
  useEffect(() => {
    const el = container.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 250
    if (nearBottom) el.scrollTop = el.scrollHeight
  }, [timeline.length, live?.text])

  return (
    <div ref={container} className="scrollbar-thin h-[64vh] space-y-2 overflow-y-auto p-3">
      {timeline.length === 0 && !live && <div className="p-6 text-center text-sm text-slate-400">{t.run.waiting}</div>}
      {timeline.map((item) =>
        item.type === 'message' ? (
          <MessageCard key={item.id} message={item.message} tasks={tasks} />
        ) : (
          <ToolLine key={item.id} tool={item.tool} />
        ),
      )}
      {live && <LiveBubble live={live} tasks={tasks} />}
    </div>
  )
}
