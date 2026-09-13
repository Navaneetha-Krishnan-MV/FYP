import { useState } from 'react';
import {
  Brain,
  FileText,
  Database,
  Layers,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Cpu,
} from 'lucide-react';
import type { AnalysisResult } from '../types';
import { AgentDecisionTimeline } from './AgentDecisionTimeline';
import { AgentAGTRRanking } from './AgentAGTRRanking';

const STAGES: Record<string, string> = {
  queued: 'Waiting for an analysis worker',
  starting: 'Checking repository and models',
  understand: 'Understanding the bug report',
  investigate: 'Specialist agents collecting repository evidence',
  rank: 'AGTR scoring and ranking investigated candidates',
  reason: 'Comparing root-cause hypotheses',
  verify: 'Validating evidence and checking contradictions',
  replan: 'Refining investigation plan',
  finalize: 'Synthesizing final diagnostic report',
  completed: 'Investigation complete',
  failed: 'Investigation failed',
};

type TabType = 'timeline' | 'report' | 'evidence' | 'all';

export function AgenticReportPanel({ analysis }: { analysis: AnalysisResult }) {
  const [activeTab, setActiveTab] = useState<TabType>('timeline');
  const context = analysis.evidenceContext;
  const report = context?.report;
  const phaseOutputs = context?.phase_outputs ?? [];
  const evidenceCount = context?.evidence?.length ?? 0;

  return (
    <div className="space-y-6">
      {/* ── Status & Metadata Overview Card ────────────────────────── */}
      <section className="glass-panel rounded-2xl border border-indigo-500/25 p-6 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                {analysis.status === 'processing' && (
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
                )}
                <span
                  className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                    analysis.status === 'completed'
                      ? 'bg-emerald-400'
                      : analysis.status === 'failed'
                      ? 'bg-rose-400'
                      : 'bg-sky-400'
                  }`}
                />
              </span>
              <h2 className="text-lg font-bold text-white tracking-tight">
                {STAGES[context?.stage ?? 'queued'] ?? 'Investigating'}
              </h2>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              {context?.reasoning && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
                  <Sparkles className="w-3 h-3 text-indigo-400" />
                  {context.reasoning.provider} · {context.reasoning.model}
                </span>
              )}
              {context?.embedding && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
                  <Database className="w-3 h-3 text-sky-400" />
                  {context.embedding.provider} · {context.embedding.model}
                </span>
              )}
              {context?.usage && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
                  <Cpu className="w-3 h-3 text-emerald-400" />
                  {context.usage.llm_calls} LLM calls · {context.usage.tool_calls} tool calls
                </span>
              )}
              {context?.usage?.elapsed_seconds !== undefined && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300 font-mono">
                  <Clock className="w-3 h-3 text-purple-400" />
                  {context.usage.elapsed_seconds.toFixed(1)}s
                </span>
              )}
            </div>
          </div>

          {/* Quick Outcome Pill (if finished) */}
          {report && (
            <div
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border self-start md:self-auto ${
                report.outcome === 'supported_hypothesis'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
              }`}
            >
              {report.outcome === 'supported_hypothesis' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              )}
              <span className="text-xs font-bold">
                {report.outcome === 'supported_hypothesis'
                  ? 'Hypothesis Supported'
                  : 'Inconclusive Analysis'}
              </span>
            </div>
          )}
        </div>

        {analysis.status === 'pending' && (
          <p className="mt-3 text-sm text-slate-400">
            The investigation will begin when a worker is available. This page refreshes automatically.
          </p>
        )}

        {context?.error && (
          <p role="alert" className="mt-3 text-sm text-rose-300 bg-rose-500/10 border border-rose-500/25 rounded-xl p-3">
            {context.error}
          </p>
        )}
      </section>

      {/* ── View Switcher Tabs ─────────────────────────────────────── */}
      <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-950/80 border border-slate-800/80 w-fit overflow-x-auto max-w-full">
        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'timeline'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
          }`}
        >
          <Brain className="w-3.5 h-3.5" />
          <span>Decision Timeline</span>
          {phaseOutputs.length > 0 && (
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono ${
              activeTab === 'timeline' ? 'bg-indigo-700/80 text-white' : 'bg-slate-800 text-slate-400'
            }`}>
              {phaseOutputs.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('report')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'report'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Executive Report</span>
          {report && (
            <span className={`w-2 h-2 rounded-full ${report.outcome === 'supported_hypothesis' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
          )}
        </button>

        <button
          onClick={() => setActiveTab('evidence')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'evidence'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Evidence Archive</span>
          {evidenceCount > 0 && (
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono ${
              activeTab === 'evidence' ? 'bg-indigo-700/80 text-white' : 'bg-slate-800 text-slate-400'
            }`}>
              {evidenceCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('all')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'all'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>All Views</span>
        </button>
      </div>

      {/* ── Tab 1: Agent Decision Timeline ─────────────────────────── */}
      {(activeTab === 'timeline' || activeTab === 'all') && (
        <AgentDecisionTimeline analysis={analysis} />
      )}

      {/* ── Tab 2: Executive Report ────────────────────────────────── */}
      {(activeTab === 'report' || activeTab === 'all') && (
        <>
          {context?.variant === 'agent-agtr' && analysis.agtrWeights && (
            <AgentAGTRRanking candidates={analysis.finalRanking} weights={analysis.agtrWeights}
              semanticGap={analysis.semanticGap} hopsUsed={analysis.hopsUsed}
              availability={context.signal_availability} warnings={context.ranking_warnings}
              selectedId={report?.primary_hypothesis?.candidate_id} rationale={report?.ranking_rationale} />
          )}
          {report ? (
            <div className="space-y-5">
              <section className="glass-panel rounded-2xl border border-emerald-500/20 p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-emerald-400" />
                    {report.outcome === 'supported_hypothesis'
                      ? 'Supported Root-Cause Hypothesis'
                      : 'Inconclusive Investigation'}
                  </h2>
                  <span className="text-[11px] font-semibold text-amber-300/90 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-md">
                    Static evidence review · not runtime verified
                  </span>
                </div>

                {analysis.rootCauseFile && (
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-indigo-500/30">
                    <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Identified Culprit Target</span>
                    <p className="font-mono text-sm text-indigo-300 break-all font-semibold">
                      {analysis.rootCauseFile} {analysis.rootCauseFunction ? `→ ${analysis.rootCauseFunction}()` : ''}
                    </p>
                  </div>
                )}

                {analysis.explanation && (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Mechanism & Explanation</h3>
                    <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap bg-slate-950/40 p-4 rounded-xl border border-slate-800/80">
                      {analysis.explanation}
                    </p>
                  </div>
                )}

                {analysis.suggestedFix && (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Suggested Resolution</h3>
                    <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-950/40 p-4 rounded-xl border border-slate-800/80">
                      {analysis.suggestedFix}
                    </p>
                  </div>
                )}

                {report.verification?.explanation && (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Verification Review</h3>
                    <p className="text-sm text-slate-400 bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/80">
                      {report.verification.explanation}
                    </p>
                  </div>
                )}

                {report.limitations && report.limitations.length > 0 && (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Limitations</h3>
                    <ul className="text-xs text-slate-400 list-disc pl-5 space-y-1">
                      {report.limitations.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="pt-2 border-t border-slate-800 flex flex-wrap items-center justify-between text-xs text-slate-500">
                  <span>Termination: {report.termination_reason?.replaceAll('_', ' ')}</span>
                  <span>{report.rounds_used} round(s) utilized</span>
                </div>
              </section>

              {/* Hypotheses considered */}
              {report.hypotheses && report.hypotheses.length > 0 && (
                <section className="glass-panel rounded-2xl p-6 space-y-4">
                  <h3 className="font-bold text-white text-base">Hypotheses Considered</h3>
                  <div className="space-y-3">
                    {report.hypotheses.map((hypothesis, i) => (
                      <div
                        key={`${hypothesis.candidate_id}-${i}`}
                        className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 text-sm text-slate-300 space-y-2.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-bold text-indigo-300">
                            Candidate: {hypothesis.candidate_id}
                          </span>
                        </div>
                        <p className="text-slate-200">{hypothesis.mechanism}</p>
                        {hypothesis.assumptions && hypothesis.assumptions.length > 0 && (
                          <p className="text-xs text-slate-400">
                            <span className="font-bold text-slate-500">Assumptions: </span>
                            {hypothesis.assumptions.join('; ')}
                          </p>
                        )}
                        <div className="flex flex-wrap gap-2 pt-1">
                          {hypothesis.evidence_ids?.map((id) => (
                            <a
                              key={id}
                              href={`#${id}`}
                              className="text-xs font-mono text-indigo-300 underline bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20"
                            >
                              {id}
                            </a>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          ) : (
            <div className="glass-panel rounded-2xl border border-slate-800 p-8 text-center text-slate-400">
              <p className="text-sm">The executive report will be generated once the agent completes the reasoning and verification phases.</p>
            </div>
          )}
        </>
      )}

      {/* ── Tab 3: Repository Evidence ─────────────────────────────── */}
      {(activeTab === 'evidence' || activeTab === 'all') && (
        <section className="glass-panel rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-white text-base">Repository Evidence Archive</h3>
            {context?.revision && (
              <span className="text-xs font-mono text-slate-500">Revision: {context.revision.slice(0, 10)}</span>
            )}
          </div>

          {evidenceCount > 0 ? (
            <div className="space-y-3">
              {context?.evidence?.map((evidence) => (
                <details
                  key={evidence.id}
                  id={evidence.id}
                  className="group rounded-xl border border-slate-800/80 bg-slate-950/60 p-4 transition-all"
                >
                  <summary className="cursor-pointer text-sm text-slate-300 break-all font-medium flex items-center justify-between">
                    <span>
                      <span className="font-bold uppercase text-[11px] text-indigo-400 mr-2 px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">
                        {evidence.kind}
                      </span>
                      {evidence.file_path ?? evidence.resolution ?? 'Dependency relationship'}
                      {evidence.start_line ? `:${evidence.start_line}–${evidence.end_line}` : ''}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">{evidence.id}</span>
                  </summary>

                  {evidence.commit_hash && (
                    <p className="mt-3 text-xs text-purple-300 bg-purple-500/10 p-2.5 rounded-lg border border-purple-500/20">
                      Commit <span className="font-mono font-bold">{evidence.commit_hash}</span>: {evidence.message}
                    </p>
                  )}

                  <pre className="mt-3 text-xs text-slate-300 font-mono whitespace-pre-wrap break-words bg-slate-900/80 p-3.5 rounded-lg border border-slate-800 overflow-x-auto max-h-80">
                    {evidence.code_content ?? evidence.diff ?? `${evidence.caller_id} → ${evidence.callee_id}`}
                  </pre>

                  {(evidence.truncated || evidence.kind === 'git') && (
                    <p className="mt-2 text-xs text-amber-300/80">
                      Excerpt may be incomplete; inspect full source before applying a fix.
                    </p>
                  )}
                </details>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-4 text-center">No repository evidence collected yet.</p>
          )}
        </section>
      )}
    </div>
  );
}
