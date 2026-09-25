import { AlertTriangle, CheckCircle2, ClipboardCheck, FileCode2, FileText, MessageSquare, Send, ShieldCheck, Sparkles, User, Workflow, XCircle } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import type { Message, Task } from '../../api/types'
import { Avatar, Badge, cx } from '../../components/ui'
import { useAgentIndex } from '../../hooks/useAgentIndex'
import type { LiveTurn, TimelineItem, ToolEvent } from '../../hooks/useRunStream'
import { useT } from '../../i18n'

function time(at: string) {
  return new Date(at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const TOOL_ICONS: Record<string, ReactNode> = {
  write_file: <FileCode2 className="h-3 w-3" />,
  read_file: <FileText className="h-3 w-3" />,
  list_files: <FileText className="h-3 w-3" />,
  send_message: <Send className="h-3 w-3" />,
  submit_result: <CheckCircle2 className="h-3 w-3" />,
  submit_plan: <Workflow className="h-3 w-3" />,
  submit_review: <ShieldCheck className="h-3 w-3" />,
}

function ToolChip({ tool }: { tool: ToolEvent }) {
  const target = tool.arguments.path ?? tool.arguments.to ?? ''
  return (
    <div className="flex justify-center py-0.5">
      <span
        title={tool.output}
        className={cx(
          'inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[11px] ring-1',
          tool.ok ? 'bg-slate-50 text-slate-600 ring-slate-200' : 'bg-rose-50 text-rose-700 ring-rose-200',
        )}
      >
        {tool.ok ? TOOL_ICONS[tool.name] ?? <Sparkles className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
        <span className="font-semibold">{tool.agent_name}</span>
        <span className="text-slate-400">·</span>
        <span>{tool.name}</span>
        {target && <span className="truncate text-slate-500">{target}</span>}
        {!tool.ok && <span className="truncate">— {tool.output}</span>}
      </span>
    </div>
  )
}

const SYSTEM_STYLE: Record<string, { box: string; icon: ReactNode }> = {
  ORCHESTRATOR: { box: 'border-indigo-100 bg-indigo-50/70 text-indigo-900', icon: <Workflow className="h-3.5 w-3.5 text-indigo-500" /> },
  SYSTEM: { box: 'border-rose-200 bg-rose-50 text-rose-900', icon: <AlertTriangle className="h-3.5 w-3.5 text-rose-500" /> },
  USER: { box: 'border-slate-300 bg-white text-slate-900', icon: <User className="h-3.5 w-3.5 text-slate-500" /> },
}

function MessageItem({ message, tasks }: { message: Message; tasks: Task[] }) {
  const t = useT()
  const agents = useAgentIndex()
  const task = tasks.find((x) => x.id === message.task_id)
  const sender = message.sender_agent_id
  const recipient = message.recipient_agent_id

  if (!sender) {
    const style = SYSTEM_STYLE[message.kind] ?? SYSTEM_STYLE.ORCHESTRATOR
    return (
      <div className={cx('animate-in mx-auto max-w-3xl rounded-xl border px-3.5 py-2 text-sm', style.box)}>
        <div className="mb-0.5 flex items-center gap-1.5 text-xs font-semibold opacity-80">
          {style.icon} {t.kinds[message.kind]}
          {recipient && <span className="font-normal">→ {agents.name(recipient)}</span>}
          {task && <Badge className="bg-white/70 font-mono">{task.key}</Badge>}
          <span className="ml-auto font-normal opacity-60">{time(message.created_at)}</span>
        </div>
        <div className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</div>
      </div>
    )
  }

  const index = agents.index(sender)
  const kindBox: Record<string, string> = {
    AGENT: 'bg-white border-slate-200',
    TASK_RESULT: 'bg-emerald-50/80 border-emerald-200',
    REVIEW: message.meta?.verdict === 'APPROVED' ? 'bg-emerald-50/80 border-emerald-200' : 'bg-amber-50/90 border-amber-200',
  }
  const kindIcon: Record<string, ReactNode> = {
    TASK_RESULT: <ClipboardCheck className="h-3 w-3" />,
    REVIEW: <ShieldCheck className="h-3 w-3" />,
    AGENT: <MessageSquare className="h-3 w-3" />,
  }
  return (
    <div className="animate-in flex gap-2.5">
      <Avatar name={agents.name(sender) ?? '?'} index={index} />
      <div className="min-w-0 max-w-3xl flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="font-semibold text-slate-800">{agents.name(sender)}</span>
          {message.kind !== 'AGENT' && <Badge className="bg-slate-100 text-slate-600">{kindIcon[message.kind]} {t.kinds[message.kind]}</Badge>}
          {recipient && <span className="text-slate-400">→ {agents.name(recipient)}</span>}
          {task && <Badge className="bg-slate-800 font-mono text-white">{task.key}</Badge>}
          <span className="ml-auto text-slate-400">{time(message.created_at)}</span>
        </div>
        <div className={cx('rounded-2xl rounded-tl-sm border px-3.5 py-2.5 text-sm leading-relaxed text-slate-800 shadow-sm', kindBox[message.kind] ?? 'bg-white border-slate-200')}>
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>
      </div>
    </div>
  )
}

function LiveBubble({ live, tasks }: { live: LiveTurn; tasks: Task[] }) {
  const t = useT()
  const agents = useAgentIndex()
  const task = tasks.find((x) => x.id === live.task_id)
  return (
    <div className="animate-in flex gap-2.5">
      <span className="relative">
        <Avatar name={live.agent_name} index={agents.index(live.agent_id)} />
        <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />
      </span>
      <div className="min-w-0 max-w-3xl flex-1">
        <div className="mb-1 flex items-center gap-1.5 text-xs">
          <span className="font-semibold text-slate-800">{live.agent_name}</span>
          {live.label && <Badge className="bg-indigo-50 text-indigo-700">{live.label}</Badge>}
          {task && <Badge className="bg-slate-800 font-mono text-white">{task.key}</Badge>}
          <span className="ml-auto flex items-center gap-1 text-indigo-600">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" /> {t.run.live}
          </span>
        </div>
        <div className="rounded-2xl rounded-tl-sm border border-indigo-200 bg-gradient-to-br from-white to-indigo-50/60 px-3.5 py-2.5 text-sm leading-relaxed shadow-sm">
          {live.text ? (
            <div className="caret whitespace-pre-wrap break-words text-slate-800">{live.text}</div>
          ) : (
            <div className="flex items-center gap-1.5 text-slate-400">
              <span className="flex gap-1">
                {[0, 150, 300].map((d) => <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: `${d}ms` }} />)}
              </span>
              {t.run.thinking}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** Conversa entre agentes, mediada pelo orquestrador, com a resposta em curso ao vivo. */
export function AgentRoom({ timeline, live, tasks }: { timeline: TimelineItem[]; live: LiveTurn | null; tasks: Task[] }) {
  const t = useT()
  const container = useRef<HTMLDivElement>(null)

  // Acompanha o fim da conversa, mas só se o utilizador já estiver lá em baixo.
  // Faz scroll só desta caixa, não da página.
  useEffect(() => {
    const el = container.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 250
    if (nearBottom) el.scrollTop = el.scrollHeight
  }, [timeline.length, live?.text])

  return (
    <div ref={container} className="scrollbar-thin h-[64vh] space-y-3 overflow-y-auto bg-gradient-to-b from-slate-50/80 to-white p-4">
      {timeline.length === 0 && !live && (
        <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-slate-400">
          <MessageSquare className="h-8 w-8 text-slate-300" /> {t.run.waiting}
        </div>
      )}
      {timeline.map((item) => (item.type === 'message' ? <MessageItem key={item.id} message={item.message} tasks={tasks} /> : <ToolChip key={item.id} tool={item.tool} />))}
      {live && <LiveBubble live={live} tasks={tasks} />}
    </div>
  )
}
