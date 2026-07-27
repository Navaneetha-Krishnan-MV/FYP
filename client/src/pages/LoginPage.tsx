import { useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Cpu, Lock, Mail, ArrowRight, Network, GitBranch, Sparkles, Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const DEMO_EMAIL = 'demo@codelens.ai';
const DEMO_PASSWORD = 'codelens';

const HIGHLIGHTS = [
  {
    icon: Sparkles,
    title: 'Semantic Retrieval',
    body: 'Jina code embeddings (768-dim) searched over pgvector to seed candidates.',
  },
  {
    icon: Network,
    title: 'Adaptive Graph Expansion',
    body: 'Neo4j traversal with a hop count chosen from retrieval confidence.',
  },
  {
    icon: GitBranch,
    title: 'Temporal Git Decay',
    body: 'Recent commits touching a file raise its suspiciousness score.',
  },
];

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = (location.state as { from?: string } | null)?.from || '/projects';

  if (isAuthenticated) return <Navigate to={redirectTo} replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await login(email, password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Brand / product panel */}
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-slate-800/70">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/30">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xl font-black tracking-tight text-white">CodeLens AI</div>
            <p className="text-[11px] text-slate-400 font-medium">
              Adaptive Graph-Temporal Bug Localization
            </p>
          </div>
        </div>

        <div className="space-y-8 max-w-md">
          <div>
            <h1 className="text-4xl font-black leading-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-200 to-indigo-300">
              Point a bug report at a repository. Get the function that caused it.
            </h1>
            <p className="mt-4 text-sm text-slate-400 leading-relaxed">
              CodeLens combines semantic search, structural graph traversal and git history
              into a single AGTR ranking, then grounds a Gemini explanation on that evidence.
            </p>
          </div>

          <div className="space-y-4">
            {HIGHLIGHTS.map(({ icon: Icon, title, body }) => (
              <div key={title} className="flex gap-3.5">
                <div className="mt-0.5 p-2 h-fit rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/25">
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-100">{title}</div>
                  <div className="text-xs text-slate-400 leading-relaxed">{body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-[11px] text-slate-600 font-mono">
          pgvector · Neo4j · Gemini 2.5 · FastAPI · Express · Prisma
        </p>
      </div>

      {/* Sign-in form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white">
              <Cpu className="w-6 h-6" />
            </div>
            <span className="text-xl font-black text-white">CodeLens AI</span>
          </div>

          <h2 className="text-2xl font-bold text-white">Sign in</h2>
          <p className="mt-1.5 text-xs text-slate-400">
            Access your indexed repositories and AGTR localization reports.
          </p>

          {error && (
            <div
              role="alert"
              className="mt-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-semibold"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-slate-300 mb-1.5">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-sm font-bold shadow-lg shadow-indigo-600/30 transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                <>
                  Enter Workspace
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 p-3.5 rounded-xl bg-slate-950/50 border border-slate-800/80">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Demo access
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              This build has no auth service — the API resolves every request to a single default
              user. Any valid email with a 4+ character password opens the workspace.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
