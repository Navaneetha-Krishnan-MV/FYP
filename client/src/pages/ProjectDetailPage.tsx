import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Bug,
  Cpu,
  FileCode,
  GitCommitVertical,
  Loader2,
  Plus,
  RefreshCw,
  CircleAlert,
  CircleCheckBig,
  Zap,
  Clock,
  ExternalLink,
  ScrollText,
  Inbox,
} from 'lucide-react';
import { AddBugModal } from '../components/AddBugModal';
import {
  fetchAnalysesForProject,
  fetchBugsForProject,
  fetchProjectById,
  triggerAGTRAnalysis,
  triggerReindex,
} from '../services/api';
import { usePolledResource } from '../hooks/usePolledResource';
import {
  ANALYSIS_STATUS_STYLES,
  SEVERITY_STYLES,
  formatDate,
  formatDuration,
  formatRelative,
  isIndexing,
} from '../lib/format';
import { INDEXING_STAGES } from '../types';
import type { AnalysisResult, BugReport, ProjectDetail } from '../types';

type TabKey = 'bugs' | 'analyses' | 'commits' | 'chunks';

/** One poll fetches the project plus its bugs and analyses together. */
interface ProjectSnapshot {
  project: ProjectDetail;
  bugs: BugReport[];
  analyses: AnalysisResult[];
}

