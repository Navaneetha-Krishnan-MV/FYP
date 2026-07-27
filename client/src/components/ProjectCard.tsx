import { Link } from 'react-router-dom';
import {
  FolderGit2,
  FileCode,
  Cpu,
  Bug,
  ArrowRight,
  RefreshCw,
  CircleAlert,
  CircleCheckBig,
} from 'lucide-react';
import { formatRelative } from '../lib/format';
import type { Project } from '../types';

interface ProjectCardProps {
  project: Project;
  onReindex: (id: string) => void;
  isReindexing?: boolean;
}

function StatusBadge({ status }: { status: Project['status'] }) {
  if (status === 'READY') {
    return (
      <span className="px-3 py-1 text-[11px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5 whitespace-nowrap">
        <CircleCheckBig className="w-3.5 h-3.5" />
        INDEXED &amp; READY
      </span>
    );
  }
  if (status === 'FAILED') {
    return (
      <span className="px-3 py-1 text-[11px] font-bold rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center gap-1.5 whitespace-nowrap">
        <CircleAlert className="w-3.5 h-3.5" />
        FAILED
      </span>
    );
  }
  return (
    <span className="px-3 py-1 text-[11px] font-bold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1.5 whitespace-nowrap">
      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
      {status}
    </span>
  );
}

export function ProjectCard({ project, onReindex, isReindexing = false }: ProjectCardProps) {
  return (
    <div className="glass-panel glass-panel-hover p-6 rounded-2xl border border-indigo-500/15 flex flex-col justify-between group">
      <div>
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-indigo-400 group-hover:border-indigo-500/40 transition shrink-0">
              <FolderGit2 className="w-6 h-6" />
            </div>
            <div className="min-w-0">
              <h3 className="text-lg font-bold text-white group-hover:text-indigo-300 transition truncate">
                {project.name}
              </h3>
              <p className="text-xs text-slate-400 line-clamp-1">
                {project.description || 'No description provided'}
              </p>
            </div>
          </div>
          <StatusBadge status={project.status} />
        </div>

        {project.status === 'FAILED' && project.errorMsg && (
          <p className="mb-4 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/25 text-[11px] font-mono text-rose-300 line-clamp-2 break-words">
            {project.errorMsg}
          </p>
        )}

        {/* Language pills */}
        <div className="flex flex-wrap gap-1.5 mb-5">
          {project.languages && project.languages.length > 0 ? (
            project.languages.map((lang) => (
              <span
                key={lang}
                className="px-2.5 py-0.5 text-[10px] font-semibold rounded-md bg-slate-900/90 text-indigo-300 border border-slate-800"
              >
                {lang}
              </span>
            ))
          ) : (
            <span className="px-2.5 py-0.5 text-[10px] font-semibold rounded-md bg-slate-900/90 text-slate-400 border border-slate-800">
              Multi-Language
            </span>
          )}
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-3 gap-3 p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 mb-5">
          <div className="text-center">
            <div className="text-xs text-slate-400 flex items-center justify-center gap-1 mb-0.5">
              <FileCode className="w-3.5 h-3.5 text-blue-400" />
              Files
            </div>
            <div className="text-base font-extrabold text-white font-mono">
              {(project.fileCount || 0).toLocaleString()}
            </div>
          </div>
          <div className="text-center border-x border-slate-800/80">
            <div className="text-xs text-slate-400 flex items-center justify-center gap-1 mb-0.5">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              Chunks
            </div>
            <div className="text-base font-extrabold text-white font-mono">
              {(project.chunkCount || project._count?.codeChunks || 0).toLocaleString()}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-slate-400 flex items-center justify-center gap-1 mb-0.5">
              <Bug className="w-3.5 h-3.5 text-rose-400" />
              Bugs
            </div>
            <div className="text-base font-extrabold text-white font-mono">
              {(project._count?.bugReports || 0).toLocaleString()}
            </div>
          </div>
        </div>

        <p className="text-[11px] text-slate-500 mb-3">
          Updated {formatRelative(project.updatedAt)}
        </p>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-slate-800/60">
        <button
          onClick={() => onReindex(project.id)}
          disabled={isReindexing}
          className="text-xs font-semibold text-slate-400 hover:text-indigo-400 flex items-center gap-1.5 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isReindexing ? 'animate-spin' : ''}`} />
          {isReindexing ? 'Starting…' : 'Re-Index'}
        </button>

        <Link
          to={`/projects/${project.id}`}
          className="px-4 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white text-xs font-bold transition flex items-center gap-1.5 group-hover:shadow-lg group-hover:shadow-indigo-600/30"
        >
          View Dashboard
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
