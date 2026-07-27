import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Cpu, Layers, Plus, LogOut, ChevronDown } from 'lucide-react';
import { fetchHealth } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import type { HealthStatus } from '../types';

interface AppShellProps {
  children: ReactNode;
  onOpenAddProject: () => void;
}

const HEALTH_POLL_MS = 30000;

export function AppShell({ children, onOpenAddProject }: AppShellProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    const ping = () => {
      fetchHealth()
        .then((data) => {
          if (!cancelled) setHealth(data);
        })
        .catch(() => {
          if (!cancelled) setHealth({ status: 'offline', service: 'Backend Server' });
        });
    };

    ping();
    const id = window.setInterval(ping, HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  // Close the account menu on any outside click.
  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [menuOpen]);

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate('/login', { replace: true });
  };

  const online = health?.status === 'online';

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Top navigation */}
      <header className="sticky top-0 z-40 glass-panel border-b border-indigo-500/20 px-4 sm:px-6 py-3.5 flex items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-8 min-w-0">
          <Link to="/projects" className="flex items-center gap-3 group shrink-0">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/30 group-hover:scale-105 transition-transform">
              <Cpu className="w-6 h-6" />
            </div>
            <div className="hidden sm:block">
              <div className="flex items-center gap-2">
                <span className="text-xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-100 to-indigo-300">
                  CodeLens AI
                </span>
                <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-widest rounded-md bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                  AGTR v1.0
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-400">
                Adaptive Graph-Temporal Bug Localization
              </p>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1.5 bg-slate-950/60 p-1.5 rounded-xl border border-slate-800/80">
            <NavLink
              to="/projects"
              className={({ isActive }) =>
                `px-4 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
                }`
              }
            >
              <Layers className="w-4 h-4" />
              Projects Dashboard
            </NavLink>
          </nav>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950/70 border border-slate-800/80 text-xs">
            <span
              className={`w-2.5 h-2.5 rounded-full ${online ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`}
            />
            <span className="text-slate-300 font-mono text-[11px]">
              {online ? 'Core Engine Online' : 'Backend Offline'}
            </span>
          </div>

          <button
            onClick={onOpenAddProject}
            className="px-3 sm:px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-extrabold tracking-wide shadow-lg shadow-indigo-600/30 hover:scale-[1.02] transition active:scale-95 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Ingest Repository</span>
          </button>

          {/* Account menu */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="flex items-center gap-2 pl-1.5 pr-2.5 py-1.5 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-indigo-500/40 transition"
            >
              <img
                src={user?.avatarUrl}
                alt=""
                className="w-7 h-7 rounded-lg bg-slate-900 border border-slate-800"
              />
              <span className="hidden lg:block text-xs font-bold text-slate-200 max-w-[9rem] truncate">
                {user?.name}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            </button>

            {menuOpen && (
              <div
                role="menu"
                className="absolute right-0 mt-2 w-60 rounded-xl glass-panel border border-slate-800 shadow-2xl overflow-hidden"
              >
                <div className="px-4 py-3 border-b border-slate-800/80">
                  <div className="text-sm font-bold text-white truncate">{user?.name}</div>
                  <div className="text-[11px] text-slate-400 truncate">{user?.email}</div>
                </div>
                <button
                  onClick={handleLogout}
                  role="menuitem"
                  className="w-full px-4 py-3 text-left text-xs font-bold text-slate-300 hover:text-white hover:bg-slate-900/70 transition flex items-center gap-2.5"
                >
                  <LogOut className="w-4 h-4" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">{children}</main>
    </div>
  );
}
