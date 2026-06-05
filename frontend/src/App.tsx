import NotificationsCenter from './components/NotificationsCenter';
import AuditLogsPage from './pages/AuditLogsPage';
import MarketplacePage from './pages/MarketplacePage';
import ABTestingPage from './pages/ABTestingPage';
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import Cluster from './pages/Cluster'
import ModelService from './pages/ModelService'
import Benchmark from './pages/Benchmark'
import Logs from './pages/Logs'
import DownloadPage from './pages/Download'

export default function App() {
  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/cluster" element={<Cluster />} />
          <Route path="/models" element={<ModelService />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/download" element={<DownloadPage />} />
          <Route path="/audit-logs" element={<AuditLogsPage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/ab-testing" element={<ABTestingPage />} /></Routes>
      </Layout>
    </ErrorBoundary>
  )
}

