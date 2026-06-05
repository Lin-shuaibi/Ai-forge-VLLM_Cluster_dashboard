import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, Square, Box, Cpu, HardDrive, Settings2, ChevronDown, Download, Server } from 'lucide-react'
import { useApi, useWebSocket } from '@/hooks'
import type { ModelInfo, Cluster, ProgressInfo } from '@/types'
import LogViewer from '@/components/LogViewer'
import ProgressTracker from '@/components/ProgressTracker'
import RemoteDownloadDialog from '@/components/RemoteDownloadDialog'

export default function ModelService() {
  const { get, post } = useApi()
  const [models, setModels] = useState<ModelInfo[]>([])
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [showForm, setShowForm] = useState(false)
  const [activeLogModel, setActiveLogModel] = useState<string | null>(null)
  const [startupProgress, setStartupProgress] = useState<{
    modelId: string
    progress: ProgressInfo
    steps: any[]
  } | null>(null)

  const [modelPath, setModelPath] = useState('')
  const [modelName, setModelName] = useState('')
  const [clusterId, setClusterId] = useState('')
  const [tensorParallel, setTensorParallel] = useState(1)
  const [maxModelLen, setMaxModelLen] = useState('')
  const [gpuMemUtil, setGpuMemUtil] = useState(0.90)
  const [dtype, setDtype] = useState('auto')
  const [maxNumSeqs, setMaxNumSeqs] = useState(256)
  const [port, setPort] = useState(8000)
  const [trustRemoteCode, setTrustRemoteCode] = useState(true)
  const [enforceEager, setEnforceEager] = useState(false)
  const [starting, setStarting] = useState(false)
  const [remoteOpen, setRemoteOpen] = useState(false)
  const [remoteDownloadId, setRemoteDownloadId] = useState('')
  const [remoteDownloadName, setRemoteDownloadName] = useState('')
  const [remoteDownloadSource, setRemoteDownloadSource] = useState('huggingface')
  const [downloadPath, setDownloadPath] = useState('')

  const { logs, connected } = useWebSocket(
    activeLogModel ? `/api/models/${activeLogModel}/logs` : null
  )

  const refresh = useCallback(async () => {
    const [m, c] = await Promise.all([
      get<ModelInfo[]>('/models').catch(() => []),
      get<Cluster[]>('/clusters').catch(() => []),
    ])
    setModels(m || [])
    setClusters(c || [])
  }, [])

  useEffect(() => { refresh() }, [])

  const handleStart = async () => {
    if (!modelPath || !modelName) return
    setStarting(true)
    try {
      const result = await post<{ model_id: string; progress: ProgressInfo }>('/models/start', {
        model_path: modelPath,
        model_name: modelName,
        cluster_id: clusterId || undefined,
        tensor_parallel_size: tensorParallel,
        max_model_len: maxModelLen ? parseInt(maxModelLen) : undefined,
        gpu_memory_utilization: gpuMemUtil,
        dtype,
        max_num_seqs: maxNumSeqs,
        port,
        trust_remote_code: trustRemoteCode,
        enforce_eager: enforceEager,
      })
      
      // Start tracking progress
      setStartupProgress({
        modelId: result.model_id,
        progress: result.progress,
        steps: Object.entries(result.progress.steps).map(([stepName, stepData]) => ({
          step: stepName,
          current: result.progress.current_step,
          total: result.progress.total_steps,
          percentage: result.progress.percentage,
          status: stepData.status || 'in_progress',
          details: stepData
        }))
      })
      
      setActiveLogModel(result.model_id)
      setShowForm(false)
      
      // Poll for progress updates
      const pollProgress = async () => {
        try {
          const progress = await get<{ status: string }>(`/models/${result.model_id}/progress`)
          if (progress.status === 'running') {
            setStartupProgress(null)
            await refresh()
          }
        } catch (e) {
          console.error('Failed to poll progress:', e)
        }
      }
      
      // Poll every 2 seconds for 30 seconds
      const pollInterval = setInterval(pollProgress, 2000)
      setTimeout(() => {
        clearInterval(pollInterval)
        setStartupProgress(null)
        refresh()
      }, 30000)
    } catch (e: any) {
      alert('启动失败: ' + (e?.message || e))
    }
    setStarting(false)
  }

  const handleStop = async (id: string) => {
    await post(`/models/${id}/stop`).catch(() => {})
    await refresh()
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <h2 className="text-2xl font-bold text-white">模型服务</h2>
          <p className="text-white/40 text-sm mt-1">启动和管理 vLLM 模型</p>
        </motion.div>
        <div className="flex items-center gap-3">
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={() => setRemoteOpen(true)}
            className="btn-secondary flex items-center gap-2"
          >
            <Download size={18} />
            远程下载
          </motion.button>
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={() => setShowForm(!showForm)}
            className="btn-primary flex items-center gap-2"
          >
            <Play size={18} />
            启动模型
          </motion.button>
        </div>
      </div>

      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="card space-y-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Box size={18} className="text-primary-400" />
                启动新模型
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">模型路径 *</label>
                  <input className="input-field" value={modelPath} onChange={(e) => setModelPath(e.target.value)} placeholder="/models/Qwen2.5-7B-Instruct" />
                </div>
                <div>
                  <label className="label">模型名称 *</label>
                  <input className="input-field" value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="Qwen2.5-7B" />
                </div>
                <div>
                  <label className="label">所属集群</label>
                  <select className="input-field" value={clusterId} onChange={(e) => setClusterId(e.target.value)}>
                    <option value="">不使用集群 (独立运行)</option>
                    {clusters.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.node_count} nodes)</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Tensor Parallel</label>
                  <input type="number" className="input-field" min={1} max={8} value={tensorParallel} onChange={(e) => setTensorParallel(Number(e.target.value))} />
                </div>
                <div>
                  <label className="label">最大上下文长度</label>
                  <input className="input-field" value={maxModelLen} onChange={(e) => setMaxModelLen(e.target.value)} placeholder="留空自动" />
                </div>
                <div>
                  <label className="label">GPU 内存利用率</label>
                  <input type="number" className="input-field" min={0.1} max={1.0} step={0.05} value={gpuMemUtil} onChange={(e) => setGpuMemUtil(Number(e.target.value))} />
                </div>
                <div>
                  <label className="label">数据类型</label>
                  <select className="input-field" value={dtype} onChange={(e) => setDtype(e.target.value)}>
                    <option value="auto">auto</option>
                    <option value="float16">float16</option>
                    <option value="bfloat16">bfloat16</option>
                    <option value="float32">float32</option>
                  </select>
                </div>
                <div>
                  <label className="label">端口</label>
                  <input type="number" className="input-field" value={port} onChange={(e) => setPort(Number(e.target.value))} />
                </div>
              </div>

              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={trustRemoteCode} onChange={(e) => setTrustRemoteCode(e.target.checked)} className="w-4 h-4 rounded accent-primary-500" />
                  Trust Remote Code
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={enforceEager} onChange={(e) => setEnforceEager(e.target.checked)} className="w-4 h-4 rounded accent-primary-500" />
                  Enforce Eager
                </label>
              </div>

              <div className="flex gap-3">
                <button onClick={handleStart} disabled={starting} className="btn-primary flex-1">
                  {starting ? '启动中...' : '确认启动'}
                </button>
                <button onClick={() => setShowForm(false)} className="btn-secondary">取消</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Progress Tracker for Active Startup */}
      <AnimatePresence>
        {startupProgress && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="card"
          >
            <ProgressTracker
              title={`模型启动进度: ${startupProgress.modelId}`}
              steps={startupProgress.steps}
              currentStep={startupProgress.progress.current_step}
              totalSteps={startupProgress.progress.total_steps}
              percentage={startupProgress.progress.percentage}
              elapsedSeconds={startupProgress.progress.elapsed_seconds}
            />
            <div className="mt-3 pt-3 border-t border-white/5 text-xs text-white/40">
              <p>模型ID: {startupProgress.modelId}</p>
              <p>正在启动模型，请勿关闭页面...</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Model List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AnimatePresence>
          {models.map((m, i) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="card"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${m.status === 'running' ? 'bg-green-500/20' : 'bg-yellow-500/20'}`}>
                    <Cpu size={20} className={m.status === 'running' ? 'text-green-400' : 'text-yellow-400'} />
                  </div>
                  <div>
                    <h4 className="font-semibold">{m.name}</h4>
                    <p className="text-xs text-white/40 truncate max-w-[180px]">{m.path}</p>
                  </div>
                </div>
                <span className={`badge ${m.status === 'running' ? 'badge-running' : m.status === 'stopped' ? 'badge-stopped' : 'badge-starting'}`}>
                  {m.status === 'running' ? '运行中' : m.status === 'stopped' ? '已停止' : '启动中'}
                </span>
              </div>

              <div className="mt-3 flex items-center gap-4 text-xs text-white/50">
                <span className="flex items-center gap-1"><HardDrive size={12} /> Port: {m.port}</span>
                {m.cluster_id && <span className="flex items-center gap-1"><Settings2 size={12} /> 集群模式</span>}
              </div>

              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => setActiveLogModel(activeLogModel === m.id ? null : m.id)}
                  className={`btn-secondary text-xs flex-1 ${activeLogModel === m.id ? 'bg-primary-600/20 border-primary-500/30 text-primary-300' : ''}`}
                >
                  {activeLogModel === m.id ? '隐藏日志' : '查看日志'}
                </button>
                {m.status !== 'stopped' && (
                  <button onClick={() => handleStop(m.id)} className="btn-danger text-xs">
                    <Square size={14} />
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {models.length === 0 && (
          <div className="col-span-full text-center py-16 text-white/25">
            <Box size={48} className="mx-auto mb-4 opacity-30" />
            <p>暂无模型，点击上方按钮启动第一个模型</p>
          </div>
        )}
      </div>

      <AnimatePresence>
        {activeLogModel && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}>
            <LogViewer logs={logs} connected={connected} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Remote Download Dialog */}
      <RemoteDownloadDialog
        open={remoteOpen}
        onClose={() => setRemoteOpen(false)}
        modelId={remoteDownloadId}
        modelName={remoteDownloadName}
        source={remoteDownloadSource}
      />
    </div>
  )
}