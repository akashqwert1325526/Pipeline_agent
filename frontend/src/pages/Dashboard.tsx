import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  BarChart3, AlertTriangle, CheckCircle2, RefreshCw, TrendingUp, 
  FileText, Clock, ArrowRight, ShieldCheck, Zap 
} from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { getDashboardStats, DashboardStats } from '../lib/api';
import { categoryChartColors, formatDate, platformLabels } from '../lib/utils';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchStats = () => {
    setLoading(true);
    getDashboardStats()
      .then(r => {
        setStats(r.data);
        setError('');
      })
      .catch(e => {
        setError(e.response?.data?.detail || e.message || 'Failed to load dashboard data');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-400">
        <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
        <p className="text-sm">Connecting to diagnosis telemetry...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-6 text-rose-300">
          <h2 className="text-lg font-bold flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
            Backend Connection Notice
          </h2>
          <p className="text-sm mb-4">{error}</p>
          <button
            onClick={fetchStats}
            className="px-4 py-2 bg-rose-900/60 hover:bg-rose-900 text-rose-200 rounded-lg text-sm transition-colors"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const pieData = Object.entries(stats?.category_distribution || {}).map(([cat, count]) => ({
    name: cat.replace('_', ' '),
    value: count,
    color: categoryChartColors[cat] || '#94a3b8',
  }));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-navy-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">CI/CD Pipeline Overview</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time failure diagnostics, root causes & mitigation insights</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchStats}
            className="p-2 text-slate-400 hover:text-white bg-navy-900 border border-navy-700/70 rounded-lg transition-colors"
            title="Refresh Metrics"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <Link
            to="/analyze"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg shadow-lg shadow-blue-600/20 transition-all"
          >
            <span>Analyze New Log</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { 
            label: 'Total Analyzed Runs', 
            value: stats?.total_analyses ?? 0, 
            icon: FileText, 
            color: 'text-blue-400',
            bg: 'bg-blue-950/20 border-blue-900/40' 
          },
          { 
            label: 'Identified Failures', 
            value: stats?.total_failures ?? 0, 
            icon: AlertTriangle, 
            color: 'text-rose-400',
            bg: 'bg-rose-950/20 border-rose-900/40' 
          },
          { 
            label: 'Recurring Patterns', 
            value: stats?.recurring_failures ?? 0, 
            icon: RefreshCw, 
            color: 'text-amber-400',
            bg: 'bg-amber-950/20 border-amber-900/40' 
          },
          { 
            label: 'Top Failure Type', 
            value: stats?.most_common_category ? stats.most_common_category.replace('_', ' ') : 'None', 
            icon: Zap, 
            color: 'text-violet-400',
            bg: 'bg-violet-950/20 border-violet-900/40' 
          },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className={`border rounded-xl p-5 bg-navy-900/80 border-navy-800 shadow-sm flex flex-col justify-between`}>
            <div className="flex items-center justify-between text-slate-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
              <div className={`p-2 rounded-lg bg-navy-800 ${color}`}>
                <Icon className="w-4 h-4" />
              </div>
            </div>
            <div>
              <p className="text-2xl font-bold text-white tracking-tight">{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Main Charts / Status Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Breakdown Chart */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-6 shadow-md">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-blue-400" />
              <span>Failure Category Distribution</span>
            </h2>
            <span className="text-xs text-slate-500 font-mono">
              {stats?.total_failures ? `${stats.total_failures} Total` : '0 Records'}
            </span>
          </div>

          {pieData.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-slate-500 gap-2">
              <ShieldCheck className="w-10 h-10 stroke-1 opacity-50" />
              <p className="text-sm">No failures recorded yet.</p>
              <Link to="/analyze" className="text-blue-400 text-xs hover:underline">Upload a log to generate metrics</Link>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row items-center gap-4">
              <div className="w-full sm:w-1/2 h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={75}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0d1526',
                        borderColor: '#1e293b',
                        borderRadius: '0.5rem',
                        fontSize: '12px',
                        color: '#f8fafc'
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="w-full sm:w-1/2 space-y-2">
                {pieData.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-slate-300 font-medium">{item.name}</span>
                    </div>
                    <span className="font-mono text-slate-400">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Recent Pipeline Diagnoses */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-6 shadow-md flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-400" />
                <span>Recent Analyses</span>
              </h2>
              <Link to="/history" className="text-xs text-blue-400 hover:text-blue-300 font-medium">
                View all ({stats?.total_analyses ?? 0}) →
              </Link>
            </div>

            {(!stats?.recent_analyses || stats.recent_analyses.length === 0) ? (
              <div className="h-56 flex flex-col items-center justify-center text-slate-500 gap-2">
                <FileText className="w-10 h-10 stroke-1 opacity-50" />
                <p className="text-sm">No analysis history found.</p>
                <Link to="/analyze" className="text-blue-400 text-xs hover:underline">Start your first analysis</Link>
              </div>
            ) : (
              <div className="space-y-2.5">
                {stats.recent_analyses.slice(0, 5).map((item) => (
                  <Link
                    key={item.id}
                    to="/history"
                    className="flex items-center justify-between p-3 rounded-lg bg-navy-950/60 border border-navy-800 hover:border-navy-700 hover:bg-navy-800/50 transition-all group"
                  >
                    <div className="min-w-0 pr-3">
                      <p className="text-sm font-medium text-slate-200 truncate group-hover:text-blue-400 transition-colors">
                        {item.filename || 'Pasted Log'}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                        <span>{platformLabels[item.platform || ''] || 'Generic CI'}</span>
                        <span>•</span>
                        <span>{formatDate(item.created_at)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        item.failure_count > 0 
                          ? 'bg-rose-950/60 text-rose-400 border border-rose-800/40' 
                          : 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40'
                      }`}>
                        {item.failure_count} {item.failure_count === 1 ? 'issue' : 'issues'}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Launch Callout Banner */}
      <div className="bg-gradient-to-r from-blue-950/60 via-indigo-950/40 to-navy-900 border border-blue-900/40 rounded-2xl p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 text-xs font-mono font-medium">ChromaDB Vector Retrieval</span>
            <span className="text-xs text-slate-400">• Continuous Learning Enabled</span>
          </div>
          <h3 className="text-xl font-bold text-white tracking-tight">Got a failing CI/CD workflow?</h3>
          <p className="text-slate-400 text-sm max-w-xl">
            PipelineMedic parses complex stack traces, strips ANSI garbage, classifies failure modes, and matches historical verified fixes in seconds.
          </p>
        </div>
        <Link
          to="/analyze"
          className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-all shadow-lg shadow-blue-600/30 flex-shrink-0"
        >
          Launch Diagnosis
        </Link>
      </div>
    </div>
  );
}
