// Ligação em tempo real a um run (Server-Sent Events).
//
// O browser liga-se a /api/runs/{id}/events. O servidor primeiro reenvia todos os
// eventos guardados (histórico do run) e depois os novos, à medida que acontecem.
// O EventSource volta a ligar-se sozinho se a ligação cair (com Last-Event-ID).
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { keys } from '../api/hooks'
import type { Message, Task } from '../api/types'

export interface ToolEvent {
  id: string
  agent_id: string
  agent_name: string
  task_id: string | null
  name: string
  arguments: Record<string, string>
  ok: boolean
  output: string
  created_at: string
}

export type TimelineItem =
  | { type: 'message'; id: string; at: string; message: Message }
  | { type: 'tool'; id: string; at: string; tool: ToolEvent }

export interface LiveTurn {
  turn_id: string
  agent_id: string
  agent_name: string
  task_id: string | null
  label: string
  text: string
}

const REFRESH_ON = new Set(['run.status', 'run.finished', 'review.completed', 'file.changed', 'plan.created'])

export function useRunStream(runId: string, projectId?: string) {
  const qc = useQueryClient()
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  const [live, setLive] = useState<LiveTurn | null>(null)
  const [connected, setConnected] = useState(false)
  const seen = useRef(new Set<string>())

  useEffect(() => {
    seen.current = new Set()
    setTimeline([])
    setLive(null)
    const source = new EventSource(`/api/runs/${runId}/events`)
    const add = (item: TimelineItem) => {
      if (seen.current.has(item.id)) return
      seen.current.add(item.id)
      setTimeline((items) => [...items, item])
    }
    const parse = (e: MessageEvent) => JSON.parse(e.data)

    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)

    source.addEventListener('message.created', (e) => {
      const m = parse(e as MessageEvent) as Message & { created_at: string }
      add({ type: 'message', id: m.id, at: m.created_at, message: m })
      const turn = (m.meta as { turn_id?: string })?.turn_id
      if (turn) setLive((current) => (current?.turn_id === turn ? null : current))
    })
    source.addEventListener('tool.called', (e) => {
      const tool = parse(e as MessageEvent) as ToolEvent
      add({ type: 'tool', id: `tool-${(e as MessageEvent).lastEventId}`, at: tool.created_at, tool })
    })
    source.addEventListener('agent.started', (e) => {
      const p = parse(e as MessageEvent)
      setLive({ turn_id: p.turn_id, agent_id: p.agent_id, agent_name: p.agent_name, task_id: p.task_id, label: p.label ?? '', text: '' })
    })
    source.addEventListener('agent.delta', (e) => {
      const p = parse(e as MessageEvent)
      setLive((current) => (current && current.turn_id === p.turn_id ? { ...current, text: current.text + p.text } : current))
    })
    source.addEventListener('task.updated', (e) => {
      const task = parse(e as MessageEvent) as Task
      qc.setQueryData<Task[]>(keys.tasks(runId), (tasks) =>
        tasks ? tasks.map((t) => (t.id === task.id ? { ...t, ...task } : t)) : tasks,
      )
    })
    for (const type of REFRESH_ON) {
      source.addEventListener(type, () => {
        qc.invalidateQueries({ queryKey: keys.run(runId) })
        qc.invalidateQueries({ queryKey: keys.tasks(runId) })
        qc.invalidateQueries({ queryKey: keys.reviews(runId) })
        qc.invalidateQueries({ queryKey: keys.metrics(runId) })
        if (projectId) qc.invalidateQueries({ queryKey: keys.files(projectId) })
        if (type === 'run.finished' || type === 'run.status') setLive(null)
      })
    }
    return () => source.close()
  }, [runId, projectId, qc])

  return { timeline, live, connected }
}