const POLL_INTERVAL_MS = 4000;

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [tab, setTab] = useState<TabKey>('bugs');
  const [isAddBugOpen, setIsAddBugOpen] = useState(false);
  const [triggeringBugId, setTriggeringBugId] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);

  const fetcher = useCallback(async (): Promise<ProjectSnapshot> => {
    if (!projectId) throw new Error('No project id in the URL');
    const [project, bugs, analyses] = await Promise.all([
      fetchProjectById(projectId),
      fetchBugsForProject(projectId),
      fetchAnalysesForProject(projectId),
    ]);
    return { project, bugs, analyses };
  }, [projectId]);

  // Keep polling while the repo is indexing or an AGTR run is still in flight.
  const { data, error, loading, refresh, setError } = usePolledResource(
    fetcher,
    (snapshot: ProjectSnapshot) =>
      isIndexing(snapshot.project.status) ||
      snapshot.analyses.some((a) => a.status === 'pending' || a.status === 'processing'),
    POLL_INTERVAL_MS,
  );

  const project = data?.project ?? null;
  const bugs = useMemo(() => data?.bugs ?? [], [data]);
  const analyses = useMemo(() => data?.analyses ?? [], [data]);

  const latestAnalysisByBug = useMemo(() => {
    const map = new Map<string, AnalysisResult>();
    // fetchAnalysesForProject returns newest first, so the first hit wins.
    for (const analysis of analyses) {
      if (!map.has(analysis.bugReportId)) map.set(analysis.bugReportId, analysis);
    }
    return map;
  }, [analyses]);

  const handleAnalyze = useCallback(
    async (bugId: string) => {
      setTriggeringBugId(bugId);
      setError('');
      try {
        const { analysisId } = await triggerAGTRAnalysis(bugId);
        navigate(`/analysis/${analysisId}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to trigger AGTR analysis');
        setTriggeringBugId(null);
      }
    },
    [navigate, setError],
  );

  const handleReindex = useCallback(async () => {
    if (!projectId) return;
    setReindexing(true);
    try {
      await triggerReindex(projectId);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger re-indexing');
    } finally {
      setReindexing(false);
    }
  }, [projectId, refresh, setError]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-3 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
        <p className="text-xs font-semibold uppercase tracking-wide">Loading project…</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="glass-panel rounded-2xl border border-rose-500/25 p-10 text-center space-y-4">
        <CircleAlert className="w-8 h-8 text-rose-400 mx-auto" />
        <div>
          <h2 className="text-lg font-bold text-white">Project unavailable</h2>
          <p className="mt-1 text-sm text-slate-400">{error || 'This project could not be found.'}</p>
        </div>
        <Link
          to="/projects"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to dashboard
        </Link>
      </div>
    );
  }

  const ready = project.status === 'READY';

  const tabs: { key: TabKey; label: string; count: number; icon: typeof Bug }[] = [
    { key: 'bugs', label: 'Bug Reports', count: bugs.length, icon: Bug },
    { key: 'analyses', label: 'AGTR Analyses', count: analyses.length, icon: Zap },
    { key: 'commits', label: 'Commits', count: project.commits?.length || 0, icon: GitCommitVertical },
    { key: 'chunks', label: 'Code Chunks', count: project.codeChunks?.length || 0, icon: FileCode },
  ];

  return (
    <div className="space-y-7">
      <Link
        to="/projects"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-indigo-400 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Projects Dashboard
      </Link>

      {/* Project header */}
      <div className="glass-panel rounded-2xl border border-indigo-500/15 p-6">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-black text-white tracking-tight">{project.name}</h1>
              <StatusBadge status={project.status} />
            </div>
            <p className="mt-2 text-sm text-slate-400">
              {project.description || 'No description provided'}
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
              {project.repoUrl && (
                <a
                  href={project.repoUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 font-mono text-indigo-300 hover:text-indigo-200 transition"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  {project.repoUrl}
                </a>
              )}
              <span className="inline-flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                Updated {formatRelative(project.updatedAt)}
              </span>
              <span className="px-2 py-0.5 rounded-md bg-slate-900 border border-slate-800 font-mono uppercase text-[10px]">
                {project.repoType || 'github'}
              </span>
            </div>

            {project.languages?.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {project.languages.map((lang) => (
                  <span
                    key={lang}
                    className="px-2.5 py-0.5 text-[10px] font-semibold rounded-md bg-slate-900/90 text-indigo-300 border border-slate-800"
                  >
                    {lang}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              onClick={() => void handleReindex()}
              disabled={reindexing}
              className="px-3.5 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs font-bold text-slate-300 hover:text-white hover:border-indigo-500/40 transition disabled:opacity-50 flex items-center gap-2"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${reindexing ? 'animate-spin' : ''}`} />
              Re-Index
            </button>
            <button
              onClick={() => setIsAddBugOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-extrabold shadow-lg shadow-rose-600/30 transition flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              File Bug Report
            </button>
          </div>
        </div>

        {/* Indexing pipeline progress */}
        {isIndexing(project.status) && <PipelineProgress status={project.status} />}

        {project.status === 'FAILED' && project.errorMsg && (
          <div className="mt-5 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 font-mono break-words">
            {project.errorMsg}
          </div>
        )}

        {/* Metrics */}
        <div className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3">
          <Metric icon={FileCode} label="Files" value={project.fileCount} tone="text-blue-400" />
          <Metric icon={Cpu} label="Chunks" value={project.chunkCount} tone="text-purple-400" />
          <Metric
            icon={GitCommitVertical}
            label="Commits"
            value={project.commitCount}
            tone="text-emerald-400"
          />
          <Metric icon={Bug} label="Bug Reports" value={bugs.length} tone="text-rose-400" />
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm font-semibold flex items-center gap-2.5">
          <CircleAlert className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-1.5 p-1.5 bg-slate-950/60 rounded-xl border border-slate-800/80 w-fit">
        {tabs.map(({ key, label, count, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
              tab === key
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                tab === key ? 'bg-indigo-900/60' : 'bg-slate-900'
              }`}
            >
              {count}
            </span>
          </button>
        ))}
      </div>

      {tab === 'bugs' && (
        <BugsTab
          bugs={bugs}
          ready={ready}
          latestAnalysisByBug={latestAnalysisByBug}
          triggeringBugId={triggeringBugId}
          onAnalyze={handleAnalyze}
          onAddBug={() => setIsAddBugOpen(true)}
        />
      )}
      {tab === 'analyses' && <AnalysesTab analyses={analyses} />}
      {tab === 'commits' && <CommitsTab project={project} />}
      {tab === 'chunks' && <ChunksTab project={project} />}

      {projectId && (
        <AddBugModal
          projectId={projectId}
          isOpen={isAddBugOpen}
          onClose={() => setIsAddBugOpen(false)}
          onSuccess={() => refresh()}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- tabs */

function BugsTab({
  bugs,
  ready,
  latestAnalysisByBug,
  triggeringBugId,
  onAnalyze,
  onAddBug,
}: {
  bugs: BugReport[];
  ready: boolean;
  latestAnalysisByBug: Map<string, AnalysisResult>;
  triggeringBugId: string | null;
  onAnalyze: (bugId: string) => void;
  onAddBug: () => void;
}) {
  if (bugs.length === 0) {
    return (
      <Placeholder
        icon={Bug}
        title="No bug reports yet"
        body="File a bug manually or upload a CSV export from your tracker to start localizing root causes."
        action={
          <button
            onClick={onAddBug}
            className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-extrabold shadow-lg shadow-rose-600/30 transition flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            File Bug Report
          </button>
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {!ready && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs font-semibold text-amber-300 flex items-center gap-2.5">
          <CircleAlert className="w-4 h-4 shrink-0" />
          AGTR analysis needs a fully indexed repository. Wait for the pipeline to reach READY.
        </div>
      )}

      {bugs.map((bug) => {
        const analysis = latestAnalysisByBug.get(bug.id) || bug.analysisResults?.[0];
        const running = analysis?.status === 'pending' || analysis?.status === 'processing';
        const completed = analysis?.status === 'completed';

        return (
          <div
            key={bug.id}
            className="glass-panel glass-panel-hover rounded-2xl border border-slate-800/70 p-5"
          >
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span
                    className={`px-2.5 py-0.5 text-[10px] font-extrabold rounded-md border ${SEVERITY_STYLES[bug.severity]}`}
                  >
                    {bug.severity}
                  </span>
                  {bug.externalBugId && (
                    <span className="px-2 py-0.5 text-[10px] font-mono rounded-md bg-slate-900 border border-slate-800 text-slate-400">
                      {bug.externalBugId}
                    </span>
                  )}
                  <span className="px-2 py-0.5 text-[10px] font-semibold uppercase rounded-md bg-slate-900 border border-slate-800 text-slate-500">
                    {bug.source}
                  </span>
                  {analysis && (
                    <span
                      className={`px-2.5 py-0.5 text-[10px] font-extrabold uppercase rounded-md border ${ANALYSIS_STATUS_STYLES[analysis.status]}`}
                    >
                      {analysis.status}
                    </span>
                  )}
                </div>

                <h3 className="mt-2 text-base font-bold text-white">{bug.title}</h3>
                <p className="mt-1 text-xs text-slate-400 line-clamp-2 leading-relaxed">
                  {bug.description}
                </p>

                <div className="mt-2.5 flex flex-wrap gap-3 text-[11px] text-slate-500">
                  <span>Reported by {bug.reporter || 'unknown'}</span>
                  <span>{formatDate(bug.createdAt)}</span>
                  {completed && analysis?.rootCauseFunction && (
                    <span className="font-mono text-emerald-400">
                      → {analysis.rootCauseFunction}()
                    </span>
                  )}
                </div>
              </div>

              <div className="shrink-0">
                {analysis && (running || completed) ? (
                  <Link
                    to={`/analysis/${analysis.id}`}
                    className="px-4 py-2.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white text-xs font-bold transition flex items-center gap-2"
                  >
                    {running ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Analysis Running
                      </>
                    ) : (
                      <>
                        <CircleCheckBig className="w-3.5 h-3.5" />
                        View Report
                      </>
                    )}
                  </Link>
                ) : (
                  <button
                    onClick={() => onAnalyze(bug.id)}
                    disabled={!ready || triggeringBugId === bug.id}
                    title={ready ? undefined : 'Repository is still indexing'}
                    className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-extrabold shadow-lg shadow-indigo-600/30 transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {triggeringBugId === bug.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Zap className="w-3.5 h-3.5" />
                    )}
                    {analysis?.status === 'failed' ? 'Retry AGTR' : 'Run AGTR Analysis'}
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AnalysesTab({ analyses }: { analyses: AnalysisResult[] }) {
  if (analyses.length === 0) {
    return (
      <Placeholder
        icon={Zap}
        title="No analyses run yet"
        body="Trigger AGTR localization from the Bug Reports tab to produce a ranked root-cause report."
      />
    );
  }

  return (
    <div className="glass-panel rounded-2xl border border-slate-800/70 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-950/60 text-[11px] uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-5 py-3 font-bold">Bug</th>
              <th className="px-5 py-3 font-bold">Status</th>
              <th className="px-5 py-3 font-bold">Confidence</th>
              <th className="px-5 py-3 font-bold">Root Cause</th>
              <th className="px-5 py-3 font-bold">Time</th>
              <th className="px-5 py-3 font-bold">Created</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {analyses.map((a) => (
              <tr key={a.id} className="hover:bg-slate-900/40 transition">
                <td className="px-5 py-3.5 max-w-xs">
                  <div className="font-semibold text-slate-100 truncate">
                    {a.bugReport?.title || '—'}
                  </div>
                  {a.bugReport?.externalBugId && (
                    <div className="text-[10px] font-mono text-slate-500">
                      {a.bugReport.externalBugId}
                    </div>
                  )}
                </td>
                <td className="px-5 py-3.5">
                  <span
                    className={`px-2.5 py-0.5 text-[10px] font-extrabold uppercase rounded-md border ${ANALYSIS_STATUS_STYLES[a.status]}`}
                  >
                    {a.status}
                  </span>
                </td>
                <td className="px-5 py-3.5 font-mono text-xs text-slate-300">
                  {a.confidence ? `${a.confidence} (${Math.round((a.confidenceValue || 0) * 100)}%)` : '—'}
                </td>
                <td className="px-5 py-3.5 font-mono text-xs text-emerald-400">
                  {a.rootCauseFunction ? `${a.rootCauseFunction}()` : '—'}
                </td>
                <td className="px-5 py-3.5 font-mono text-xs text-slate-400">
                  {formatDuration(a.processingTimeMs)}
                </td>
                <td className="px-5 py-3.5 text-xs text-slate-400">{formatRelative(a.createdAt)}</td>
                <td className="px-5 py-3.5 text-right">
                  <Link
                    to={`/analysis/${a.id}`}
                    className="text-xs font-bold text-indigo-400 hover:text-indigo-300 transition"
                  >
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CommitsTab({ project }: { project: ProjectDetail }) {
  const commits = project.commits || [];
  if (commits.length === 0) {
    return (
      <Placeholder
        icon={GitCommitVertical}
        title="No commit history indexed"
        body="Git history is captured for GitHub repositories during the GIT_INDEXING stage."
      />
    );
  }

  return (
    <div className="space-y-2.5">
      {commits.map((commit) => (
        <div
          key={commit.id}
          className="glass-panel rounded-xl border border-slate-800/70 p-4 flex items-start gap-3.5"
        >
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/25 shrink-0">
            <GitCommitVertical className="w-4 h-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="font-mono text-xs font-bold text-purple-300">
                {commit.commitHash.slice(0, 8)}
              </span>
              <span className="text-xs text-slate-400">{commit.authorName}</span>
              <span className="text-[11px] text-slate-500">{formatDate(commit.committedAt)}</span>
            </div>
            <p className="mt-1 text-sm text-slate-200 break-words">
              {commit.message.split('\n')[0]}
            </p>
          </div>
        </div>
      ))}
      <p className="text-[11px] text-slate-500 px-1">
        Showing the {commits.length} most recent commits of {project.commitCount} indexed.
      </p>
    </div>
  );
}

function ChunksTab({ project }: { project: ProjectDetail }) {
  const chunks = project.codeChunks || [];
  if (chunks.length === 0) {
    return (
      <Placeholder
        icon={FileCode}
        title="No code chunks indexed"
        body="Chunks are produced by AST parsing during the PARSING stage and embedded into pgvector."
      />
    );
  }

  return (
    <div className="space-y-2.5">
      {chunks.map((chunk) => (
        <div key={chunk.id} className="glass-panel rounded-xl border border-slate-800/70 p-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/25">
              {chunk.chunkType}
            </span>
            <span className="font-mono text-sm font-bold text-white">
              {chunk.className ? `${chunk.className}.` : ''}
              {chunk.functionName}()
            </span>
            <span className="px-2 py-0.5 text-[10px] font-semibold rounded-md bg-slate-900 border border-slate-800 text-slate-400">
              {chunk.language}
            </span>
          </div>
          <div className="mt-1.5 text-[11px] font-mono text-slate-500 break-all">
            {chunk.filePath}:{chunk.startLine}-{chunk.endLine}
          </div>
          {chunk.calls?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {chunk.calls.slice(0, 6).map((call, i) => (
                <span
                  key={`${chunk.id}-${call}-${i}`}
                  className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-950/70 border border-slate-800 text-slate-400"
                >
                  → {call}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
      <p className="text-[11px] text-slate-500 px-1">
        Showing {chunks.length} of {project.chunkCount} indexed chunks.
      </p>
    </div>
  );
}

/* -------------------------------------------------------------- primitives */

function StatusBadge({ status }: { status: ProjectDetail['status'] }) {
  if (status === 'READY') {
    return (
      <span className="px-3 py-1 text-[11px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
        <CircleCheckBig className="w-3.5 h-3.5" />
        INDEXED &amp; READY
      </span>
    );
  }
  if (status === 'FAILED') {
    return (
      <span className="px-3 py-1 text-[11px] font-bold rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center gap-1.5">
        <CircleAlert className="w-3.5 h-3.5" />
        FAILED
      </span>
    );
  }
  return (
    <span className="px-3 py-1 text-[11px] font-bold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1.5">
      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
      {status}
    </span>
  );
}

function PipelineProgress({ status }: { status: ProjectDetail['status'] }) {
  const current = INDEXING_STAGES.indexOf(status);

  return (
    <div className="mt-5 p-4 rounded-xl bg-slate-950/50 border border-slate-800/80">
      <div className="flex items-center gap-2 mb-3">
        <ScrollText className="w-3.5 h-3.5 text-indigo-400" />
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
          Indexing pipeline
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {INDEXING_STAGES.map((stage, i) => {
          const done = current > i;
          const active = current === i;
          return (
            <span
              key={stage}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-md border transition ${
                done
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                  : active
                    ? 'bg-indigo-600 text-white border-indigo-400 animate-pulse'
                    : 'bg-slate-900/60 text-slate-600 border-slate-800'
              }`}
            >
              {stage}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Bug;
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-center">
      <div className="text-[11px] text-slate-400 flex items-center justify-center gap-1.5 mb-1">
        <Icon className={`w-3.5 h-3.5 ${tone}`} />
        {label}
      </div>
      <div className="text-lg font-extrabold text-white font-mono">
        {(value || 0).toLocaleString()}
      </div>
    </div>
  );
}

function Placeholder({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: typeof Inbox;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="glass-panel rounded-2xl border border-dashed border-slate-800/70 py-16 px-6 flex flex-col items-center text-center gap-4">
      <div className="p-4 rounded-2xl bg-slate-900 text-slate-400 border border-slate-800">
        <Icon className="w-7 h-7" />
      </div>
      <div>
        <h3 className="text-base font-bold text-white">{title}</h3>
        <p className="mt-1 text-sm text-slate-400 max-w-md">{body}</p>
      </div>
      {action}
    </div>
  );
}
