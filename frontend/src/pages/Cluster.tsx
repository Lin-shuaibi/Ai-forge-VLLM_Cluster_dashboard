import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Trash2, Server, Wifi, WifiOff, Network, Cpu } from 'lucide-react'
import { useApi, useWebSocket } from '@/hooks'
import type { Cluster, NodeSpec, ImageSettings, ProgressInfo } from '@/types'
import LogViewer from '@/components/LogViewer'
import ProgressTracker from '@/components/ProgressTracker'

export default function Cluster() {
  const { get, post, del } = useApi()
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [activeLogCluster, setActiveLogCluster] = useState<string | null>(null)
  const [settings, setSettings] = useState<ImageSettings | null>(null)
  const [creationProgress, setCreationProgress] = useState<{
    clusterId: string
    progress: ProgressInfo
    steps: any[]
  } | null>(null)

  // Create form
  const [name, setName] = useState('')
  const [nodes, setNodes] = useState<NodeSpec[]>([{ ip: '', username: 'root', password: '', gpus: 1 }])
  const [useCombined, setUseCombined] = useState(false)
  const [customImage, setCustomImage] = useState('')
  const [creating, setCreating] = useState(false)

  const { logs, connected } = useWebSocket(
    activeLogCluster ? `/api/clusters/${activeLogCluster}/logs` : null
  )

  const refresh = useCallback(async () => {
    const data = await get<Cluster[]>('/clusters').catch(() => [])
    setClusters(data || [])
  }, [])

  useEffect(() => {
    refresh()
    get<ImageSettings>('/settings').then(setSettings).catch(() => {})
  }, [])

  const addNode = () => setNodes([...nodes, { ip: '', username: 'root', password: '', gpus: 1 }])
  const removeNode = (i: number) => setNodes(nodes.filter((_, idx) => idx !== i))
  const updateNode = (i: number, field: keyof NodeSpec, val: string | number) => {
    const updated = [...nodes]
    updated[i] = { ...updated[i], [field]: field === 'gpus' ? Number(val) : val }
    setNodes(updated)
  }

  const handleCreate = async () => {
    if (!name || nodes.some((n) => !n.ip)) return
    setCreating(true)
    try {
      const result = await post<{ cluster_id: string; progress: ProgressInfo }>('/clusters', {
        name,
        nodes,
        use_combined_image: useCombined,
        image: customImage || undefined,
      })
      
      // Start tracking progress
      setCreationProgress({
        clusterId: result.cluster_id,
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
      
      setActiveLogCluster(result.cluster_id)
      
      // Poll for progress updates
      const pollProgress = async () => {
        try {
          const progress = await get<any>(`/clusters/${result.cluster_id}/progress`)
          if (progress && progress.status !== 'no_progress_data' && progress.steps) {
            setCreationProgress(prev => prev ? {
              ...prev,
              progress,
              steps: Object.entries(progress.steps).map(([stepName, stepData]: [string, any]) => ({
                step: stepName,
                current: progress.current_step,
                total: progress.total_steps,
                percentage: progress.percentage,
                status: stepData.status || 'in_progress',
                details: stepData
              }))
            } : null)
          }
        } catch (e) {
          console.error('Failed to poll progress:', e)
        }
      }
      
      // Poll every 2 seconds for 30 seconds
      const pollInterval = setInterval(pollProgress, 2000)
      setTimeout(() => {
        clearInterval(pollInterval)
        setCreationProgress(null)
        refresh()
      }, 30000)
      
      setShowCreate(false)
      setName('')
      setNodes([{ ip: '', username: 'root', password: '', gpus: 1 }])
      setCustomImage('')
    } catch (e: any) {
      alert('创建失败: ' + (e?.message || e))
    }
    setCreating(false)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除该集群？')) return
    await del(`/clusters/${id}`).catch(() => {})
    if (activeLogCluster === id) setActiveLogCluster(null)
    await refresh()
  }

  const effectiveImage = customImage || settings?.ray_vllm_image || settings?.ray_image || ''

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <h2 className="text-2xl font-bold text-white">集群管理</h2>
          <p className="text-white/40 text-sm mt-1">创建和管理 Ray 集群</p>
        </motion.div>
        <motion.button
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          onClick={() => setShowCreate(!showCreate)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={18} />
          创建集群
        </motion.button>
      </div>

      {/* Create Form */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="card space-y-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Network size={18} className="text-primary-400" />
                新建集群
              </h3>

              <div>
                <label className="label">集群名称</label>
                <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} placeholder="my-vllm-cluster" />
              </div>

              <div>
                <label className="label">设备节点 (IP / 账号 / 密码 / GPU数)</label>
                <div className="space-y-2">
                  {nodes.map((n, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input
                        className="input-field flex-1"
                        placeholder="192.168.1.x"
                        value={n.ip}
                        onChange={(e) => updateNode(i, 'ip', e.target.value)}
                      />
                      <input
                        className="input-field w-20"
                        placeholder="账号"
                        value={n.username}
                        onChange={(e) => updateNode(i, 'username', e.target.value)}
                      />
                      <input
                        type="password"
                        className="input-field w-24"
                        placeholder="密码"
                        value={n.password}
                        onChange={(e) => updateNode(i, 'password', e.target.value)}
                      />
                      <input
                        type="number"
                        className="input-field w-16"
                        min={1}
                        value={n.gpus}
                        onChange={(e) => updateNode(i, 'gpus', e.target.value)}
                        title="GPU 数量"
                      />
                      {nodes.length > 1 && (
                        <button onClick={() => removeNode(i)} className="p-2 text-red-400 hover:bg-red-500/10 rounded-lg">
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <button onClick={addNode} className="text-xs text-primary-400 hover:text-primary-300 mt-2">+ 添加节点</button>
              </div>

              <div>
                <label className="label">自定义镜像 (可选)</label>
                <input
                  className="input-field"
                  value={customImage}
                  onChange={(e) => setCustomImage(e.target.value)}
                  placeholder={effectiveImage || '留空使用设置页默认镜像'}
                />
                {effectiveImage && !customImage && (
                  <p className="text-[10px] text-white/25 mt-1">当前默认: {effectiveImage}</p>
                )}
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="useCombined"
                  checked={useCombined}
                  onChange={(e) => setUseCombined(e.target.checked)}
                  className="w-4 h-4 rounded accent-primary-500"
                />
                <label htmlFor="useCombined" className="text-sm cursor-pointer">
                  使用 Ray+vLLM 合并镜像 (模型将在集群容器内启动)
                </label>
              </div>

              <div className="flex gap-3">
                <button onClick={handleCreate} disabled={creating} className="btn-primary flex-1">
                  {creating ? '创建中...' : '确认创建'}
                </button>
                <button onClick={() => setShowCreate(false)} className="btn-secondary">取消</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Progress Tracker for Active Creation */}
      <AnimatePresence>
        {creationProgress && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="card"
          >
            <ProgressTracker
              title={`集群创建进度: ${creationProgress.clusterId}`}
              steps={creationProgress.steps}
              currentStep={creationProgress.progress.current_step}
              totalSteps={creationProgress.progress.total_steps}
              percentage={creationProgress.progress.percentage}
              elapsedSeconds={creationProgress.progress.elapsed_seconds}
            />
            <div className="mt-3 pt-3 border-t border-white/5 text-xs text-white/40">
              <p>集群ID: {creationProgress.clusterId}</p>
              <p>正在创建集群，请勿关闭页面...</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Cluster List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AnimatePresence>
          {clusters.map((c, i) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="card"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.status === 'running' ? 'bg-green-500/20' : 'bg-yellow-500/20'}`}>
                    <Server size={20} className={c.status === 'running' ? 'text-green-400' : 'text-yellow-400'} />
                  </div>
                  <div>
                    <h4 className="font-semibold">{c.name}</h4>
                    <p className="text-xs text-white/40">{c.id}</p>
                  </div>
                </div>
                <span className={`badge ${c.status === 'running' ? 'badge-running' : 'badge-creating'}`}>
                  {c.status === 'running' ? '运行中' : '创建中'}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                <div className="glass p-3 text-center">
                  <Cpu size={14} className="text-primary-400 mx-auto mb-1" />
                  <p className="text-white/30">节点</p>
                  <p className="text-white font-bold">{c.node_count}</p>
                </div>
                <div className="glass p-3 text-center">
                  <Wifi size={14} className="text-green-400 mx-auto mb-1" />
                  <p className="text-white/30">Head IP</p>
                  <p className="text-white font-bold truncate">{c.head_ip || '-'}</p>
                </div>
                <div className="glass p-3 text-center">
                  <Network size={14} className="text-blue-400 mx-auto mb-1" />
                  <p className="text-white/30">合并镜像</p>
                  <p className="text-white font-bold">{c.use_combined ? '是' : '否'}</p>
                </div>
              </div>

              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => setActiveLogCluster(activeLogCluster === c.id ? null : c.id)}
                  className={`btn-secondary text-xs flex-1 ${activeLogCluster === c.id ? 'bg-primary-600/20 border-primary-500/30 text-primary-300' : ''}`}
                >
                  {activeLogCluster === c.id ? '隐藏日志' : '查看日志'}
                </button>
                <button onClick={() => handleDelete(c.id)} className="btn-danger text-xs">
                  <Trash2 size={14} />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {clusters.length === 0 && (
          <div className="col-span-full text-center py-16 text-white/25">
            <Server size={48} className="mx-auto mb-4 opacity-30" />
            <p>暂无集群，点击上方按钮创建第一个集群</p>
          </div>
        )}
      </div>

      {/* Logs Panel */}
      <AnimatePresence>
        {activeLogCluster && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}>
            <LogViewer logs={logs} connected={connected} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}