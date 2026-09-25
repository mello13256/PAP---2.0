import { FileCode2, FolderOpen, GitCompare, History } from 'lucide-react'
import { useState } from 'react'
import { useFile, useFileDiff, useFileHistory, useFiles } from '../../api/hooks'
import { AgentName, Badge, Empty, Loading, cx, formatDate } from '../../components/ui'
import { useAgentIndex } from '../../hooks/useAgentIndex'
import { useT } from '../../i18n'

function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="scrollbar-thin overflow-auto p-4 font-mono text-xs leading-5">
      {diff.split('\n').map((line, i) => (
        <div
          key={i}
          className={cx(
            line.startsWith('+') && !line.startsWith('+++') && 'bg-emerald-50 text-emerald-800',
            line.startsWith('-') && !line.startsWith('---') && 'bg-rose-50 text-rose-800',
            line.startsWith('@@') && 'text-indigo-600',
          )}
        >
          {line || ' '}
        </div>
      ))}
    </pre>
  )
}

/** Ficheiros do projeto: árvore, conteúdo, histórico de versões (quem/quando) e diffs. */
export function FileExplorer({ projectId, highlight }: { projectId: string; highlight?: Set<string> }) {
  const t = useT()
  const agents = useAgentIndex()
  const files = useFiles(projectId)
  const [chosenPath, setPath] = useState<string | null>(null)
  const path = chosenPath ?? files.data?.[0]?.path ?? null
  const [version, setVersion] = useState<number | undefined>()
  const [showDiff, setShowDiff] = useState(false)
  const file = useFile(projectId, path, version)
  const history = useFileHistory(projectId, path)
  const shown = file.data?.version
  const diff = useFileDiff(projectId, showDiff ? path : null, shown ? shown - 1 : undefined, shown)

  if (files.isLoading) return <Loading />
  if (!files.data?.length) return <Empty icon={<FolderOpen className="h-5 w-5" />}>{t.files.noFiles}</Empty>

  return (
    <div className="grid min-h-[480px] grid-cols-1 md:grid-cols-[260px_1fr]">
      <ul className="scrollbar-thin max-h-[70vh] overflow-auto border-b border-slate-100 p-2 md:border-b-0 md:border-r">
        {files.data.map((f) => (
          <li key={f.path}>
            <button
              onClick={() => { setPath(f.path); setVersion(undefined); setShowDiff(false) }}
              className={cx('flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left font-mono text-xs', path === f.path ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-slate-50', highlight?.has(f.path) && 'font-semibold')}
            >
              <span className="flex min-w-0 items-center gap-1.5"><FileCode2 className="h-3.5 w-3.5 shrink-0 text-slate-400" /><span className="truncate">{f.path}</span></span>
              <span className="shrink-0 text-slate-400">v{f.version}</span>
            </button>
          </li>
        ))}
      </ul>

      <div className="min-w-0">
        {!path ? <Empty>{t.files.select}</Empty> : (
          <div className="flex h-full flex-col">
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-2">
              <span className="font-mono text-sm font-medium">{path}</span>
              {file.data && <Badge>v{file.data.version}{file.data.version === file.data.current_version ? ` · ${t.files.current}` : ''}</Badge>}
              <div className="ml-auto flex gap-1">
                <button className={cx('rounded-md px-2 py-1 text-xs', !showDiff ? 'bg-slate-100 font-medium' : 'text-slate-500')} onClick={() => setShowDiff(false)}>{t.files.showContent}</button>
                <button className={cx('rounded-md px-2 py-1 text-xs', showDiff ? 'bg-slate-100 font-medium' : 'text-slate-500')} onClick={() => setShowDiff(true)} disabled={!shown || shown < 2}><GitCompare className="mr-1 inline h-3.5 w-3.5" />{t.files.showDiff}</button>
              </div>
            </div>
            <div className="grid flex-1 grid-cols-1 xl:grid-cols-[1fr_240px]">
              <div className="min-w-0 bg-slate-50/50">
                {file.isLoading ? <Loading /> : showDiff ? (diff.data ? <DiffView diff={diff.data.diff} /> : <Loading />) : (
                  <pre className="scrollbar-thin max-h-[65vh] overflow-auto bg-slate-950 p-4 font-mono text-xs leading-5 whitespace-pre text-slate-100">{file.data?.content}</pre>
                )}
              </div>
              <div className="border-t border-slate-100 p-3 xl:border-l xl:border-t-0">
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500"><History className="h-3.5 w-3.5" />{t.files.history}</div>
                <ol className="space-y-2">
                  {[...(history.data ?? [])].reverse().map((v) => (
                    <li key={v.version}>
                      <button
                        onClick={() => setVersion(v.version)}
                        className={cx('w-full rounded-md border px-2 py-1.5 text-left text-xs', shown === v.version ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50')}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold">v{v.version}</span>
                          <span className="text-slate-400">{t.files.kinds[v.change_kind]}</span>
                        </div>
                        <div className="mt-0.5">
                          {v.author_agent_id ? <AgentName name={agents.name(v.author_agent_id) ?? '?'} index={agents.index(v.author_agent_id)} /> : <span className="text-slate-600">{t.common.user}</span>}
                        </div>
                        {v.change_summary && <div className="mt-0.5 line-clamp-2 text-slate-500">{v.change_summary}</div>}
                        <div className="mt-0.5 text-slate-400">{formatDate(v.created_at)}</div>
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
