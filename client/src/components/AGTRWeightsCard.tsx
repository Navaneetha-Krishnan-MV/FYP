import { Activity, Sparkles } from 'lucide-react';
import { CONFIDENCE_STYLES } from '../lib/format';
import type { AGTRWeights } from '../types';

interface AGTRWeightsCardProps {
  weights?: AGTRWeights;
  semanticGap?: number;
  confidence?: string;
  confidenceValue?: number;
  hopsUsed?: number;
  rankingOnly?: boolean;
}

const SIGNALS = [
  {
    key: 'ws' as const,
    label: 'Semantic Embedding Weight (w_s)',
    dot: 'bg-indigo-500',
    text: 'text-indigo-300',
    bar: 'from-indigo-500 to-blue-400',
  },
  {
    key: 'wg' as const,
    label: 'Structural Neo4j Graph Weight (w_g)',
    dot: 'bg-purple-500',
    text: 'text-purple-300',
    bar: 'from-purple-500 to-pink-400',
  },
  {
    key: 'wt' as const,
    label: 'Temporal Git Commit Decay Weight (w_t)',
    dot: 'bg-emerald-500',
    text: 'text-emerald-300',
    bar: 'from-emerald-500 to-teal-400',
  },
];

/**
 * Renders the dynamic (w_s, w_g, w_t) split that AGTR derives from the retrieval
 * confidence gap C. Values come straight from the analysis record — nothing is
 * substituted when the pipeline did not report them.
 */
export function AGTRWeightsCard({
  weights,
  semanticGap,
  confidence,
  confidenceValue,
  hopsUsed,
  rankingOnly = false,
}: AGTRWeightsCardProps) {
  const confidenceStyle =
    (confidence && CONFIDENCE_STYLES[confidence]) ||
    'bg-indigo-500/10 text-indigo-400 border-indigo-500/30';

  return (
    <div className="glass-panel p-6 rounded-2xl border border-indigo-500/20 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/15 text-purple-400 border border-purple-500/30">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">AGTR Dynamic Multi-Signal Weights</h3>
            <p className="text-xs text-slate-400">Adaptive Graph-Temporal Ranking formula output</p>
          </div>
        </div>

        {!rankingOnly && <span className={`px-3 py-1 text-xs font-bold rounded-full border ${confidenceStyle}`}>
          {confidence || 'UNKNOWN'} CONFIDENCE
          {confidenceValue != null && ` (${Math.round(confidenceValue * 100)}%)`}
        </span>}
      </div>

      {/* Confidence gap meter */}
      <div className="mb-6 bg-slate-950/50 p-4 rounded-xl border border-slate-800/80 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
          <div>
            <div className="text-xs font-semibold text-slate-300">{rankingOnly ? 'Semantic Seed Gap (C)' : 'Retrieval Confidence Gap (C)'}</div>
            <div className="text-[11px] text-slate-400">
              Separation between the top candidate and the rest
            </div>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-xl font-extrabold text-white font-mono">
            {semanticGap != null ? semanticGap.toFixed(4) : '—'}
          </div>
          <div className="text-[10px] text-indigo-400 font-bold uppercase">
            {hopsUsed != null ? `${hopsUsed}-Hop Traversal` : 'Hops not reported'}
          </div>
        </div>
      </div>

      {/* Dynamic weight bars */}
      {weights ? (
        <div className="space-y-4">
          {SIGNALS.map(({ key, label, dot, text, bar }) => {
            const value = weights[key] ?? 0;
            const pct = Math.round(value * 100);
            return (
              <div key={key}>
                <div className="flex justify-between text-xs font-semibold mb-1.5 gap-3">
                  <span className={`${text} flex items-center gap-1.5`}>
                    <span className={`w-2.5 h-2.5 rounded-full ${dot} shrink-0`} />
                    {label}
                  </span>
                  <span className="text-white font-mono whitespace-nowrap">
                    {pct}% ({value.toFixed(3)})
                  </span>
                </div>
                <div className="w-full h-2.5 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className={`h-full bg-gradient-to-r ${bar} rounded-full transition-all duration-700`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-slate-500 italic">
          The pipeline did not report AGTR weights for this run.
        </p>
      )}
    </div>
  );
}
