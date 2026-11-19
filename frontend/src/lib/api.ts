import axios from 'axios';

// Directly connect to the FastAPI backend running on port 8000
const API_BASE_URL = typeof window !== 'undefined' && window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

export interface SimilarFailure {
  error_pattern: string;
  category: string;
  fix: string;
  similarity_score: number;
}

export interface DiagnosisCard {
  id: string;
  analysis_id: string;
  pipeline_name?: string;
  failed_step?: string;
  failure_category: string;
  error_message?: string;
  root_cause?: string;
  confidence_score: number;
  recommended_fix?: string;
  commands: string[];
  reasoning?: string;
  log_evidence?: string;
  similar_failures: SimilarFailure[];
  is_flaky: boolean;
  rerun_recommended: boolean;
  resolution_status: string;
  resolved_at?: string;
}

export interface AnalysisResponse {
  analysis_id: string;
  filename?: string;
  platform?: string;
  failure_count: number;
  diagnoses: DiagnosisCard[];
  created_at: string;
}

export interface AnalysisSummary {
  id: string;
  created_at: string;
  filename?: string;
  platform?: string;
  failure_count: number;
  status: string;
  diagnoses: DiagnosisCard[];
}

export interface DashboardStats {
  total_analyses: number;
  total_failures: number;
  most_common_category?: string;
  recurring_failures: number;
  category_distribution: Record<string, number>;
  recent_analyses: AnalysisSummary[];
}

export interface AnalyticsTrends {
  failures_by_day: { date: string; count: number }[];
  top_errors: { error_message: string; count: number }[];
  category_trends: { category: string; count: number }[];
  fix_success_rate: number;
  flaky_test_count: number;
}

export interface GithubRun {
  id: number;
  name: string;
  workflow_name: string;
  status: string;
  conclusion: string;
  created_at: string;
  html_url: string;
  head_commit_message: string;
  head_branch: string;
}

export const analyzeFile = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api.post<AnalysisResponse>('/api/analyze/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const analyzeText = (logContent: string, filename?: string) =>
  api.post<AnalysisResponse>('/api/analyze/text', { log_content: logContent, filename });

export const getAnalyses = (skip = 0, limit = 20) =>
  api.get<AnalysisSummary[]>(`/api/analyses?skip=${skip}&limit=${limit}`);

export const getAnalysis = (id: string) =>
  api.get<AnalysisSummary>(`/api/analyses/${id}`);

export const submitFeedback = (diagnosisId: string, worked: boolean, notes?: string) =>
  api.post(`/api/diagnoses/${diagnosisId}/feedback`, { worked, notes });

export const getDashboardStats = () =>
  api.get<DashboardStats>('/api/dashboard/stats');

export const getAnalyticsTrends = () =>
  api.get<AnalyticsTrends>('/api/analytics/trends');

export const getGithubWorkflows = (owner: string, repo: string, token: string) =>
  api.post<{ workflows: GithubRun[] }>('/api/github/workflows', { owner, repo, token });

export const analyzeGithubRun = (runId: number, owner: string, repo: string, token: string) =>
  api.post<AnalysisResponse>(`/api/github/analyze/${runId}`, { owner, repo, token });

export const getHealth = () => api.get('/api/health');

export default api;
