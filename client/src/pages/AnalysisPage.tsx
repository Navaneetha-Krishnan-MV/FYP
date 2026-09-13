import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  CircleAlert,
  Clock,
  Copy,
  Check,
  FileCode,
  GitCommitVertical,
  ListOrdered,
  Loader2,
  ShieldAlert,
  Wand2,
  Zap,
  Brain,
  RefreshCw,
} from 'lucide-react';
import { AGTRWeightsCard } from '../components/AGTRWeightsCard';
import { SubgraphVisualizer } from '../components/SubgraphVisualizer';
import { fetchAnalysisById, triggerAGTRAnalysis } from '../services/api';
import { usePolledResource } from '../hooks/usePolledResource';
import {
  ANALYSIS_STATUS_STYLES,
  SEVERITY_STYLES,
  formatDate,
  formatDuration,
  fileName,
} from '../lib/format';
import type { AGTRCandidate, AnalysisResult } from '../types';

const POLL_INTERVAL_MS = 3000;

const PIPELINE_STEPS = [
  'Gemini query expansion',
  'pgvector semantic retrieval',
  'Confidence C & dynamic weights',
  'Adaptive Neo4j hop expansion',
  'Git temporal decay scoring',
  'AGTR final ranking',
  'Grounded RAG root-cause reasoning',
];

