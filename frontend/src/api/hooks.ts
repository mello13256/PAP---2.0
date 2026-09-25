// Hooks de dados (TanStack Query): cache, estados de loading/erro e atualização.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, qs } from './client'
import type {
  Agent,
  CatalogModel,
  ModelStatus,
  PullState,
  FileContent,
  FileEntry,
  FileVersion,
  Message,
  PingResult,
  Project,
  RecentRun,
  Review,
  Run,
  RunMetrics,
  Strategy,
  Task,
  User,
} from './types'

export const keys = {
  me: ['me'] as const,
  projects: ['projects'] as const,
  project: (id: string) => ['project', id] as const,
  runs: (projectId: string) => ['runs', projectId] as const,
  recentRuns: ['runs', 'recent'] as const,
  run: (id: string) => ['run', id] as const,
  tasks: (runId: string) => ['tasks', runId] as const,
  reviews: (runId: string) => ['reviews', runId] as const,
  metrics: (runId: string) => ['metrics', runId] as const,
  agents: ['agents'] as const,
  strategies: ['strategies'] as const,
  files: (projectId: string) => ['files', projectId] as const,
  file: (projectId: string, path: string, version?: number) => ['file', projectId, path, version] as const,
  history: (projectId: string, path: string) => ['history', projectId, path] as const,
  providerModels: (key: string) => ['provider-models', key] as const,
}

export const useMe = () =>
  useQuery({ queryKey: keys.me, queryFn: () => api.get<User>('/auth/me'), retry: false })

export const useProjects = () =>
  useQuery({ queryKey: keys.projects, queryFn: () => api.get<Project[]>('/projects') })

export const useProject = (id: string) =>
  useQuery({ queryKey: keys.project(id), queryFn: () => api.get<Project>(`/projects/${id}`) })

export const useRecentRuns = () =>
  useQuery({ queryKey: keys.recentRuns, queryFn: () => api.get<RecentRun[]>('/runs/recent') })

export const useRuns = (projectId: string) =>
  useQuery({
    queryKey: keys.runs(projectId),
    queryFn: () => api.get<Run[]>(`/projects/${projectId}/runs`),
  })

export const useRun = (id: string) =>
  useQuery({ queryKey: keys.run(id), queryFn: () => api.get<Run>(`/runs/${id}`) })

export const useTasks = (runId: string) =>
  useQuery({ queryKey: keys.tasks(runId), queryFn: () => api.get<Task[]>(`/runs/${runId}/tasks`) })

export const useReviews = (runId: string) =>
  useQuery({
    queryKey: keys.reviews(runId),
    queryFn: () => api.get<Review[]>(`/runs/${runId}/reviews`),
  })

export const useMetrics = (runId: string) =>
  useQuery({
    queryKey: keys.metrics(runId),
    queryFn: () => api.get<RunMetrics>(`/runs/${runId}/metrics`),
  })

export const useAgents = () =>
  useQuery({ queryKey: keys.agents, queryFn: () => api.get<Agent[]>('/agents') })

export const useStrategies = () =>
  useQuery({ queryKey: keys.strategies, queryFn: () => api.get<Strategy[]>('/strategies') })

export const useFiles = (projectId: string) =>
  useQuery({
    queryKey: keys.files(projectId),
    queryFn: () => api.get<FileEntry[]>(`/projects/${projectId}/files`),
  })

export const useFile = (projectId: string, path: string | null, version?: number) =>
  useQuery({
    queryKey: keys.file(projectId, path ?? '', version),
    queryFn: () => api.get<FileContent>(`/projects/${projectId}/files/content${qs({ path: path!, version })}`),
    enabled: !!path,
  })

export const useFileHistory = (projectId: string, path: string | null) =>
  useQuery({
    queryKey: keys.history(projectId, path ?? ''),
    queryFn: () => api.get<FileVersion[]>(`/projects/${projectId}/files/history${qs({ path: path! })}`),
    enabled: !!path,
  })

export const useFileDiff = (projectId: string, path: string | null, from?: number, to?: number) =>
  useQuery({
    queryKey: ['diff', projectId, path, from, to],
    queryFn: () =>
      api.get<{ diff: string }>(
        `/projects/${projectId}/files/diff${qs({ path: path!, from_version: from, to_version: to })}`,
      ),
    enabled: !!path && from !== undefined && to !== undefined,
  })

export const useProviderModels = (key: string) =>
  useQuery({
    queryKey: keys.providerModels(key),
    queryFn: () => api.get<string[]>(`/providers/${key}/models`),
    staleTime: 60_000,
  })

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { email: string; password: string }) => api.post<User>('/auth/login', data),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { email: string; password: string; display_name: string }) =>
      api.post<User>('/auth/register', data),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<void>('/auth/logout'),
    onSuccess: () => qc.clear(),
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description: string }) => api.post<Project>('/projects', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  })
}

export function useCreateRun(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { objective: string; strategy_key: string; agent_ids: string[] }) =>
      api.post<Run>(`/projects/${projectId}/runs`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.runs(projectId) })
      qc.invalidateQueries({ queryKey: keys.recentRuns })
    },
  })
}

export function useRunControl(runId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (action: 'pause' | 'resume' | 'cancel') => api.post<Run>(`/runs/${runId}/${action}`),
    onSuccess: (run) => qc.setQueryData(keys.run(runId), run),
  })
}

export function useSendInstruction(runId: string) {
  return useMutation({
    mutationFn: (content: string) => api.post<Message>(`/runs/${runId}/messages`, { content }),
  })
}

export function useUpdateAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Agent> & { id: string }) =>
      api.patch<Agent>(`/agents/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.agents }),
  })
}

export function useCreateAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Omit<Partial<Agent>, 'id'>) => api.post<Agent>('/agents', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.agents }),
  })
}

export function useRestoreDefaultAgents() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<Agent[]>('/agents/defaults'),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.agents }),
  })
}

export const usePingAgent = () =>
  useMutation({ mutationFn: (id: string) => api.post<PingResult>(`/agents/${id}/ping`) })

export function useRemoveAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<{ deleted: boolean; agent: Agent | null }>(`/agents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.agents }),
  })
}

// ------------------------------------------------------------ modelos (Ollama)

export const useModelStatus = () =>
  useQuery({ queryKey: ['models', 'status'], queryFn: () => api.get<ModelStatus>('/models/status'), refetchInterval: 15_000 })

export const useModelCatalog = () =>
  useQuery({ queryKey: ['models', 'catalog'], queryFn: () => api.get<CatalogModel[]>('/models/catalog'), staleTime: Infinity })

export function useModelPulls() {
  const qc = useQueryClient()
  return useQuery({
    queryKey: ['models', 'pulls'],
    queryFn: async () => {
      const pulls = await api.get<PullState[]>('/models/pulls')
      if (pulls.some((p) => p.done)) qc.invalidateQueries({ queryKey: ['models', 'status'] })
      return pulls
    },
    // Enquanto houver downloads a decorrer, pergunta o progresso a cada segundo.
    refetchInterval: (query) => (query.state.data?.some((p) => !p.done) ? 1000 : false),
  })
}

export function usePullModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => api.post<PullState>('/models/pull', { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['models', 'pulls'] }),
  })
}

export function useDeleteModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => api.delete<void>(`/models/${encodeURIComponent(name)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['models', 'status'] }),
  })
}
