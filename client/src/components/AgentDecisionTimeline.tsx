import { useState } from 'react';
import {
  Brain,
  Search,
  Lightbulb,
  ShieldCheck,
  RotateCcw,
  Flag,
  ChevronDown,
  ChevronRight,
  Wrench,
  FileCode,
  GitBranch,
  Network,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import type { AnalysisResult, PhaseOutput, PhaseAgentTrace } from '../types';

/* ── Phase metadata ────────────────────────────────────────────── */

const PHASE_META: Record<
  string,
  { label: string; icon: typeof Brain; accent: string; bg: string; border: string }
> = {
  understand: {
    label: 'Understand',
    icon: Brain,
    accent: 'text-violet-400',
    bg: 'bg-violet-500/10',
    border: 'border-violet-500/25',
  },
  investigate: {
    label: 'Investigate',
    icon: Search,
    accent: 'text-sky-400',
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/25',
  },
  reason: {
    label: 'Reason',
    icon: Lightbulb,
    accent: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/25',
  },
  verify: {
    label: 'Verify',
    icon: ShieldCheck,
    accent: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/25',
  },
  replan: {
    label: 'Re-plan',
    icon: RotateCcw,
    accent: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/25',
  },
  finalize: {
    label: 'Finalize',
    icon: Flag,
    accent: 'text-indigo-400',
    bg: 'bg-indigo-500/10',
    border: 'border-indigo-500/25',
  },
};

const ROLE_ICON: Record<string, typeof FileCode> = {
  code: FileCode,
  git: GitBranch,
  dependency: Network,
};

const VERDICT_BADGE: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
  supported: { color: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30', icon: CheckCircle2, label: 'Supported' },
  insufficient_evidence: { color: 'text-amber-400 bg-amber-500/15 border-amber-500/30', icon: AlertTriangle, label: 'Insufficient Evidence' },
  contradicted: { color: 'text-rose-400 bg-rose-500/15 border-rose-500/30', icon: XCircle, label: 'Contradicted' },
};

/* ── Helpers ──────────────────────────────────────────────────── */

const ALL_PHASES = ['understand', 'investigate', 'reason', 'verify', 'finalize'] as const;

function inferPendingPhases(completed: PhaseOutput[], currentStage?: string): PhaseOutput[] {
  const seen = new Set(completed.map((p) => `${p.phase}-${p.round ?? 0}`));
  const pending: PhaseOutput[] = [];
  for (const phase of ALL_PHASES) {
    if (!seen.has(`${phase}-0`) && !completed.some((p) => p.phase === phase)) {
      const isActive = currentStage === phase;
      pending.push({ phase, status: isActive ? 'active' : 'pending' });
    }
  }
  return pending;
}

/* ── Main component ──────────────────────────────────────────── */

export function AgentDecisionTimeline({ analysis }: { analysis: AnalysisResult }) {
  const context = analysis.evidenceContext;
  const phaseOutputs = context?.phase_outputs ?? [];
  const isRunning = analysis.status === 'pending' || analysis.status === 'processing';

  // Build timeline: completed phases + pending/active ones
  const pending = isRunning ? inferPendingPhases(phaseOutputs, context?.stage) : [];
  const timeline = [...phaseOutputs, ...pending];

  if (timeline.length === 0) return null;

  return (
    <section className="glass-panel rounded-2xl border border-slate-700/40 p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2.5 rounded-xl bg-gradient-to-br from-violet-500/20 to-indigo-500/20 border border-violet-500/30">
          <Brain className="w-5 h-5 text-violet-400" />
        </div>
        <div>
          <h2 className="text-base font-bold text-white">Agent Decision Timeline</h2>
          <p className="text-xs text-slate-400">
            Each phase's decisions, tool calls, and reasoning trace
          </p>
        </div>
      </div>

      <div className="relative pl-8">
        {/* Vertical timeline connector */}
        <div className="absolute left-[15px] top-0 bottom-0 w-px bg-gradient-to-b from-violet-500/40 via-sky-500/40 via-amber-500/30 to-indigo-500/40" />

        <div className="space-y-4">
          {timeline.map((phase, i) => (
            <PhaseCard key={`${phase.phase}-${phase.round ?? 0}-${i}`} phase={phase} />
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Phase card ──────────────────────────────────────────────── */

function PhaseCard({ phase }: { phase: PhaseOutput }) {
  const [expanded, setExpanded] = useState(phase.status === 'active');
  const meta = PHASE_META[phase.phase] ?? PHASE_META.understand;
  const Icon = meta.icon;
  const isCompleted = phase.status === 'completed';
  const isActive = phase.status === 'active';
  const isPending = phase.status === 'pending';
  const hasContent = isCompleted;

  return (
    <div className="relative">
      {/* Timeline node */}
      <div
        className={`absolute -left-8 top-4 w-[18px] h-[18px] rounded-full border-2 flex items-center justify-center transition-all
          ${isCompleted ? `${meta.border} ${meta.bg}` : ''}
          ${isActive ? 'border-sky-400 bg-sky-500/20 animate-pulse' : ''}
          ${isPending ? 'border-slate-700 bg-slate-900' : ''}`}
      >
        {isCompleted && <div className={`w-2 h-2 rounded-full ${meta.accent.replace('text-', 'bg-')}`} />}
        {isActive && <Loader2 className="w-2.5 h-2.5 text-sky-400 animate-spin" />}
      </div>

      {/* Card */}
      <div
        className={`rounded-xl border transition-all ${
          isPending
            ? 'border-slate-800/60 bg-slate-950/30 opacity-50'
            : isActive
              ? 'border-sky-500/30 bg-sky-500/[0.04] shadow-lg shadow-sky-500/5'
              : `${meta.border} ${meta.bg}`
        }`}
      >
        <button
          onClick={() => hasContent && setExpanded(!expanded)}
          disabled={!hasContent}
          className="w-full flex items-center gap-3 p-4 text-left"
        >
          <div className={`p-2 rounded-lg ${meta.bg} border ${meta.border}`}>
            <Icon className={`w-4 h-4 ${meta.accent}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white">{meta.label}</span>
              {phase.round !== undefined && phase.round > 0 && (
                <span className="text-[10px] font-mono font-bold text-slate-400 px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
                  Round {phase.round}
                </span>
              )}
              {phase.decision && (
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border ${
                  phase.decision === 'supported' || phase.decision === 'supported_hypothesis'
                    ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                    : phase.decision === 'contradicted'
                      ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                      : phase.decision === 'skipped'
                        ? 'text-slate-400 bg-slate-800 border-slate-700'
                        : 'text-slate-300 bg-slate-800/60 border-slate-700/60'
                }`}>
                  {phase.decision.replaceAll('_', ' ')}
                </span>
              )}
              {isActive && (
                <span className="text-[10px] font-bold text-sky-400 animate-pulse">Running…</span>
              )}
            </div>
            {/* Inline preview */}
            {isCompleted && <PhasePreview phase={phase} />}
          </div>
          {hasContent && (
            <span className="text-slate-500">
              {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </span>
          )}
        </button>

        {expanded && hasContent && (
          <div className="px-4 pb-4 pt-0 border-t border-slate-800/50 mt-0">
            <PhaseDetails phase={phase} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Inline preview (collapsed) ──────────────────────────────── */

function PhasePreview({ phase }: { phase: PhaseOutput }) {
  switch (phase.phase) {
    case 'understand':
      return (
        <p className="text-xs text-slate-400 mt-1 line-clamp-1">
          {phase.summary ?? 'Analyzed bug report'}
          {phase.search_terms?.length ? ` · ${phase.search_terms.length} search terms` : ''}
        </p>
      );
    case 'investigate':
      return (
        <p className="text-xs text-slate-400 mt-1">
          {phase.findings?.length ?? 0} findings · {phase.new_evidence_count ?? 0} new evidence pieces
          {phase.agent_traces?.length ? ` · ${phase.agent_traces.length} agent roles` : ''}
        </p>
      );
    case 'reason':
      return (
        <p className="text-xs text-slate-400 mt-1">
          {phase.hypotheses?.length ?? 0} hypotheses generated
          {phase.decision === 'skipped' ? ' · Skipped (no code evidence)' : ''}
        </p>
      );
    case 'verify':
      return (
        <p className="text-xs text-slate-400 mt-1">
          {phase.verdict ? `Verdict: ${phase.verdict.replaceAll('_', ' ')}` : 'Evaluated hypotheses'}
        </p>
      );
    case 'replan':
      return (
        <p className="text-xs text-slate-400 mt-1">
          {phase.tasks?.length ?? 0} follow-up tasks scheduled
        </p>
      );
    case 'finalize':
      return (
        <p className="text-xs text-slate-400 mt-1">
          {phase.termination_reason?.replaceAll('_', ' ') ?? 'Complete'}
          {phase.rounds_used ? ` · ${phase.rounds_used} round(s)` : ''}
        </p>
      );
    default:
      return null;
  }
}

/* ── Expanded detail ─────────────────────────────────────────── */

function PhaseDetails({ phase }: { phase: PhaseOutput }) {
  switch (phase.phase) {
    case 'understand':
      return <UnderstandDetails phase={phase} />;
    case 'investigate':
      return <InvestigateDetails phase={phase} />;
    case 'reason':
      return <ReasonDetails phase={phase} />;
    case 'verify':
      return <VerifyDetails phase={phase} />;
    case 'replan':
      return <ReplanDetails phase={phase} />;
    case 'finalize':
      return <FinalizeDetails phase={phase} />;
    default:
      return null;
  }
}

/* ── Phase-specific detail panels ────────────────────────────── */

function UnderstandDetails({ phase }: { phase: PhaseOutput }) {
  return (
    <div className="space-y-3 pt-3">
      {phase.summary && (
        <div>
          <Label>Bug Summary</Label>
          <p className="text-sm text-slate-200 whitespace-pre-wrap">{phase.summary}</p>
        </div>
      )}
      {phase.search_terms && phase.search_terms.length > 0 && (
        <div>
          <Label>Search Terms Extracted</Label>
          <div className="flex flex-wrap gap-1.5">
            {phase.search_terms.map((term, i) => (
              <span
                key={i}
                className="px-2.5 py-1 text-xs font-mono text-violet-300 bg-violet-500/10 border border-violet-500/25 rounded-lg"
              >
                {term}
              </span>
            ))}
          </div>
        </div>
      )}
      {phase.missing_information && phase.missing_information.length > 0 && (
        <div>
          <Label>Missing Information</Label>
          <ul className="text-xs text-amber-300/80 space-y-1 list-disc pl-4">
            {phase.missing_information.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function InvestigateDetails({ phase }: { phase: PhaseOutput }) {
  return (
    <div className="space-y-4 pt-3">
      {phase.findings && phase.findings.length > 0 && (
        <div>
          <Label>Role Findings</Label>
          <div className="space-y-2">
            {phase.findings.map((f, i) => {
              const RoleIcon = ROLE_ICON[f.role] ?? FileCode;
              return (
                <div key={i} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80">
                  <div className="flex items-center gap-2 mb-1.5">
                    <RoleIcon className="w-3.5 h-3.5 text-sky-400" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-sky-300">{f.role}</span>
                  </div>
                  <p className="text-sm text-slate-300">{f.summary}</p>
                  {f.evidence_ids.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {f.evidence_ids.map((id) => (
                        <a key={id} href={`#${id}`} className="text-[10px] font-mono text-indigo-300 underline decoration-indigo-500/30 hover:text-indigo-200">
                          {id}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
      {phase.agent_traces && phase.agent_traces.length > 0 && (
        <div>
          <Label>Agent Tool Traces</Label>
          <div className="space-y-2">
            {phase.agent_traces.map((trace, i) => (
              <AgentTraceCard key={i} trace={trace} />
            ))}
          </div>
        </div>
      )}
      {phase.new_evidence_count !== undefined && (
        <p className="text-xs text-slate-500">
          +{phase.new_evidence_count} new evidence pieces collected this round
        </p>
      )}
    </div>
  );
}

function AgentTraceCard({ trace }: { trace: PhaseAgentTrace }) {
  const [expanded, setExpanded] = useState(false);
  const RoleIcon = ROLE_ICON[trace.role] ?? FileCode;
  return (
    <div className="rounded-lg border border-slate-800/60 bg-slate-950/40 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-2.5 text-left hover:bg-slate-900/40 transition"
      >
        <RoleIcon className="w-3.5 h-3.5 text-sky-400 shrink-0" />
        <span className="text-[11px] font-bold uppercase text-sky-300">{trace.role}</span>
        <span className="text-xs text-slate-400 truncate flex-1">{trace.question}</span>
        <span className="text-[10px] text-slate-500 font-mono shrink-0">{trace.trace.length} steps</span>
        {expanded ? <ChevronDown className="w-3 h-3 text-slate-500" /> : <ChevronRight className="w-3 h-3 text-slate-500" />}
      </button>
      {expanded && (
        <div className="px-3 pb-3 space-y-1.5">
          {trace.trace.map((step, j) => (
            <div
              key={j}
              className={`flex items-start gap-2 p-2 rounded-md text-xs ${
                step.action === 'finish' ? 'bg-emerald-500/5 border border-emerald-500/20' : 'bg-slate-900/50'
              }`}
            >
              <span className="shrink-0 w-5 h-5 rounded bg-slate-800 text-slate-400 text-[10px] font-mono font-bold flex items-center justify-center">
                {step.step}
              </span>
              {step.action === 'tool' ? (
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <Wrench className="w-3 h-3 text-slate-400" />
                    <span className="font-mono font-bold text-indigo-300">{step.tool}</span>
                    <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                      step.status === 'ok' ? 'text-emerald-400 bg-emerald-500/10' :
                      step.status === 'empty' ? 'text-amber-400 bg-amber-500/10' :
                      'text-slate-400 bg-slate-800'
                    }`}>
                      {step.status}
                    </span>
                  </div>
                  {step.arguments && (
                    <pre className="mt-1 text-[10px] text-slate-500 font-mono truncate max-w-full">
                      {JSON.stringify(step.arguments)}
                    </pre>
                  )}
                </div>
              ) : (
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    <span className="font-bold text-emerald-300">Finish</span>
                  </div>
                  {step.summary && <p className="mt-1 text-slate-300">{step.summary}</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ReasonDetails({ phase }: { phase: PhaseOutput }) {
  if (phase.decision === 'skipped') {
    return (
      <div className="pt-3">
        <p className="text-sm text-slate-400">
          Reasoning skipped — no code evidence was available to formulate hypotheses.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-3 pt-3">
      {phase.hypotheses && phase.hypotheses.length > 0 && (
        <div className="space-y-2">
          {phase.hypotheses.map((h, i) => (
            <div key={i} className="p-3 rounded-lg bg-slate-950/60 border border-amber-500/20">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-lg bg-amber-500/15 text-amber-300 text-[11px] font-mono font-bold flex items-center justify-center border border-amber-500/30">
                  H{i + 1}
                </span>
                <span className="text-xs font-mono text-indigo-300 break-all">{h.candidate_id}</span>
              </div>
              <p className="text-sm text-slate-200 mb-2">{h.mechanism}</p>
              {h.suggested_fix && (
                <div className="mb-2">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Suggested Fix</span>
                  <p className="text-xs text-slate-300 mt-0.5">{h.suggested_fix}</p>
                </div>
              )}
              {h.assumptions.length > 0 && (
                <div className="mb-2">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Assumptions</span>
                  <ul className="text-xs text-amber-300/70 list-disc pl-4 mt-0.5">
                    {h.assumptions.map((a, j) => <li key={j}>{a}</li>)}
                  </ul>
                </div>
              )}
              <div className="flex flex-wrap gap-1.5">
                {h.evidence_ids.map((id) => (
                  <a key={id} href={`#${id}`} className="text-[10px] font-mono text-emerald-300 underline decoration-emerald-500/30">
                    {id}
                  </a>
                ))}
                {h.counterevidence_ids?.map((id) => (
                  <a key={id} href={`#${id}`} className="text-[10px] font-mono text-rose-300 underline decoration-rose-500/30 line-through">
                    {id}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {phase.missing_information && phase.missing_information.length > 0 && (
        <div>
          <Label>Still Missing</Label>
          <ul className="text-xs text-amber-300/80 list-disc pl-4">
            {phase.missing_information.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function VerifyDetails({ phase }: { phase: PhaseOutput }) {
  const badge = VERDICT_BADGE[phase.verdict ?? ''];
  const VIcon = badge?.icon ?? AlertTriangle;
  return (
    <div className="space-y-3 pt-3">
      {badge && (
        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border ${badge.color}`}>
          <VIcon className="w-4 h-4" />
          <span className="text-sm font-bold">{badge.label}</span>
        </div>
      )}
      {phase.primary_candidate_id && (
        <p className="text-xs font-mono text-indigo-300">
          Primary candidate: {phase.primary_candidate_id}
        </p>
      )}
      {phase.explanation && (
        <p className="text-sm text-slate-200 whitespace-pre-wrap">{phase.explanation}</p>
      )}
      {phase.evidence_ids && phase.evidence_ids.length > 0 && (
        <div>
          <Label>Cited Evidence</Label>
          <div className="flex flex-wrap gap-1.5">
            {phase.evidence_ids.map((id) => (
              <a key={id} href={`#${id}`} className="text-[10px] font-mono text-indigo-300 underline decoration-indigo-500/30">
                {id}
              </a>
            ))}
          </div>
        </div>
      )}
      {phase.follow_up && phase.follow_up.length > 0 && (
        <div>
          <Label>Follow-up Questions</Label>
          <ul className="space-y-1">
            {phase.follow_up.map((f, i) => (
              <li key={i} className="text-xs text-slate-300">
                <span className="font-bold text-orange-300 uppercase">{f.role}</span>{' '}
                {f.question}
              </li>
            ))}
          </ul>
        </div>
      )}
      {phase.limitations && phase.limitations.length > 0 && (
        <div>
          <Label>Limitations</Label>
          <ul className="text-xs text-slate-400 list-disc pl-4">
            {phase.limitations.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function ReplanDetails({ phase }: { phase: PhaseOutput }) {
  return (
    <div className="space-y-2 pt-3">
      <Label>Tasks Scheduled for Next Round</Label>
      {phase.tasks?.map((t, i) => {
        const RoleIcon = ROLE_ICON[t.role] ?? FileCode;
        return (
          <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-950/50 border border-orange-500/15">
            <RoleIcon className="w-3.5 h-3.5 text-orange-400 mt-0.5 shrink-0" />
            <div>
              <span className="text-[10px] font-bold uppercase text-orange-300">{t.role}</span>
              <p className="text-xs text-slate-300 mt-0.5">{t.question}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FinalizeDetails({ phase }: { phase: PhaseOutput }) {
  return (
    <div className="space-y-2 pt-3">
      <div className="flex flex-wrap gap-3 text-xs">
        {phase.termination_reason && (
          <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
            <span className="text-[10px] font-bold uppercase text-slate-500 block">Termination</span>
            <span className="text-slate-200 font-semibold">{phase.termination_reason.replaceAll('_', ' ')}</span>
          </div>
        )}
        {phase.rounds_used !== undefined && (
          <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
            <span className="text-[10px] font-bold uppercase text-slate-500 block">Rounds Used</span>
            <span className="text-slate-200 font-semibold">{phase.rounds_used}</span>
          </div>
        )}
        {phase.decision && (
          <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
            <span className="text-[10px] font-bold uppercase text-slate-500 block">Outcome</span>
            <span className={`font-semibold ${phase.decision === 'supported_hypothesis' ? 'text-emerald-300' : 'text-amber-300'}`}>
              {phase.decision.replaceAll('_', ' ')}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Primitives ──────────────────────────────────────────────── */

function Label({ children }: { children: string }) {
  return (
    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
      {children}
    </div>
  );
}
