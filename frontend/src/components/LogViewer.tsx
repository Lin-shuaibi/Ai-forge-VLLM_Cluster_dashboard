import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react'
import type { LogEntry } from '@/types'

interface Props {
  logs: LogEntry[]
  connected: boolean
  maxHeight?: string
}

const levelIcon = {
  info: Info,
  success: CheckCircle,
  warn: AlertTriangle,
  error: AlertCircle,
}

const levelColor = {
  info: 'text-blue-400',
  success: 'text-green-400',
  warn: 'text-yellow-400',
  error: 'text-red-400',
}

export default function LogViewer({ logs, connected, maxHeight = '400px' }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length])

  return (
    <div className="glass overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <span className="text-sm font-medium text-white/80">实时日志</span>
        <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-green-400' : 'text-red-400'}`}>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
          {connected ? '已连接' : '未连接'}
        </span>
      </div>
      <div className="p-3 overflow-y-auto font-mono text-xs leading-relaxed" style={{ maxHeight }}>
        <AnimatePresence initial={false}>
          {logs.map((log, i) => {
            const Icon = levelIcon[log.level] || Info
            return (
              <motion.div
                key={`${log.timestamp}-${i}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
                className="flex items-start gap-2 py-0.5"
              >
                <Icon size={12} className={`mt-0.5 flex-shrink-0 ${levelColor[log.level]}`} />
                <span className="text-white/30 flex-shrink-0">
                  {new Date(log.timestamp * 1000).toLocaleTimeString()}
                </span>
                <span className={levelColor[log.level]}>{log.message}</span>
              </motion.div>
            )
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
        {logs.length === 0 && (
          <div className="text-white/25 text-center py-8">等待日志输出...</div>
        )}
      </div>
    </div>
  )
}