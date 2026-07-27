import { useCallback, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Layers,
  Search,
  Plus,
  Loader2,
  RefreshCw,
  CircleAlert,
  FolderGit2,
  Bug,
  Cpu,
} from 'lucide-react';
import { ProjectCard } from '../components/ProjectCard';
import { fetchProjects, triggerReindex } from '../services/api';
import { usePolledResource } from '../hooks/usePolledResource';
import { isIndexing } from '../lib/format';
import type { AppOutletContext } from '../layouts/AppLayout';
import type { Project } from '../types';

type StatusFilter = 'ALL' | 'READY' | 'INDEXING' | 'FAILED';

const FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'READY', label: 'Ready' },
  { key: 'INDEXING', label: 'Indexing' },
  { key: 'FAILED', label: 'Failed' },
];

const POLL_INTERVAL_MS = 5000;

export function ProjectsPage() {
  const { dataVersion, openAddProject } = useOutletContext<AppOutletContext>();

  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<StatusFilter>('ALL');
  const [reindexingId, setReindexingId] = useState<string | null>(null);

  // Keep polling while any repository is still moving through the pipeline.
  const { data, error, loading, refresh, setError } = usePolledResource(
    fetchProjects,
    (list: Project[]) => list.some((p) => isIndexing(p.status)),
    POLL_INTERVAL_MS,
    dataVersion,
  );

  const projects = useMemo(() => data ?? [], [data]);

  const handleReindex = useCallback(
    async (projectId: string) => {
      setReindexingId(projectId);
      try {
        await triggerReindex(projectId);
        refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to trigger re-indexing');
      } finally {
        setReindexingId(null);
      }
    },
    [refresh, setError],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return projects.filter((p) => {
      const matchesQuery =
        !q ||
        p.name.toLowerCase().includes(q) ||
        (p.description || '').toLowerCase().includes(q) ||
        (p.repoUrl || '').toLowerCase().includes(q);

      const matchesFilter =
        filter === 'ALL' ||
        (filter === 'READY' && p.status === 'READY') ||
        (filter === 'FAILED' && p.status === 'FAILED') ||
        (filter === 'INDEXING' && isIndexing(p.status));

      return matchesQuery && matchesFilter;
    });
  }, [projects, query, filter]);

  const stats = useMemo(
    () => ({
      total: projects.length,
      ready: projects.filter((p) => p.status === 'READY').length,
      chunks: projects.reduce((sum, p) => sum + (p.chunkCount || 0), 0),
      bugs: projects.reduce((sum, p) => sum + (p._count?.bugReports || 0), 0),
    }),
    [projects],
  );

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <Layers className="w-5 h-5 text-indigo-400" />
            <h1 className="text-2xl font-black text-white tracking-tight">Projects Dashboard</h1>
          </div>
          <p className="mt-1.5 text-sm text-slate-400">
            Every indexed repository, its pipeline state and its filed bug reports.
          </p>
        </div>

        <button
          onClick={() => refresh(true)}
          className="self-start md:self-auto px-3.5 py-2 rounded-xl bg-slate-950/60 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white hover:border-indigo-500/40 transition flex items-center gap-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryTile icon={FolderGit2} label="Repositories" value={stats.total} tone="indigo" />
        <SummaryTile icon={Layers} label="Indexed & Ready" value={stats.ready} tone="emerald" />
        <SummaryTile icon={Cpu} label="Code Chunks" value={stats.chunks} tone="purple" />
        <SummaryTile icon={Bug} label="Bug Reports" value={stats.bugs} tone="rose" />
      </div>

      {/* Search + status filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, description or repository URL…"
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-white text-sm placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>

        <div className="flex gap-1.5 p-1.5 bg-slate-950/60 rounded-xl border border-slate-800/80">
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
                filter === key
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm font-semibold flex items-center gap-2.5">
          <CircleAlert className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
          <p className="text-xs font-semibold uppercase tracking-wide">Loading repositories…</p>
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          hasProjects={projects.length > 0}
          onAddProject={openAddProject}
          onClearFilters={() => {
            setQuery('');
            setFilter('ALL');
          }}
        />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {visible.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onReindex={handleReindex}
              isReindexing={reindexingId === project.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const TONES = {
  indigo: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/25',
  emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25',
  purple: 'text-purple-400 bg-purple-500/10 border-purple-500/25',
  rose: 'text-rose-400 bg-rose-500/10 border-rose-500/25',
};

function SummaryTile({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Layers;
  label: string;
  value: number;
  tone: keyof typeof TONES;
}) {
  return (
    <div className="glass-panel rounded-2xl p-4 border border-slate-800/70 flex items-center gap-3.5">
      <div className={`p-2.5 rounded-xl border ${TONES[tone]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          {label}
        </div>
        <div className="text-xl font-extrabold text-white font-mono">{value.toLocaleString()}</div>
      </div>
    </div>
  );
}

function EmptyState({
  hasProjects,
  onAddProject,
  onClearFilters,
}: {
  hasProjects: boolean;
  onAddProject: () => void;
  onClearFilters: () => void;
}) {
  return (
    <div className="glass-panel rounded-2xl border border-slate-800/70 border-dashed py-20 px-6 flex flex-col items-center text-center gap-4">
      <div className="p-4 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/25">
        <FolderGit2 className="w-8 h-8" />
      </div>
      {hasProjects ? (
        <>
          <div>
            <h3 className="text-lg font-bold text-white">No matching repositories</h3>
            <p className="mt-1 text-sm text-slate-400">Try a different search term or filter.</p>
          </div>
          <button
            onClick={onClearFilters}
            className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-bold text-slate-300 hover:text-white transition"
          >
            Clear filters
          </button>
        </>
      ) : (
        <>
          <div>
            <h3 className="text-lg font-bold text-white">No repositories indexed yet</h3>
            <p className="mt-1 text-sm text-slate-400 max-w-md">
              Ingest a GitHub repository or upload a source ZIP to start the parsing, embedding and
              graph-building pipeline.
            </p>
          </div>
          <button
            onClick={onAddProject}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-extrabold shadow-lg shadow-indigo-600/30 transition flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Ingest Repository
          </button>
        </>
      )}
    </div>
  );
}
