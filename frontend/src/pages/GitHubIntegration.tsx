import React, { useState } from 'react';
import { 
  Github, Loader2, AlertCircle, ExternalLink, Play, 
  Key, GitBranch, Clock, CheckCircle2, Shield
} from 'lucide-react';
import { getGithubWorkflows, analyzeGithubRun, GithubRun, AnalysisResponse } from '../lib/api';
import DiagnosisCardComponent from '../components/DiagnosisCard';
import { cn } from '../lib/utils';

export default function GitHubIntegration() {
  const [owner, setOwner] = useState('');
  const [repo, setRepo] = useState('');
  const [token, setToken] = useState('');
  const [runs, setRuns] = useState<GithubRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzingRunId, setAnalyzingRunId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AnalysisResponse | null>(null);

  const fetchRuns = async () => {
    if (!owner.trim() || !repo.trim() || !token.trim()) {
      setError('Please provide GitHub owner, repository, and personal access token.');
      return;
    }
    setError('');
    setRuns([]);
    setResult(null);
    setLoading(true);
    try {
      const r = await getGithubWorkflows(owner.trim(), repo.trim(), token.trim());
      setRuns(r.data.workflows || []);
      if (!r.data.workflows || r.data.workflows.length === 0) {
        setError('No recent failed workflow runs found in this repository.');
      }
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Failed to fetch GitHub Action runs.');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeRun = async (runId: number) => {
    setAnalyzingRunId(runId);
    setResult(null);
    setError('');
    try {
      const r = await analyzeGithubRun(runId, owner.trim(), repo.trim(), token.trim());
      setResult(r.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Failed to download and analyze workflow logs.');
    } finally {
      setAnalyzingRunId(null);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-navy-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Github className="w-6 h-6 text-white" />
            <span>GitHub Actions Integration</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">Connect your repositories to automatically fetch and diagnose failed workflow runs</p>
        </div>
      </div>

      {/* GitHub Repository Credentials Card */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-6 shadow-md space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-navy-800 text-xs font-semibold text-slate-400">
          <Shield className="w-4 h-4 text-blue-400" />
          <span>REPOSITORY CONNECTION & AUTHENTICATION</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
              Repository Owner / Org
            </label>
            <input
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="e.g. facebook or octocat"
              className="w-full bg-navy-950 border border-navy-700/80 rounded-lg px-3.5 py-2 text-sm text-slate-200 outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
              Repository Name
            </label>
            <input
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              placeholder="e.g. react or my-service"
              className="w-full bg-navy-950 border border-navy-700/80 rounded-lg px-3.5 py-2 text-sm text-slate-200 outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
            GitHub Personal Access Token (PAT)
          </label>
          <div className="relative">
            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              className="w-full pl-9 pr-3.5 py-2 bg-navy-950 border border-navy-700/80 rounded-lg text-sm text-slate-200 outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600 font-mono text-xs"
            />
          </div>
          <p className="text-[11px] text-slate-500 mt-1.5 flex items-center gap-1">
            <span>Requires <code className="text-slate-400">repo</code> or <code className="text-slate-400">actions:read</code> scope. Token is transmitted securely in memory and never persisted in database.</span>
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 bg-rose-950/40 border border-rose-800/50 rounded-lg text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <div className="pt-2">
          <button
            onClick={fetchRuns}
            disabled={!owner || !repo || !token || loading}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-navy-800 disabled:text-slate-500 text-white font-medium rounded-lg text-sm transition-all shadow-md shadow-blue-600/20 flex items-center gap-2 cursor-pointer disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Querying GitHub API...</span>
              </>
            ) : (
              <span>Fetch Failed Runs</span>
            )}
          </button>
        </div>
      </div>

      {/* Workflow Runs List */}
      {runs.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Recent Failed Runs ({runs.length})</h2>
            <span className="text-xs text-slate-500 font-mono">{owner}/{repo}</span>
          </div>

          <div className="space-y-2.5">
            {runs.map((run) => (
              <div
                key={run.id}
                className="bg-navy-900 border border-navy-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 hover:border-navy-700 transition-colors shadow-sm"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-white text-sm">{run.workflow_name || run.name}</span>
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-rose-950/60 text-rose-400 border border-rose-800/40 font-semibold">
                      FAILED
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-slate-400 flex-wrap">
                    <span className="flex items-center gap-1 font-mono text-slate-300">
                      <GitBranch className="w-3.5 h-3.5 text-slate-500" />
                      {run.head_branch}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                    <span>•</span>
                    <span className="font-mono text-slate-500 text-[11px]">Run #{run.id}</span>
                  </div>

                  {run.head_commit_message && (
                    <p className="text-xs text-slate-400 font-mono truncate max-w-lg">
                      Commit: {run.head_commit_message}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <a
                    href={run.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-slate-400 hover:text-white bg-navy-800 hover:bg-navy-750 border border-navy-700 rounded-lg transition-colors"
                    title="View on GitHub"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                  <button
                    onClick={() => handleAnalyzeRun(run.id)}
                    disabled={analyzingRunId === run.id}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all shadow-sm"
                  >
                    {analyzingRunId === run.id ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Downloading Logs...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5" />
                        <span>Diagnose Run</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Diagnosis Results */}
      {result && (
        <div className="pt-6 border-t border-navy-800 space-y-4">
          <div className="flex items-center justify-between bg-navy-900 border border-navy-800 p-4 rounded-xl">
            <div>
              <h2 className="text-lg font-bold text-white">GitHub Action Diagnosis</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Analyzed log stream • {result.failure_count} {result.failure_count === 1 ? 'failure' : 'failures'} isolated
              </p>
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-rose-950/60 text-rose-400 border border-rose-800/40">
              Run Diagnosis Ready
            </span>
          </div>

          <div className="space-y-4">
            {result.diagnoses.map((diag) => (
              <DiagnosisCardComponent key={diag.id} diagnosis={diag} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
