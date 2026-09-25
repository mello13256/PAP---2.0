// Tipos dos dados devolvidos pela API (espelham os esquemas Pydantic do backend).

export type Uuid = string

export interface User {
  id: Uuid
  email: string
  display_name: string
  created_at: string
}

export interface Project {
  id: Uuid
  name: string
  description: string
  status: 'ACTIVE' | 'ARCHIVED'
  created_at: string
  updated_at: string
}

export interface Agent {
  id: Uuid
  name: string
  provider: string
  model: string
  capabilities: string[]
  system_prompt: string
  config: { temperature?: number; max_output_tokens?: number }
  enabled: boolean
  provider_available: boolean
  created_at: string
}

export interface PingResult {
  ok: boolean
  text: string
  model: string | null
  latency_ms: number
  input_tokens: number | null
  output_tokens: number | null
  error_kind: string | null
  error: string | null
}

export type RunStatus =
  | 'PENDING'
  | 'PLANNING'
  | 'AWAITING_PLAN_APPROVAL'
  | 'RUNNING'
  | 'PAUSED'
  | 'WAITING_USER'
  | 'FINALIZING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'

export interface Run {
  id: Uuid
  project_id: Uuid
  objective: string
  strategy_key: string
  strategy_config: { agent_ids?: Uuid[]; name?: string }
  status: RunStatus
  final_result: string | null
  failure_reason: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface RecentRun extends Run {
  project_name: string
}

export interface Strategy {
  key: string
  name: string
  description: string
  min_agents: number
}

export type TaskStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'WAITING'
  | 'REVIEW'
  | 'FAILED'
  | 'COMPLETED'
  | 'CANCELLED'

export interface Task {
  id: Uuid
  run_id: Uuid
  key: string
  title: string
  description: string
  acceptance_criteria: string
  required_capability: string | null
  status: TaskStatus
  assigned_agent_id: Uuid | null
  assignment_reason: string | null
  priority: number
  result: string | null
  iteration_count: number
  max_iterations: number
  depends_on: string[]
}

export type MessageKind =
  | 'USER'
  | 'ORCHESTRATOR'
  | 'AGENT'
  | 'TASK_RESULT'
  | 'REVIEW'
  | 'DECISION'
  | 'SYSTEM'

export interface Message {
  id: Uuid
  run_id: Uuid
  task_id: Uuid | null
  kind: MessageKind
  sender_agent_id: Uuid | null
  sender_user_id: Uuid | null
  recipient_agent_id: Uuid | null
  content: string
  meta: Record<string, unknown>
  created_at: string
}

export interface ReviewIssue {
  id: Uuid
  severity: 'CRITICAL' | 'MAJOR' | 'MINOR' | 'INFO'
  file_path: string | null
  description: string
  suggestion: string
}

export interface Review {
  id: Uuid
  task_id: Uuid
  task_key: string
  round: number
  reviewer_agent_id: Uuid | null
  author_agent_id: Uuid | null
  verdict: 'APPROVED' | 'NEEDS_REVISION'
  summary: string
  issues: ReviewIssue[]
  created_at: string
}

export type ChangeKind = 'CREATE' | 'MODIFY' | 'REVISION' | 'DELETE'

export interface FileEntry {
  path: string
  version: number
  size_bytes: number
  change_kind: ChangeKind
  author_agent_id: Uuid | null
  author_user_id: Uuid | null
  updated_at: string
}

export interface FileVersion {
  path: string
  version: number
  size_bytes: number
  change_kind: ChangeKind
  change_summary: string
  author_agent_id: Uuid | null
  author_user_id: Uuid | null
  run_id: Uuid | null
  task_id: Uuid | null
  created_at: string
}

export interface FileContent extends FileVersion {
  content: string
  current_version: number
}

export interface RunMetrics {
  execution_time_s: number
  api_calls: number
  failed_calls: number
  input_tokens: number
  output_tokens: number
  tasks_total: number
  tasks_completed: number
  tasks_failed: number
  reviews: number
  revisions: number
  estimated_cost_usd: number | null
  final_status: string
}

export interface InstalledModel {
  name: string
  size_bytes: number
  modified_at: string | null
  parameter_size: string | null
  quantization: string | null
  family: string | null
}

export interface ModelStatus {
  ollama: { running: boolean; version: string | null; url: string }
  installed: InstalledModel[]
}

export interface CatalogModel {
  name: string
  family: string
  size_gb: number
  recommended: boolean
  description_pt: string
  description_en: string
}

export interface PullState {
  name: string
  status: string
  completed: number
  total: number
  percent: number
  done: boolean
  error: string | null
}
