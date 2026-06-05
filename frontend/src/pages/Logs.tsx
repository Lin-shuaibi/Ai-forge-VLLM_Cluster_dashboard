import { useState, useMemo, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ScrollText, Filter, Search, Download, Copy, XCircle, AlertCircle, Info } from 'lucide-react'
import { useWebSocket } from '@/hooks'
import LogViewer from '@/components/LogViewer'

type LogLevel = 'all' | 'info' | 'warn' | 'error' | 'debug'
type LogChannel = 'global' | 'cluster' | 'model' | 'download' | 'benchmark'

export default function Logs() {
  const [channel, setChannel] = useState<LogChannel>('global')
  const [level, setLevel] = useState<LogLevel>('all')
  const [search, setSearch] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const { logs, connected } = useWebSocket(`/ws/logs/${channel}`)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      if (level !== 'all' && !log.message.toLowerCase().includes(level)) return false
      if (search && !log.message.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [logs, level, search])

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [filteredLogs, autoScroll])

  const handleDownload = () => {
    const blob = new Blob([filteredLogs.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${channel}-${new Date().toISOString().slice(0, 10)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(filteredLogs.join('\n'))
      .then(() => alert('日志已复制到剪贴板'))
      .catch(err => console.error('复制失败:', err))
  }

  const handleClear = () => {
    // 需要后端实现清空日志接口
    // fetch(`/api/logs/clear/${channel}`, { method: 'POST' })
  }

  return (
    <div className="p-6 space-y-6">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <ScrollText size={24} className="text-primary-400" />
          实时日志
        </h2>
        <p className="text-white/40 text-sm mt-1">全局系统日志流，实时监控所有操作</p>
      </motion.div>

      {/* 控制栏 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex flex-wrap gap-3 items-center"
      >
        {/* 频道选择 */}
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-white/40" />
          {(['global', 'cluster', 'model', 'download', 'benchmark'] as LogChannel[]).map(ch => (
            <button
              key={ch}
              onClick={() => setChannel(ch)}
              className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                channel === ch ? 'bg-primary-600/20 text-primary-300 border border-primary-500/30' : 'text-white/40 hover:text-white/70'
              }`}
            >
              {ch === 'global' ? '全局' : ch === 'cluster' ? '集群' : ch === 'model' ? '模型' : ch === 'download' ? '下载' : '压测'}
            </button>
          ))}
        </div>

        {/* 级别过滤 */}
        <div className="flex items-center gap-2">
          <AlertCircle size={16} className="text-white/40" />
          {(['all', 'info', 'warn', 'error', 'debug'] as LogLevel[]).map(lvl => (
            <button
              key={lvl}
              onClick={() => setLevel(lvl)}
              className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                level === lvl ? 'bg-gray-600/30 text-white border border-gray-500/30' : 'text-white/40 hover:text-white/70'
              }`}
            >
              {lvl === 'all' ? '全部' : lvl === 'info' ? '信息' : lvl === 'warn' ? '警告' : lvl === 'error' ? '错误' : '调试'}
            </button>
          ))}
        </div>

        {/* 搜索框 */}
        <div className="flex-1 max-w-xs">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-white/40" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索日志..."
              className="w-full pl-10 pr-3 py-1.5 bg-gray-800/30 border border-gray-700 rounded-lg text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
            />
          </div>
        </div>

        {/* 工具按钮 */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            className="p-1.5 text-white/60 hover:text-white bg-gray-800/30 rounded-lg hover:bg-gray-700/30 transition-colors"
            title="下载日志"
          >
            <Download size={16} />
          </button>
          <button
            onClick={handleCopy}
            className="p-1.5 text-white/60 hover:text-white bg-gray-800/30 rounded-lg hover:bg-gray-700/30 transition-colors"
            title="复制日志"
          >
            <Copy size={16} />
          </button>
          <button
            onClick={handleClear}
            className="p-1.5 text-white/60 hover:text-white bg-gray-800/30 rounded-lg hover:bg-gray-700/30 transition-colors"
            title="清空日志"
          >
            <XCircle size={16} />
          </button>
          <label className="flex items-center gap-2 text-sm text-white/60 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-gray-600 bg-gray-800/30"
            />
            自动滚动
          </label>
        </div>
      </motion.div>

      {/* 状态栏 */}
      <div className="flex items-center justify-between text-sm text-white/60">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <Info size={14} />
            <span>连接状态: {connected ? <span className="text-green-400">已连接</span> : <span className="text-red-400">断开</span>}</span>
          </div>
          <div>频道: <span className="text-white">{channel}</span></div>
          <div>级别: <span className="text-white">{level}</span></div>
          <div>日志条数: <span className="text-white">{filteredLogs.length}</span></div>
        </div>
        <div className="text-xs">
          {search && <span>搜索: "{search}"</span>}
        </div>
      </div>

      {/* 日志查看器 */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <LogViewer logs={filteredLogs} connected={connected} maxHeight="calc(100vh - 320px)" />
        <div ref={logsEndRef} />
      </motion.div>
    </div>
  )
}
