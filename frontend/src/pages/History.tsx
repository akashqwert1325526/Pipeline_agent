import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Search, RefreshCw, ChevronDown, ChevronUp, Filter, 
  Calendar, Layers, FileText, CheckCircle2, AlertTriangle, ArrowRight
} from 'lucide-react';
import { getAnalyses, AnalysisSummary } from '../lib/api';
import DiagnosisCardComponent from '../components/DiagnosisCard';
import { formatDate, platformLabels, cn } from '../lib/utils';

export default function History() {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [platformFilter, setPlatformFilter] = useState('ALL');
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchHistory = () => {
    setLoading(true);
    getAnalyses(0, 100)
      .then((r) => setAnalyses(r.data))
      .catch((e) => console.error('History fetch error:', e))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const filtered = analyses.filter((a) => {
    const matchesSearch = !search || 
      a.filename?.toLowerCase().includes(search.toLowerCase()) ||
      a.platform?.toLowerCase().includes(search.toLowerCase()) ||
      a.diagnoses?.some((d) => d.error_message?.toLowerCase().includes(search.toLowerCase()));

    const matchesPlatform = platformFilter === 'ALL' || a.platform === platformFilter;

    return matchesSearch && matchesPlatform;
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-navy-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Failure Diagnosis Archive</h1>
          <p className="text-slate-400 text-sm mt-1">Review, search and filter previous investigation reports</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchHistory}
            className="p-2 text-slate-400 hover:text-white bg-navy-900 border border-navy-700/70 rounded-lg transition-colors"
            title="Reload Archive"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
          <Link
            to="/analyze"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-all shadow-md shadow-blue-600/20"
          >
            New Analysis
          </Link>
        </div>
      </div>

      {/* Controls: Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search logs by filename, error signature, or platform..."
            className="w-full pl-10 pr-4 py-2.5 bg-navy-900 border border-navy-700/80 rounded-xl text-sm text-slate-200 outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-500" />
          <select
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
            className="bg-navy-900 border border-navy-700/80 rounded-xl px-3 py-2.5 text-xs text-slate-300 outline-none focus:border-blue-500"
          >
            <option value="ALL">All Platforms</option>
            <option value="github_actions">GitHub Actions</option>
            <option value="jenkins">Jenkins</option>
            <option value="gitlab">GitLab CI/CD</option>
            <option value="generic">Generic CI</option>
          </select>
        </div>
      </div>

      {/* Analysis List */}
      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center text-slate-400 gap-3">
          <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
          <p className="text-sm">Fetching historical reports...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-24 bg-navy-900/40 border border-navy-800 rounded-2xl text-slate-500 space-y-3">
          <FileText className="w-12 h-12 stroke-1 mx-auto text-slate-600" />
          <p className="text-base font-medium text-slate-300">No matching pipeline analyses found.</p>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {search || platformFilter !== 'ALL' 
              ? 'Try adjusting your search criteria or resetting the platform filter.' 
              : 'Analyze your first log to start tracking failure trends.'}
          </p>
          <Link
            to="/analyze"
            className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-semibold mt-2"
          >
            <span>Analyze a pipeline log now</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => {
            const isItemExpanded = expanded === item.id;
            return (
              <div
                key={item.id}
                className="bg-navy-900 border border-navy-800/80 rounded-xl overflow-hidden shadow-sm transition-all hover:border-navy-700"
              >
                <div
                  onClick={() => setExpanded(isItemExpanded ? null : item.id)}
                  className="p-4 sm:p-5 flex items-center justify-between cursor-pointer select-none hover:bg-navy-850/50 transition-colors"
                >
                  <div className="flex items-center gap-4 min-w-0 pr-4">
                    <div className={cn(
                      'p-2.5 rounded-lg border flex-shrink-0',
                      item.failure_count > 0 
                        ? 'bg-rose-950/40 border-rose-800/40 text-rose-400' 
                        : 'bg-emerald-950/40 border-emerald-800/40 text-emerald-400'
                    )}>
                      {item.failure_count > 0 ? (
                        <AlertTriangle className="w-4 h-4" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-200 truncate">
                        {item.filename || 'Pasted Log Snippet'}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-slate-500 mt-1 flex-wrap">
                        <span className="text-blue-400 font-medium">
                          {platformLabels[item.platform || ''] || item.platform || 'Generic CI'}
                        </span>
                        <span>•</span>
                        <span>{formatDate(item.created_at)}</span>
                        <span>•</span>
                        <span className="font-mono text-[11px] text-slate-600">ID: {item.id.slice(0, 8)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className={cn(
                      'text-xs font-semibold px-2.5 py-1 rounded-full border',
                      item.failure_count > 0 
                        ? 'bg-rose-950/50 text-rose-400 border-rose-800/40' 
                        : 'bg-emerald-950/50 text-emerald-400 border-emerald-800/40'
                    )}>
                      {item.failure_count} {item.failure_count === 1 ? 'failure' : 'failures'}
                    </span>
                    {isItemExpanded ? (
                      <ChevronUp className="w-4 h-4 text-slate-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-500" />
                    )}
                  </div>
                </div>

                {isItemExpanded && (
                  <div className="p-4 sm:p-5 border-t border-navy-800/80 bg-navy-950/50 space-y-4">
                    <div className="flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-navy-800/60">
                      <span className="font-semibold uppercase tracking-wider">Detailed Diagnostic Cards</span>
                      <span>Total: {item.diagnoses.length}</span>
                    </div>

                    {item.diagnoses.length === 0 ? (
                      <p className="text-xs text-slate-500 py-4 text-center">No failure items attached to this analysis record.</p>
                    ) : (
                      <div className="space-y-4">
                        {item.diagnoses.map((diag) => (
                          <DiagnosisCardComponent
                            key={diag.id}
                            diagnosis={diag}
                            onFeedbackSubmitted={fetchHistory}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
