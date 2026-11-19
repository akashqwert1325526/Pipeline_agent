import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, Upload, History, BarChart3, Github, 
  Activity, ShieldAlert, Cpu
} from 'lucide-react';
import { cn } from '../lib/utils';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/analyze', icon: Upload, label: 'Analyze Logs' },
  { to: '/history', icon: History, label: 'Failure History' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/github', icon: Github, label: 'GitHub CI' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-navy-950 font-sans">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 bg-navy-900 border-r border-navy-700/60 flex flex-col justify-between">
        <div>
          {/* Brand header */}
          <div className="p-5 border-b border-navy-700/50 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-white tracking-tight text-base">PipelineMedic</span>
                <span className="px-1.5 py-0.2 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded text-[10px] font-mono font-semibold">v1.0</span>
              </div>
              <p className="text-slate-400 text-xs mt-0.5">CI/CD Failure Diagnosis</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="p-3 space-y-1">
            {navItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) => cn(
                  'flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all group',
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-sm shadow-blue-500/10'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-navy-800/60'
                )}
              >
                <Icon className="w-4 h-4 transition-transform group-hover:scale-110" />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Footer status pill */}
        <div className="p-4 border-t border-navy-700/50 bg-navy-950/40">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Agent Online</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-slate-500 font-mono">
              <Cpu className="w-3 h-3 text-slate-400" />
              <span>ChromaDB</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main View Area */}
      <main className="flex-1 overflow-y-auto bg-gradient-to-b from-navy-950 via-navy-900/60 to-navy-950">
        {children}
      </main>
    </div>
  );
}