export function AnalysisPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const navigate = useNavigate();

  const [retrying, setRetrying] = useState(false);

  const fetcher = useCallback(() => {
    if (!analysisId) return Promise.reject(new Error('No analysis id in the URL'));
    return fetchAnalysisById(analysisId);
  }, [analysisId]);

  // Poll until the AGTR pipeline reports a terminal state.
  const {
    data: analysis,
    error,
    loading,
    setError,
  } = usePolledResource(
    fetcher,
    (result: AnalysisResult) => result.status === 'pending' || result.status === 'processing',
    POLL_INTERVAL_MS,
  );

  const handleRetry = async (bugReportId: string) => {
    setRetrying(true);
    setError('');
    try {
      const { analysisId: newAnalysisId } = await triggerAGTRAnalysis(bugReportId);
      navigate(`/analysis/${newAnalysisId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retrigger analysis');
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-3 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
        <p className="text-xs font-semibold uppercase tracking-wide">Loading analysis…</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="glass-panel rounded-2xl border border-rose-500/25 p-10 text-center space-y-4">
        <CircleAlert className="w-8 h-8 text-rose-400 mx-auto" />
        <div>
          <h2 className="text-lg font-bold text-white">Analysis unavailable</h2>
          <p className="mt-1 text-sm text-slate-400">
            {error || 'This analysis result could not be found.'}
          </p>
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

  const backTo = analysis.projectId ? `/projects/${analysis.projectId}` : '/projects';
  const ranking = analysis.finalRanking || [];
  const dependencyPaths = analysis.evidenceContext?.dependency_paths || [];
  const gitCommits = analysis.evidenceContext?.git_commits || [];

  return (
    <div className="space-y-7">
      <Link
        to={backTo}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-indigo-400 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        {analysis.project?.name || 'Back to project'}
      </Link>

      {/* Bug header */}
      <div className="glass-panel rounded-2xl border border-indigo-500/15 p-6">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="px-2.5 py-1 text-[10px] font-extrabold uppercase rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/25 flex items-center gap-1.5">
                <Zap className="w-3 h-3" />
                AGTR Localization Report
              </span>
              <span
                className={`px-2.5 py-1 text-[10px] font-extrabold uppercase rounded-md border ${ANALYSIS_STATUS_STYLES[analysis.status]}`}
              >
                {analysis.status}
              </span>
              {analysis.bugReport && (
                <span
                  className={`px-2.5 py-1 text-[10px] font-extrabold rounded-md border ${SEVERITY_STYLES[analysis.bugReport.severity]}`}
                >
                  {analysis.bugReport.severity}
                </span>
              )}
            </div>

            <h1 className="mt-3 text-2xl font-black text-white tracking-tight">
              {analysis.bugReport?.title || 'Bug analysis'}
            </h1>
            {analysis.bugReport?.description && (
              <p className="mt-2 text-sm text-slate-400 leading-relaxed max-w-3xl">
                {analysis.bugReport.description}
              </p>
            )}

            <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                Started {formatDate(analysis.createdAt)}
              </span>
              {analysis.completedAt && (
                <span>Completed {formatDate(analysis.completedAt)}</span>
              )}
              {analysis.processingTimeMs !== undefined && (
                <span className="font-mono text-indigo-300">
                  {formatDuration(analysis.processingTimeMs)} pipeline runtime
                </span>
              )}
            </div>
          </div>

          {(analysis.status === 'failed' || analysis.status === 'completed') && (
            <button
              onClick={() => void handleRetry(analysis.bugReportId)}
              disabled={retrying}
              className="shrink-0 px-4 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs font-bold text-slate-300 hover:text-white hover:border-indigo-500/40 transition disabled:opacity-50 flex items-center gap-2"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${retrying ? 'animate-spin' : ''}`} />
              Re-run analysis
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm font-semibold flex items-center gap-2.5">
          <CircleAlert className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {(analysis.status === 'pending' || analysis.status === 'processing') && <RunningPanel />}

      {analysis.status === 'failed' && (
        <div className="glass-panel rounded-2xl border border-rose-500/25 p-8 text-center space-y-3">
          <CircleAlert className="w-8 h-8 text-rose-400 mx-auto" />
          <h2 className="text-lg font-bold text-white">AGTR pipeline failed</h2>
          <p className="text-sm text-slate-400 max-w-lg mx-auto">
            The FastAPI analysis service could not complete this run. Check the ai-server logs for
            the traceback, then re-run once the cause is addressed.
          </p>
        </div>
      )}

      {analysis.status === 'completed' && (
        <>
          <RootCausePanel analysis={analysis} />

          <AGTRWeightsCard
            weights={analysis.agtrWeights}
            semanticGap={analysis.semanticGap}
            confidence={analysis.confidence}
            confidenceValue={analysis.confidenceValue}
            hopsUsed={analysis.hopsUsed}
          />

          <SubgraphVisualizer
            rootCauseFile={analysis.rootCauseFile}
            rootCauseFunction={analysis.rootCauseFunction}
            dependencyPaths={dependencyPaths}
            gitCommit={analysis.rootCauseCommit}
            hopsUsed={analysis.hopsUsed}
          />

          <RankingTable candidates={ranking} rootCauseFunction={analysis.rootCauseFunction} />

          {gitCommits.length > 0 && (
            <div className="glass-panel rounded-2xl border border-purple-500/20 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2.5 rounded-xl bg-purple-500/15 text-purple-400 border border-purple-500/30">
                  <GitCommitVertical className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Temporal Git Evidence</h3>
                  <p className="text-xs text-slate-400">
                    Recent commits that raised the suspiciousness of the ranked files
                  </p>
                </div>
              </div>
              <div className="space-y-2.5">
                {gitCommits.map((commit, i) => (
                  <div
                    key={`${commit.hash}-${i}`}
                    className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80"
                  >
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="font-mono text-xs font-bold text-purple-300">
                        {commit.hash}
                      </span>
                      <span className="text-xs text-slate-400">{commit.author}</span>
                      <span className="text-[11px] text-slate-500">{commit.date}</span>
                    </div>
                    <p className="mt-1 text-sm text-slate-200 break-words">
                      {commit.message?.split('\n')[0]}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- panels */

function RunningPanel() {
  return (
    <div className="glass-panel rounded-2xl border border-indigo-500/25 p-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2.5 rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">Running the AGTR pipeline</h2>
          <p className="text-xs text-slate-400">
            This page refreshes automatically — multi-stage retrieval usually takes 20–90 seconds.
          </p>
        </div>
      </div>

      <ol className="space-y-2.5">
        {PIPELINE_STEPS.map((step, i) => (
          <li
            key={step}
            className="flex items-center gap-3 p-3 rounded-xl bg-slate-950/50 border border-slate-800/70"
          >
            <span className="w-6 h-6 shrink-0 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-[11px] font-mono font-bold flex items-center justify-center">
              {i + 1}
            </span>
            <span className="text-sm text-slate-300">{step}</span>
            <span className="ml-auto w-2 h-2 rounded-full bg-indigo-500/60 animate-pulse" />
          </li>
        ))}
      </ol>
    </div>
  );
}

function RootCausePanel({ analysis }: { analysis: AnalysisResult }) {
  const [copied, setCopied] = useState(false);

  const copyFix = async () => {
    if (!analysis.suggestedFix) return;
    try {
      await navigator.clipboard.writeText(analysis.suggestedFix);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — nothing useful to show the user */
    }
  };

  return (
    <div className="glass-panel rounded-2xl border border-emerald-500/25 p-6 shadow-xl">
      <div className="flex items-center gap-3 mb-5">
        <div className="p-2.5 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <ShieldAlert className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">Localized Root Cause</h2>
          <p className="text-xs text-slate-400">
            Gemini reasoning grounded on the top-ranked AGTR evidence
          </p>
        </div>
      </div>

      <div className="grid sm:grid-cols-3 gap-3 mb-5">
        <Fact icon={FileCode} label="File" value={fileName(analysis.rootCauseFile)} title={analysis.rootCauseFile} />
        <Fact
          icon={Wand2}
          label="Function"
          value={analysis.rootCauseFunction ? `${analysis.rootCauseFunction}()` : '—'}
        />
        <Fact icon={GitCommitVertical} label="Commit" value={analysis.rootCauseCommit || '—'} />
      </div>

      {analysis.explanation && (
        <section className="mb-5">
          <SectionLabel icon={Brain}>Explanation</SectionLabel>
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
            {analysis.explanation}
          </p>
        </section>
      )}

      {analysis.dependencyPath && (
        <section className="mb-5">
          <SectionLabel icon={ListOrdered}>Dependency Path</SectionLabel>
          {/* The pipeline emits one "- Path: a -> b" line per chain. */}
          <pre className="text-xs font-mono text-indigo-300/90 bg-slate-950/60 px-3.5 py-2.5 rounded-xl border border-slate-800/70 whitespace-pre-wrap break-words">
            {analysis.dependencyPath}
          </pre>
        </section>
      )}

      {analysis.suggestedFix && (
        <section>
          <div className="flex items-center justify-between mb-2">
            <SectionLabel icon={Wand2}>Suggested Fix</SectionLabel>
            <button
              onClick={() => void copyFix()}
              className="text-[11px] font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="text-xs font-mono text-slate-200 bg-slate-950/70 p-4 rounded-xl border border-slate-800/70 overflow-x-auto whitespace-pre-wrap">
            {analysis.suggestedFix}
          </pre>
        </section>
      )}
    </div>
  );
}

function RankingTable({
  candidates,
  rootCauseFunction,
}: {
  candidates: AGTRCandidate[];
  rootCauseFunction?: string;
}) {
  if (candidates.length === 0) return null;

  const top = candidates.slice(0, 10);
  const maxScore = Math.max(...top.map((c) => c.agtrScore), 0.0001);

  return (
    <div className="glass-panel rounded-2xl border border-indigo-500/20 p-6">
      <div className="flex items-center gap-3 mb-5">
        <div className="p-2.5 rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
          <ListOrdered className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-base font-bold text-white">Ranked Candidates</h3>
          <p className="text-xs text-slate-400">
            Top {top.length} of {candidates.length} scored by AGTR = w_s·semantic + w_g·graph +
            w_t·git
          </p>
        </div>
      </div>

      <div className="space-y-2.5">
        {top.map((c) => {
          const isRootCause =
            rootCauseFunction !== undefined && c.functionName === rootCauseFunction;
          return (
            <div
              key={c.chunkId}
              className={`p-4 rounded-xl border transition ${
                isRootCause
                  ? 'bg-emerald-500/[0.06] border-emerald-500/35'
                  : 'bg-slate-950/60 border-slate-800/80'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  <span
                    className={`w-7 h-7 shrink-0 rounded-lg text-xs font-mono font-extrabold flex items-center justify-center border ${
                      isRootCause
                        ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/35'
                        : 'bg-slate-900 text-slate-400 border-slate-800'
                    }`}
                  >
                    {c.rank}
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-bold text-white break-all">
                        {c.className ? `${c.className}.` : ''}
                        {c.functionName}()
                      </span>
                      {isRootCause && (
                        <span className="px-2 py-0.5 text-[9px] font-black uppercase tracking-wider rounded bg-emerald-500 text-slate-950">
                          Root Cause
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] font-mono text-slate-500 break-all">
                      {c.filePath}
                    </div>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-base font-extrabold text-white font-mono">
                    {c.agtrScore.toFixed(4)}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">
                    AGTR
                  </div>
                </div>
              </div>

              {/* Signal contribution bar */}
              <div className="mt-3 h-2 rounded-full bg-slate-900 overflow-hidden border border-slate-800 flex">
                <div
                  className="h-full bg-indigo-500"
                  style={{ width: `${(c.semanticScore / maxScore) * 33}%` }}
                  title={`Semantic ${c.semanticScore.toFixed(4)}`}
                />
                <div
                  className="h-full bg-purple-500"
                  style={{ width: `${(c.graphScore / maxScore) * 33}%` }}
                  title={`Graph ${c.graphScore.toFixed(4)}`}
                />
                <div
                  className="h-full bg-emerald-500"
                  style={{ width: `${(c.gitScore / maxScore) * 33}%` }}
                  title={`Git ${c.gitScore.toFixed(4)}`}
                />
              </div>

              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[11px] font-mono">
                <Signal color="bg-indigo-500" label="semantic" value={c.semanticScore} />
                <Signal color="bg-purple-500" label="graph" value={c.graphScore} />
                <Signal color="bg-emerald-500" label="git" value={c.gitScore} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- primitives */

function Signal({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <span className="flex items-center gap-1.5 text-slate-400">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      {label} <span className="text-slate-200">{value.toFixed(4)}</span>
    </span>
  );
}

function Fact({
  icon: Icon,
  label,
  value,
  title,
}: {
  icon: typeof FileCode;
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5 mb-1">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <div className="text-sm font-mono font-bold text-emerald-300 break-all" title={title}>
        {value}
      </div>
    </div>
  );
}

function SectionLabel({ icon: Icon, children }: { icon: typeof Brain; children: string }) {
  return (
    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-2">
      <Icon className="w-3.5 h-3.5 text-indigo-400" />
      {children}
    </div>
  );
}
