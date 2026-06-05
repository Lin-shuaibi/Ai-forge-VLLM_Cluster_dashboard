import { useState, useEffect, useCallback } from 'react'
import { Download, CheckCircle, XCircle, Loader2, Wifi, WifiOff, Terminal, PauseCircle, PlayCircle, StopCircle } from 'lucide-react'

interface DownloadTask {
  task_id: string
  model_name: string
  local_path: string
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'paused' | 'stopped'
  progress: number
  start_time: string
  error?: string
}

export default function DownloadPage() {
  const [modelName, setModelName] = useState('Qwen/Qwen3-0.6B-FP8')
  const [tasks, setTasks] = useState<DownloadTask[]>([])
  const [logs, setLogs] = useState<Record<string, string[]>>({})
  const [speeds, setSpeeds] = useState<Record<string, string>>({})
  const [expandedTask, setExpandedTask] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchTasks = async () => {
    try {
      const response = await fetch('/api/download/local')
      const data = await response.json()
      setTasks(Array.isArray(data) ? data : (data.tasks || []))
    } catch (error) {
      console.error('Failed to fetch tasks:', error)
    }
  }

  const fetchLogs = async () => {
    try {
      const response = await fetch('/api/download/local/logs')
      const data = await response.json()
      setLogs(data.logs || {})
      setSpeeds(data.speeds || {})
    } catch (error) {
      console.error('Failed to fetch logs:', error)
    }
  }

  useEffect(() => {
    fetchTasks()
    fetchLogs()
    const interval = setInterval(() => {
      fetchTasks()
      fetchLogs()
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleStartDownload = async () => {
    if (!modelName.trim()) return
    setLoading(true)
    try {
      await fetch('/api/download/local/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName })
      })
      await fetchTasks()
    } catch (error) {
      console.error('Failed to start download:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePause = async (taskId: string) => {
    try {
      await fetch(`/api/download/local/${taskId}/pause`, { method: 'POST' })
      await fetchTasks()
    } catch (error) {
      console.error('Failed to pause:', error)
    }
  }

  const handleStop = async (taskId: string) => {
    try {
      await fetch(`/api/download/local/${taskId}/stop`, { method: 'POST' })
      await fetchTasks()
    } catch (error) {
      console.error('Failed to stop:', error)
    }
  }

  const handleResume = async (taskId: string) => {
    try {
      await fetch(`/api/download/local/${taskId}/resume`, { method: 'POST' })
      await fetchTasks()
    } catch (error) {
      console.error('Failed to resume:', error)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'downloading': return <Loader2 className="w-4 h-4 animate-spin" />
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed': return <XCircle className="w-4 h-4 text-red-500" />
      case 'paused': return <PauseCircle className="w-4 h-4 text-yellow-500" />
      case 'stopped': return <StopCircle className="w-4 h-4 text-gray-500" />
      default: return <Download className="w-4 h-4" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'downloading': return 'bg-blue-500/20 text-blue-300'
      case 'completed': return 'bg-green-500/20 text-green-300'
      case 'failed': return 'bg-red-500/20 text-red-300'
      case 'paused': return 'bg-yellow-500/20 text-yellow-300'
      case 'stopped': return 'bg-gray-500/20 text-gray-300'
      default: return 'bg-gray-500/20 text-gray-300'
    }
  }

  const toggleExpand = (taskId: string) => {
    setExpandedTask(expandedTask === taskId ? null : taskId)
  }

  return (
    <div className="p-6">
      <h2 className="text-3xl font-bold mb-6">Model Download</h2>

      <div className="glass-card p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium mb-2">Model Name</label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="例如: Qwen/Qwen3-0.6B-FP8"
              className="w-full px-3 py-2 bg-gray-800/50 border border-gray-700 rounded-md focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500/50"
            />
            <p className="text-sm text-gray-400 mt-1">下载路径固定: /data/models/模型名称/</p>
          </div>
          <div>
            <button
              onClick={handleStartDownload}
              disabled={loading || !modelName.trim()}
              className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Start Download
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      <h3 className="text-2xl font-bold mb-4">Download Tasks</h3>

      <div className="glass-card overflow-hidden">
        <table className="min-w-full divide-y divide-gray-700/50">
          <thead className="bg-gray-800/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Task ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Model</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Progress</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Speed</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Actions</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Logs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {tasks.map((task) => (
              <>
                <tr key={task.task_id} className="hover:bg-gray-800/30">
                  <td className="px-6 py-4">
                    <code className="text-sm font-mono">{task.task_id}</code>
                  </td>
                  <td className="px-6 py-4">{task.model_name}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                      {getStatusIcon(task.status)}
                      <span className="ml-1">{task.status}</span>
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div
                          className={`h-full rounded-full ${
                            task.status === 'failed' ? 'bg-red-500' :
                            task.status === 'completed' ? 'bg-green-500' :
                            'bg-blue-500'
                          }`}
                          style={{ width: `${task.progress * 100}%` }}
                        />
                      </div>
                      <span className="text-sm">{Math.round(task.progress * 100)}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {speeds[task.task_id] && (
                      <span className="inline-flex items-center gap-1 text-sm">
                        <Terminal className="w-4 h-4" />
                        {speeds[task.task_id]}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      {task.status === 'downloading' && (
                        <button
                          onClick={() => handlePause(task.task_id)}
                          className="p-1 text-yellow-600 hover:text-yellow-800"
                          title="Pause"
                        >
                          <PauseCircle className="w-5 h-5" />
                        </button>
                      )}
                      {task.status === 'paused' && (
                        <button
                          onClick={() => handleResume(task.task_id)}
                          className="p-1 text-green-600 hover:text-green-800"
                          title="Resume"
                        >
                          <PlayCircle className="w-5 h-5" />
                        </button>
                      )}
                      {(task.status === 'downloading' || task.status === 'paused') && (
                        <button
                          onClick={() => handleStop(task.task_id)}
                          className="p-1 text-red-600 hover:text-red-800"
                          title="Stop & Delete"
                        >
                          <StopCircle className="w-5 h-5" />
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => toggleExpand(task.task_id)}
                      className="p-1 text-gray-600 hover:text-gray-800"
                    >
                      {expandedTask === task.task_id ? '▲' : '▼'}
                    </button>
                  </td>
                </tr>
                {expandedTask === task.task_id && (
                  <tr>
                    <td colSpan={7} className="px-6 py-4 bg-gray-900/50">
                      <div className="max-h-48 overflow-auto font-mono text-sm">
                        <div className="text-gray-400 mb-2">Logs for {task.task_id}:</div>
                        {logs[task.task_id]?.map((log, idx) => (
                          <div key={idx} className="py-1 border-b border-gray-700/50 last:border-0">
                            {log}
                          </div>
                        )) || <div className="text-gray-500">No logs available</div>}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {tasks.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-gray-400">
                  No download tasks
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

