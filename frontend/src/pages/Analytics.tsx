import React, { useEffect, useState } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  LineChart, Line, CartesianGrid, Cell
} from 'recharts';
import { 
  TrendingUp, Zap, CheckCircle2, AlertTriangle, RefreshCw, 
  BarChart3, Activity, Layers, HelpCircle
} from 'lucide-react';
import { getAnalyticsTrends, AnalyticsTrends } from '../lib/api';
import { categoryChartColors } from '../lib/utils';

export default function Analytics() {
  const [data, setData] = useState<AnalyticsTrends | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchTrends = () => {
    setLoading(true);
    getAnalyticsTrends()
      .then((r) => setData(r.data))
      .catch((e) => console.error('Trends error:', e))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTrends();
  }, []);

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-400 gap-3">
        <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
        <p className="text-sm">Calculating failure trends & vector memory insights...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-center text-slate-400">
        <p>Telemetry metrics unavailable. Please verify backend connection.</p>
      </div>
    );
  }

  const tooltipStyle = {
    backgroundColor: '#0d1526',
    borderColor: '#1e293b',
    borderRadius: '0.5rem',
    fontSize: '12px',
    color: '#f8fafc',
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-navy-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Failure Analytics & Trends</h1>
          <p className="text-slate-400 text-sm mt-1">Telemetry queries analyzing recurring failure patterns, flaky tests & resolution efficacy</p>
        </div>
        <button
          onClick={fetchTrends}
          className="p-2 text-slate-400 hover:text-white bg-navy-900 border border-navy-700/70 rounded-lg transition-colors w-fit"
          title="Refresh Telemetry"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Top Telemetry KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Fix Confirmation Rate</span>
            <div className="p-2 rounded-lg bg-emerald-950/40 text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold text-white font-mono">
            {Math.round(data.fix_success_rate * 100)}%
          </p>
          <p className="text-xs text-slate-500 mt-1">Verified resolutions by developers</p>
        </div>

        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Flaky Test Indicators</span>
            <div className="p-2 rounded-lg bg-amber-950/40 text-amber-400">
              <Zap className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold text-white font-mono">{data.flaky_test_count}</p>
          <p className="text-xs text-slate-500 mt-1">Intermittent / timing-dependent failures</p>
        </div>

        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Distinct Failure Categories</span>
            <div className="p-2 rounded-lg bg-blue-950/40 text-blue-400">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <p className="text-3xl font-bold text-white font-mono">{data.category_trends.length}</p>
          <p className="text-xs text-slate-500 mt-1">Active categories detected in logs</p>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Failures by Day Line Chart */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-6 shadow-md">
          <h2 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-blue-400" />
            <span>Failure Frequency Over Time (30 Days)</span>
          </h2>
          <p className="text-xs text-slate-400 mb-4">Historical daily failure volume recorded</p>

          {data.failures_by_day.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-slate-500 text-xs">
              No historical daily data available yet.
            </div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.failures_by_day}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1b2850" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line 
                    type="monotone" 
                    dataKey="count" 
                    stroke="#3b82f6" 
                    strokeWidth={2}
                    dot={{ fill: '#3b82f6', r: 3 }}
                    activeDot={{ r: 5, fill: '#60a5fa' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Category Breakdown Bar Chart */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-6 shadow-md">
          <h2 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-violet-400" />
            <span>Failure Mode Breakdown</span>
          </h2>
          <p className="text-xs text-slate-400 mb-4">Aggregated failure count by category</p>

          {data.category_trends.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-slate-500 text-xs">
              No category trends available yet.
            </div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.category_trends} layout="vertical" margin={{ left: 10, right: 10 }}>
                  <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} allowDecimals={false} />
                  <YAxis 
                    dataKey="category" 
                    type="category" 
                    tick={{ fill: '#94a3b8', fontSize: 10 }} 
                    width={110}
                    tickFormatter={(val) => val.replace('_', ' ')}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {data.category_trends.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={categoryChartColors[entry.category] || '#3b82f6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Top Recurring Errors List */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-6 shadow-md">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <span>Top Recurring Error Signatures</span>
          </h2>
          <span className="text-xs text-slate-500 font-mono">Top 10 Patterns</span>
        </div>
        <p className="text-xs text-slate-400 mb-4">Ranked by frequency of occurrence across all analyzed logs</p>

        {data.top_errors.length === 0 ? (
          <div className="py-8 text-center text-slate-500 text-xs">
            No recurring error signatures indexed yet.
          </div>
        ) : (
          <div className="space-y-2">
            {data.top_errors.map((item, i) => (
              <div 
                key={i} 
                className="flex items-center justify-between p-3 rounded-lg bg-navy-950/60 border border-navy-800 hover:border-navy-700 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0 pr-4">
                  <span className="w-5 text-right font-mono text-xs font-bold text-slate-500">#{i + 1}</span>
                  <span className="text-xs font-mono text-rose-300 truncate">{item.error_message}</span>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <span className="font-mono text-xs font-bold text-white bg-navy-800 px-2 py-0.5 rounded border border-navy-700">
                    {item.count} {item.count === 1 ? 'occurrence' : 'occurrences'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
