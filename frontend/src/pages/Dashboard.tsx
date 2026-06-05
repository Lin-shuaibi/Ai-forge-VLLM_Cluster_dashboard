import { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { 
  Server, Box, Gauge, Activity, Cpu, HardDrive, Monitor, Thermometer, 
  Zap, MemoryStick, Database, Network, Shield, 
  Radio, Layers, Globe, Wifi, Clock, TrendingUp,
  Cloud, Terminal, Settings, Users, Battery,
  ArrowRight
} from 'lucide-react'
import { useApi, useWebSocket } from '@/hooks'
import type { SystemStatus } from '@/types'
import LogViewer from '@/components/LogViewer'

interface GPUInfo {
  available: boolean
  gpu_count: number
  message?: string
  total_memory_used_mb?: number
  total_memory_mb?: number
  memory_usage_percent?: number
  avg_temperature?: number
  avg_utilization?: number
  gpus?: Array<{
    index: number
    name: string
    temperature: number | null
    gpu_utilization: number | null
    memory_used_mb: number | null
    memory_total_mb: number | null
    power_draw_w: number | null
  }>
}

export default function Dashboard() {
  const { get } = useApi()
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [gpuInfo, setGpuInfo] = useState<GPUInfo | null>(null)
  const { logs, connected } = useWebSocket('/ws/logs/global')

  useEffect(() => {
    get<SystemStatus>('/status').then(setStatus).catch(() => {})
    get<GPUInfo>('/api/gpu/summary').then(setGpuInfo).catch(() => {})
    const timer = setInterval(() => {
      get<SystemStatus>('/status').then(setStatus).catch(() => {})
      get<GPUInfo>('/api/gpu/summary').then(setGpuInfo).catch(() => {})
    }, 5000)
    return () => clearInterval(timer)
  }, [])




  const systemMetrics = [
    { label: '集群节点', value: status?.clusters ?? 0, icon: Server, color: '#0066ff', progress: 85 },
    { label: '运行模型', value: status?.models ?? 0, icon: Box, color: '#9d00ff', progress: 60 },
    { label: '性能测试', value: status?.benchmarks ?? 0, icon: Gauge, color: '#00ff41', progress: 45 },
    { label: 'Docker状态', value: status?.docker ? '在线' : '离线', icon: Activity, color: '#ffaa00', progress: status?.docker ? 100 : 20 },
    { label: '网络延迟', value: '12ms', icon: Network, color: '#00d9ff', progress: 92 },
    { label: '系统负载', value: '0.8', icon: Cpu, color: '#ff4757', progress: 80 },
  ]

  const gpuMetrics = gpuInfo?.available ? [
    { label: 'GPU数量', value: gpuInfo.gpu_count, icon: Cpu, color: '#00d9ff' },
    { label: '平均温度', value: `${gpuInfo.avg_temperature}\u00B0C`, icon: Thermometer, color: '#ffaa00' },
    { label: '利用率', value: `${gpuInfo.avg_utilization}%`, icon: Zap, color: '#00ff41' },
    { label: '显存占用', value: `${gpuInfo.memory_usage_percent}%`, icon: MemoryStick, color: '#9d00ff' },
  ] : []

  return (
    <div className="relative min-h-screen bg-[#080d1a] overflow-hidden">
      {/* 科幻网格背景 */}
      <div className="absolute inset-0 opacity-[0.07]">
        <div className="absolute inset-0" style={{
          backgroundImage: `linear-gradient(rgba(0, 217, 255, 1) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(0, 217, 255, 1) 1px, transparent 1px)`,
          backgroundSize: '50px 50px'
        }} />
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(circle at 30% 20%, rgba(0,217,255,0.08) 0%, transparent 50%), radial-gradient(circle at 80% 40%, rgba(157,0,255,0.08) 0%, transparent 50%)'
        }} />
      </div>

      <div className="relative z-10 p-6">
        {/* 顶部标题区 */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-4xl font-extrabold tracking-tight" style={{
                background: 'linear-gradient(135deg, #00d9ff 0%, #9d00ff 50%, #ff00ff 100%)',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                color: 'transparent',
                textShadow: '0 0 40px rgba(0, 217, 255, 0.4)',
                filter: 'drop-shadow(0 0 8px rgba(0,217,255,0.3))'
              }}>VLLM 控制中心</h1>
              <p className="text-xs text-white/30 mt-1 tracking-[0.2em] uppercase">AI CLUSTER MONITORING &amp; SCHEDULING SYSTEM</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-black/40 border border-white/10">
                <Wifi size={14} className="text-green-400" />
                <span className="text-xs text-white/50">连接</span>
                <span className="text-sm font-semibold text-green-400">{connected ? '在线' : '离线'}</span>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-black/40 border border-white/10">
                <Clock size={14} className="text-blue-400" />
                <span className="text-xs text-white/50">延迟</span>
                <span className="text-sm font-semibold text-blue-400">12ms</span>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-black/40 border border-white/10">
                <Shield size={14} className="text-purple-400" />
                <span className="text-xs text-white/50">状态</span>
                <span className="text-sm font-semibold text-purple-400">正常</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* 科幻HUD主网格 */}
        <div className="hud-grid">
          {/* 左侧主仪表区 */}
          <div className="hud-main-panel">
            <motion.div 
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              className="card-3d p-6"
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-bold text-white/90 uppercase tracking-[0.15em]">系统总览</h2>
                <div className="flex items-center gap-2">
                  <span className="status-led"></span>
                  <span className="text-[10px] text-white/30 uppercase tracking-wider">实时同步中</span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {systemMetrics.map((metric, i) => (
                  <motion.div
                    key={metric.label}
                    initial={{ opacity: 0, scale: 0.92 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.08, duration: 0.4 }}
                    className="data-panel group cursor-pointer hover:border-cyan-400/30 transition-all duration-300"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <metric.icon size={20} style={{ color: metric.color }} />
                      <div className="w-10 h-10 relative">
                        <svg width="40" height="40" viewBox="0 0 40 40" className="-rotate-90">
                          <defs>
                            <linearGradient id={`grad-${i}`} x1="0%" y1="0%" x2="100%" y2="100%">
                              <stop offset="0%" stopColor={metric.color} stopOpacity="1" />
                              <stop offset="100%" stopColor={metric.color} stopOpacity="0.2" />
                            </linearGradient>
                          </defs>
                          <circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
                          <circle 
                            cx="20" cy="20" r="16" fill="none" 
                            stroke={`url(#grad-${i})`} strokeWidth="3" strokeLinecap="round"
                            strokeDasharray={`${(metric.progress / 100) * 100.5} 100.5`}
                            className="transition-all duration-700"
                          />
                        </svg>
                      </div>
                    </div>
                    <div className="text-3xl font-extrabold text-white">{metric.value}</div>
                    <div className="text-xs text-white/40 mt-1 tracking-wider uppercase">{metric.label}</div>
                    <div className="waveform mt-3">
                      <div className="waveform-line"></div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            {/* GPU监控面板 */}
            {gpuInfo && (
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="card-3d mt-6 p-6"
              >
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-sm font-bold text-white/90 uppercase tracking-[0.15em] flex items-center gap-2">
                    <Monitor size={18} className="text-cyan-400" />
                    GPU 监控
                    {gpuInfo.available ? (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 tracking-wider">
                        {gpuInfo.gpu_count} GPU 在线
                      </span>
                    ) : (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400 tracking-wider">
                        无GPU
                      </span>
                    )}
                  </h2>
                  <div className="radar-container">
                    <div className="radar-grid"></div>
                    <div className="radar-scan"></div>
                  </div>
                </div>

                {gpuInfo.available ? (
                  <>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                      {gpuMetrics.map((metric, i) => (
                        <div key={metric.label} className="data-panel text-center">
                          <metric.icon size={20} style={{ color: metric.color }} className="mx-auto mb-2" />
                          <div className="text-2xl font-extrabold text-white">{metric.value}</div>
                          <div className="text-xs text-white/40 mt-1 tracking-wider uppercase">{metric.label}</div>
                        </div>
                      ))}
                    </div>

                    {gpuInfo.gpus && gpuInfo.gpus.length > 0 && (
                      <div className="space-y-4">
                        <div className="hud-divider"></div>
                        <h3 className="text-xs text-white/40 uppercase tracking-[0.2em] mb-3">GPU 详细数据</h3>
                        {gpuInfo.gpus.map((gpu) => (
                          <div key={gpu.index} className="data-panel">
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-3">
                                <Cpu size={16} className="text-cyan-400" />
                                <span className="text-sm font-semibold">GPU {gpu.index}: {gpu.name}</span>
                              </div>
                              <div className="flex items-center gap-4 text-xs text-white/50">
                                <span className="flex items-center gap-1">
                                  <Thermometer size={12} className="text-orange-400" />
                                  {gpu.temperature ?? 'N/A'}\u00B0C
                                </span>
                                <span className="flex items-center gap-1">
                                  <Zap size={12} className="text-yellow-400" />
                                  {gpu.power_draw_w ?? 'N/A'}W
                                </span>
                              </div>
                            </div>
                            
                            <div className="space-y-3">
                              <div>
                                <div className="flex justify-between text-xs mb-1">
                                  <span className="text-white/40">GPU 利用率</span>
                                  <span className="text-cyan-400 font-semibold">{gpu.gpu_utilization ?? 0}%</span>
                                </div>
                                <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
                                  <div 
                                    className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500 relative overflow-hidden"
                                    style={{ width: `${gpu.gpu_utilization ?? 0}%` }}
                                  >
                                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer"></div>
                                  </div>
                                </div>
                              </div>
                              <div>
                                <div className="flex justify-between text-xs mb-1">
                                  <span className="text-white/40">显存占用</span>
                                  <span className="text-purple-400 font-semibold">
                                    {gpu.memory_used_mb ? (gpu.memory_used_mb / 1024).toFixed(1) : 0} / 
                                    {gpu.memory_total_mb ? (gpu.memory_total_mb / 1024).toFixed(1) : 0} GB
                                  </span>
                                </div>
                                <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
                                  <div 
                                    className="h-full rounded-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500 relative overflow-hidden"
                                    style={{ width: `${gpu.memory_total_mb ? ((gpu.memory_used_mb ?? 0) / gpu.memory_total_mb * 100) : 0}%` }}
                                  >
                                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer"></div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-10">
                    <Monitor size={48} className="mx-auto text-white/10 mb-4" />
                    <p className="text-white/30 text-sm">{gpuInfo?.message || '未检测到 NVIDIA GPU'}</p>
                  </div>
                )}
              </motion.div>
            )}
          </div>

          {/* 右侧数据流面板 */}
          <div className="hud-side-panel">
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="card-3d h-full p-6 flex flex-col"
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-bold text-white/90 uppercase tracking-[0.15em]">数据流监控</h2>
                <div className="flex items-center gap-2">
                  <Radio size={14} className="text-green-400 animate-pulse" />
                  <span className="text-[10px] text-green-400/70 uppercase tracking-wider">活跃</span>
                </div>
              </div>

              {/* 运行模型 */}
              {status && status.models_list.length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xs text-white/40 uppercase tracking-[0.2em]">运行中的模型</h3>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">
                      {status.models_list.length}
                    </span>
                  </div>
                  <div className="space-y-3">
                    {status.models_list.map((model) => (
                      <div key={model.id} className="data-panel p-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-semibold truncate">{model.name}</span>
                          <span className={`badge text-[10px] ${model.status === 'running' ? 'badge-running' : 'badge-starting'}`}>
                            {model.status}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[10px] text-white/40">
                          <span>端口: {model.port}</span>
                          <span className="flex items-center gap-1">
                            <Database size={10} />
                            {model.path.split('/').pop()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(!status || status.models_list.length === 0) && (
                <div className="data-panel p-4 text-center mb-6">
                  <Box size={24} className="mx-auto text-white/10 mb-2" />
                  <p className="text-xs text-white/30">暂无运行中的模型</p>
                </div>
              )}

              <div className="hud-divider"></div>

              {/* 系统日志 */}
              <div className="flex-1 flex flex-col min-h-0 mt-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs text-white/40 uppercase tracking-[0.2em] flex items-center gap-2">
                    <Terminal size={14} />
                    系统日志
                  </h3>
                  <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 shadow-[0_0_8px_#00ff41] animate-pulse' : 'bg-red-400'}`}></span>
                </div>
                <div className="data-panel p-4 flex-1 overflow-hidden">
                  <LogViewer logs={logs} connected={connected} maxHeight="100%" />
                </div>
              </div>

              {/* 快速操作 */}
              <div className="mt-6">
                <h3 className="text-xs text-white/40 uppercase tracking-[0.2em] mb-4">快速操作</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Link to="/benchmark">
                    <button className="w-full btn-neon py-3 rounded-xl text-sm font-medium">
                      <TrendingUp size={14} className="inline mr-1" />
                      性能测试
                    </button>
                  </Link>
                  <Link to="/settings">
                    <button className="w-full btn-neon py-3 rounded-xl text-sm font-medium">
                      <Settings size={14} className="inline mr-1" />
                      系统设置
                    </button>
                  </Link>
                  <Link to="/cluster">
                    <button className="w-full btn-neon py-3 rounded-xl text-sm font-medium">
                      <Users size={14} className="inline mr-1" />
                      集群管理
                    </button>
                  </Link>
                  <Link to="/models">
                    <button className="w-full btn-neon py-3 rounded-xl text-sm font-medium">
                      <Cloud size={14} className="inline mr-1" />
                      模型部署
                    </button>
                  </Link>
                </div>
              </div>
            </motion.div>
          </div>
        </div>

        {/* 底部状态栏 */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="mt-8"
        >
          <div className="card-3d p-4">
            <div className="flex items-center justify-between text-xs flex-wrap gap-3">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Battery size={14} className="text-green-400" />
                  <span className="text-white/40">CPU</span>
                  <span className="text-white/80 font-semibold">34%</span>
                </div>
                <div className="flex items-center gap-2">
                  <Globe size={14} className="text-blue-400" />
                  <span className="text-white/40">吞吐</span>
                  <span className="text-white/80 font-semibold">2.4 Gb/s</span>
                </div>
                <div className="flex items-center gap-2">
                  <Layers size={14} className="text-purple-400" />
                  <span className="text-white/40">存储</span>
                  <span className="text-white/80 font-semibold">1.2 TB</span>
                </div>
              </div>
              <div className="text-white/20">
                最后更新: 刚刚 &bull; 运行时间: 12天 4小时
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
