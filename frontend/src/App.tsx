import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import AnalyzeLogs from './pages/AnalyzeLogs';
import History from './pages/History';
import Analytics from './pages/Analytics';
import GitHubIntegration from './pages/GitHubIntegration';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analyze" element={<AnalyzeLogs />} />
          <Route path="/history" element={<History />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/github" element={<GitHubIntegration />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
