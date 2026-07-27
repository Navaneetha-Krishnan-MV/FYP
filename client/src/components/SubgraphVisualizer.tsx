import { Network, FileCode, ShieldAlert, GitCommitVertical, ArrowRight, Code } from 'lucide-react';
import { fileName } from '../lib/format';

interface SubgraphVisualizerProps {
  rootCauseFile?: string;
  rootCauseFunction?: string;
  /** `"caller -> callee -> callee"` chains produced by the Neo4j hop expansion. */
  dependencyPaths?: string[];
  gitCommit?: string;
  hopsUsed?: number;
}

const MAX_CHAINS = 5;

/**
 * Draws the expanded dependency subgraph AGTR traversed. Every node shown comes
 * from `evidenceContext.dependency_paths` — no placeholder neighbours are invented.
 */
export function SubgraphVisualizer({
  rootCauseFile,
  rootCauseFunction,
  dependencyPaths = [],
  gitCommit,
  hopsUsed,
}: SubgraphVisualizerProps) {
  const chains = dependencyPaths
    .map((path) => path.split('->').map((node) => node.trim()).filter(Boolean))
    .filter((nodes) => nodes.length > 0)
    .slice(0, MAX_CHAINS);

  const hasCommit = Boolean(gitCommit) && gitCommit !== 'N/A';

  return (
    <div className="glass-panel p-6 rounded-2xl border border-indigo-500/20 shadow-2xl relative overflow-hidden">
      {/* Cyber grid accent */}
      <div className="absolute inset-0 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:16px_16px] opacity-10 pointer-events-none" />

      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 relative z-10">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
            <Network className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white tracking-wide">AGTR Subgraph Evidence</h3>
            <p className="text-xs text-slate-400">
              Dependency chains expanded from the semantic seed set
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hopsUsed !== undefined && (
            <span className="px-3 py-1 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
              {hopsUsed}-Hop Traversal
            </span>
          )}
          <span className="px-3 py-1 text-xs font-semibold rounded-full bg-slate-900 text-slate-300 border border-slate-800">
            {chains.length} chain{chains.length === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      {/* Focal root-cause node */}
      <div className="relative z-10 rounded-xl bg-slate-950/60 border border-slate-800/80 p-6 flex flex-wrap items-center justify-center gap-4">
        <NodeCard
          icon={FileCode}
          kind="File Node"
          name={fileName(rootCauseFile)}
          title={rootCauseFile}
          accent="border-blue-500/40 text-blue-300"
        />

        <ArrowRight className="w-5 h-5 text-slate-600 shrink-0" />

        <div className="px-5 py-4 rounded-2xl bg-slate-900/95 border-2 border-emerald-400 shadow-[0_0_30px_rgba(16,185,129,0.25)] flex items-center gap-3 relative">
          <div className="absolute -top-3 -right-3 px-2 py-0.5 bg-emerald-500 text-slate-950 font-black text-[10px] rounded-full uppercase tracking-wider shadow">
            Root Cause
          </div>
          <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
              Target Function
            </div>
            <div className="text-base font-extrabold text-white font-mono break-all">
              {rootCauseFunction ? `${rootCauseFunction}()` : 'not reported'}
            </div>
          </div>
        </div>

        {hasCommit && (
          <>
            <ArrowRight className="w-5 h-5 text-slate-600 shrink-0 rotate-180" />
            <NodeCard
              icon={GitCommitVertical}
              kind="Modified By"
              name={gitCommit as string}
              accent="border-purple-500/40 text-purple-300"
            />
          </>
        )}
      </div>

      {/* Traversed chains */}
      <div className="mt-5 relative z-10">
        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-2.5">
          <Code className="w-3.5 h-3.5 text-indigo-400" />
          Traversed dependency chains
        </div>

        {chains.length === 0 ? (
          <p className="text-xs text-slate-500 italic">
            No multi-hop chains were recorded — the root cause was a direct semantic hit.
          </p>
        ) : (
          <div className="space-y-2">
            {chains.map((nodes, chainIdx) => (
              <div
                key={`chain-${chainIdx}`}
                className="flex items-center gap-2 flex-wrap px-3.5 py-2.5 rounded-xl bg-slate-950/50 border border-slate-800/70"
              >
                {nodes.map((node, nodeIdx) => (
                  <span key={`${chainIdx}-${nodeIdx}`} className="flex items-center gap-2">
                    {nodeIdx > 0 && <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />}
                    <span
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-mono border ${
                        node === rootCauseFunction
                          ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/35 font-bold'
                          : 'bg-slate-900 text-slate-300 border-slate-800'
                      }`}
                    >
                      {node}
                    </span>
                  </span>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function NodeCard({
  icon: Icon,
  kind,
  name,
  title,
  accent,
}: {
  icon: typeof FileCode;
  kind: string;
  name: string;
  title?: string;
  accent: string;
}) {
  return (
    <div
      className={`px-4 py-3 rounded-xl bg-slate-900/90 border shadow-lg flex items-center gap-3 ${accent}`}
      title={title}
    >
      <Icon className="w-5 h-5 shrink-0" />
      <div className="min-w-0">
        <div className="text-xs font-semibold">{kind}</div>
        <div className="text-sm font-bold text-white font-mono break-all">{name}</div>
      </div>
    </div>
  );
}
