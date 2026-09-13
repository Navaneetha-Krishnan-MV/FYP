import type { AGTRCandidate, AGTRWeights, PhaseOutput } from '../types';
import { AGTRWeightsCard } from './AGTRWeightsCard';

interface Props {
  candidates?: AGTRCandidate[];
  weights?: AGTRWeights;
  semanticGap?: number;
  hopsUsed?: number;
  availability?: PhaseOutput['signal_availability'];
  warnings?: string[];
  selectedId?: string;
  rationale?: string;
}

export function AgentAGTRRanking({ candidates = [], weights, semanticGap, hopsUsed,
  availability, warnings = [], selectedId, rationale }: Props) {
  return (
    <section className="space-y-3" aria-label="AGTR candidate ranking">
      <AGTRWeightsCard weights={weights} semanticGap={semanticGap} hopsUsed={hopsUsed} rankingOnly />
      <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 space-y-3">
        <h3 className="text-sm font-bold text-white">AGTR ranked candidates</h3>
        <p className="text-xs text-slate-400">
          Signal columns show raw scores. AGTR combines their min-max normalized values using the weights above.
          Scores prioritize investigation; they are not probabilities of a root cause.
        </p>
        {availability && (
          <p className="text-xs text-slate-300">
            {Object.entries(availability).map(([signal, available]) => `${signal}: ${available ? 'available' : 'unavailable'}`).join(' · ')}
          </p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-400 border-b border-slate-800">
              <tr>{['Rank', 'Candidate', 'Semantic', 'Graph', 'Git', 'AGTR'].map(label => <th key={label} scope="col" className="p-2">{label}</th>)}</tr>
            </thead>
            <tbody>
              {candidates.map(candidate => (
                <tr key={candidate.chunkId} className={`border-b border-slate-800/60 ${candidate.chunkId === selectedId ? 'bg-emerald-500/10' : ''}`}>
                  <td className="p-2 font-mono text-slate-300">{candidate.rank}</td>
                  <td className="p-2">
                    <span className="text-indigo-300 font-mono break-all">{candidate.functionName}</span>
                    <span className="block text-slate-400 break-all">{candidate.filePath}</span>
                    {candidate.chunkId === selectedId && <span className="text-emerald-300">Selected after evidence review</span>}
                  </td>
                  {[candidate.semanticScore, candidate.graphScore, candidate.gitScore, candidate.agtrScore].map((value, i) => (
                    <td key={i} className="p-2 font-mono text-slate-300">{value.toFixed(4)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!candidates.length && <p className="text-xs text-slate-400">No candidates were available to rank.</p>}
        {rationale && <p className="text-sm text-emerald-200 whitespace-pre-wrap">Selection rationale: {rationale}</p>}
        {warnings.length > 0 && <ul className="list-disc pl-4 text-xs text-amber-300 space-y-1">{warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>}
      </div>
    </section>
  );
}
