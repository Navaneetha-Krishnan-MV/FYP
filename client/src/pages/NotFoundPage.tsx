import { Link } from 'react-router-dom';
import { Compass, ArrowLeft } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="glass-panel rounded-2xl border border-slate-800/70 py-24 px-6 flex flex-col items-center text-center gap-5">
      <div className="p-4 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/25">
        <Compass className="w-8 h-8" />
      </div>
      <div>
        <div className="text-5xl font-black font-mono text-white">404</div>
        <h1 className="mt-2 text-lg font-bold text-white">This route does not exist</h1>
        <p className="mt-1 text-sm text-slate-400 max-w-sm">
          The page you were looking for is not part of the CodeLens workspace.
        </p>
      </div>
      <Link
        to="/projects"
        className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-extrabold shadow-lg shadow-indigo-600/30 transition flex items-center gap-2"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Projects Dashboard
      </Link>
    </div>
  );
}
