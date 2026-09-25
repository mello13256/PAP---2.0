import { useMemo } from 'react'
import { useAgents } from '../api/hooks'
import type { Agent } from '../api/types'

/** Acesso rápido a agentes por id + índice (para cores consistentes). */
export function useAgentIndex() {
  const { data: agents = [] } = useAgents()
  return useMemo(() => {
    const byId = new Map<string, { agent: Agent; index: number }>()
    agents.forEach((agent, index) => byId.set(agent.id, { agent, index }))
    return {
      agents,
      name: (id: string | null | undefined) => (id ? byId.get(id)?.agent.name : undefined),
      index: (id: string | null | undefined) => (id ? byId.get(id)?.index ?? 0 : 0),
    }
  }, [agents])
}
