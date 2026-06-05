import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Target, Users, Activity, Zap, PieChart, Settings } from 'lucide-react';

interface ModelVersion {
  id: string;
  model_id: string;
  version_name: string;
  config: any;
  traffic_weight: number;
  is_active: boolean;
  metrics: {
    total_requests: number;
    successful_requests: number;
    avg_latency_ms: number;
    error_rate: number;
  };
  created_at: string;
}

const ABTestingPage: React.FC = () => {
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [newVersionName, setNewVersionName] = useState('');
  const [newVersionConfig, setNewVersionConfig] = useState('{}');
  const [newVersionWeight, setNewVersionWeight] = useState(50);

  useEffect(() => {
    fetchVersions();
  }, [selectedModel]);

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/features/models/${selectedModel || 'default'}/versions`);
      const data = await response.json();
      setVersions(data.versions || []);
    } catch (error) {
      console.error('Failed to fetch versions:', error);
    } finally {
      setLoading(false);
    }
  };

  const createVersion = async () => {
    try {
      const config = JSON.parse(newVersionConfig);
      const response = await fetch(`/api/features/models/${selectedModel}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version_name: newVersionName,
          config,
          traffic_weight: newVersionWeight
        })
      });
      
      if (response.ok) {
        setNewVersionName('');
        setNewVersionConfig('{}');
        setNewVersionWeight(50);
        fetchVersions();
      }
    } catch (error) {
      console.error('Failed to create version:', error);
    }
  };

  const updateTrafficWeights = async (weights: Record<string, number>) => {
    try {
      await fetch(`/api/features/models/${selectedModel}/traffic-weights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(weights)
      });
      fetchVersions();
    } catch (error) {
      console.error('Failed to update weights:', error);
    }
  };

  const promoteVersion = async (versionName: string) => {
    try {
      await fetch(`/api/features/models/${selectedModel}/promote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version_name: versionName })
      });
      fetchVersions();
    } catch (error) {
      console.error('Failed to promote version:', error);
    }
  };

  const getTotalRequests = () => {
    return versions.reduce((sum, v) => sum + v.metrics.total_requests, 0);
  };

  const getSuccessRate = () => {
    const total = getTotalRequests();
    const successful = versions.reduce((sum, v) => sum + v.metrics.successful_requests, 0);
    return total > 0 ? (successful / total) * 100 : 0;
  };

  const getAvgLatency = () => {
    const total = getTotalRequests();
    const weightedSum = versions.reduce((sum, v) => 
      sum + v.metrics.avg_latency_ms * v.metrics.total_requests, 0
    );
    return total > 0 ? weightedSum / total : 0;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          A/B Testing Dashboard
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Compare model versions and optimize performance through controlled experiments
        </p>
      </div>

      {/* Model Selection */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="flex items-center space-x-4">
          <Target className="h-5 w-5 text-blue-500" />
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
          >
            <option value="">Select a model...</option>
            <option value="qwen-7b">Qwen 7B</option>
            <option value="llama-8b">Llama 8B</option>
            <option value="deepseek-16b">DeepSeek 16B</option>
          </select>
          <button
            onClick={fetchVersions}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Load Versions
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {versions.length}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Active Versions
              </div>
            </div>
            <Users className="h-8 w-8 text-blue-500" />
          </div>
        </div>
        
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {getTotalRequests().toLocaleString()}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Total Requests
              </div>
            </div>
            <Activity className="h-8 w-8 text-green-500" />
          </div>
        </div>
        
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {getSuccessRate().toFixed(1)}%
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Success Rate
              </div>
            </div>
            <TrendingUp className="h-8 w-8 text-emerald-500" />
          </div>
        </div>
        
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {getAvgLatency().toFixed(0)}ms
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Avg Latency
              </div>
            </div>
            <Zap className="h-8 w-8 text-yellow-500" />
          </div>
        </div>
      </div>

      {/* Create New Version */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Create New Version
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Version Name
            </label>
            <input
              type="text"
              value={newVersionName}
              onChange={(e) => setNewVersionName(e.target.value)}
              placeholder="e.g., v2.0-optimized"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Traffic Weight (%)
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={newVersionWeight}
              onChange={(e) => setNewVersionWeight(parseInt(e.target.value))}
              className="w-full"
            />
            <div className="text-sm text-gray-600 dark:text-gray-400 text-center">
              {newVersionWeight}%
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Configuration (JSON)
            </label>
            <textarea
              value={newVersionConfig}
              onChange={(e) => setNewVersionConfig(e.target.value)}
              placeholder="Enter JSON configuration..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white font-mono text-sm"
            />
          </div>
        </div>
        
        <div className="mt-4 flex justify-end">
          <button
            onClick={createVersion}
            disabled={!newVersionName || !selectedModel}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Create Version
          </button>
        </div>
      </div>

      {/* Versions Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading versions...</div>
        ) : versions.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <BarChart3 className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p>No versions found for this model</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Version
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Traffic Weight
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Requests
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Success Rate
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Avg Latency
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {versions.map((version) => {
                  const successRate = version.metrics.total_requests > 0 
                    ? (version.metrics.successful_requests / version.metrics.total_requests) * 100 
                    : 0;
                  
                  return (
                    <tr key={version.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="font-medium text-gray-900 dark:text-white">
                            {version.version_name}
                          </div>
                          <div className="text-xs text-gray-500">
                            Created: {new Date(version.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </td>
                      
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center space-x-2">
                          <div className="w-32 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                            <div 
                              className="bg-blue-500 h-2 rounded-full"
                              style={{ width: `${version.traffic_weight}%` }}
                            ></div>
                          </div>
                          <span className="text-sm font-medium">
                            {version.traffic_weight}%
                          </span>
                        </div>
                      </td>
                      
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900 dark:text-white">
                          {version.metrics.total_requests.toLocaleString()}
                        </div>
                      </td>
                      
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="w-24 bg-gray-200 dark:bg-gray-700 rounded-full h-2 mr-2">
                            <div 
                              className={`h-2 rounded-full ${
                                successRate >= 95 ? 'bg-green-500' :
                                successRate >= 80 ? 'bg-yellow-500' : 'bg-red-500'
                              }`}
                              style={{ width: `${Math.min(successRate, 100)}%` }}
                            ></div>
                          </div>
                          <span className={`text-sm font-medium ${
                            successRate >= 95 ? 'text-green-600 dark:text-green-400' :
                            successRate >= 80 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'
                          }`}>
                            {successRate.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900 dark:text-white">
                          {version.metrics.avg_latency_ms.toFixed(0)}ms
                        </div>
                      </td>
                      
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => promoteVersion(version.version_name)}
                            className="px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm rounded hover:bg-blue-200 dark:hover:bg-blue-800"
                          >
                            Promote
                          </button>
                          <button
                            onClick={() => {
                              const newWeight = prompt('Enter new traffic weight (%):', version.traffic_weight.toString());
                              if (newWeight) {
                                updateTrafficWeights({ [version.version_name]: parseInt(newWeight) });
                              }
                            }}
                            className="px-3 py-1 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                          >
                            Adjust
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Traffic Distribution Chart */}
      <div className="mt-6 bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Traffic Distribution
        </h3>
        <div className="h-64 flex items-end space-x-2">
          {versions.map((version) => {
            const height = (version.traffic_weight / Math.max(...versions.map(v => v.traffic_weight))) * 100;
            const successRate = version.metrics.total_requests > 0 
              ? (version.metrics.successful_requests / version.metrics.total_requests) * 100 
              : 0;
            
            return (
              <div key={version.id} className="flex-1 flex flex-col items-center">
                <div 
                  className={`w-full rounded-t ${
                    successRate >= 95 ? 'bg-green-500' :
                    successRate >= 80 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ height: `${height}%` }}
                ></div>
                <div className="mt-2 text-xs text-center">
                  <div className="font-medium">{version.version_name}</div>
                  <div className="text-gray-500">{version.traffic_weight}%</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ABTestingPage;
