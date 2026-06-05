import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react'
import type { ProgressStep } from '@/types'

interface ProgressTrackerProps {
  steps: ProgressStep[]
  currentStep: number
  totalSteps: number
  percentage: number
  elapsedSeconds: number
  title?: string
}

const ProgressTracker: React.FC<ProgressTrackerProps> = ({
  steps,
  currentStep,
  totalSteps,
  percentage,
  elapsedSeconds,
  title = '进度跟踪'
}) => {
  const getStepIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} className="text-green-400" />
      case 'failed':
        return <XCircle size={16} className="text-red-400" />
      case 'in_progress':
        return <Clock size={16} className="text-blue-400 animate-spin" />
      default:
        return <AlertCircle size={16} className="text-gray-400" />
    }
  }

  const getStepColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'border-green-500/20 bg-green-500/5'
      case 'failed':
        return 'border-red-500/20 bg-red-500/5'
      case 'in_progress':
        return 'border-blue-500/20 bg-blue-500/5'
      default:
        return 'border-white/10 bg-white/[0.02]'
    }
  }

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="text-xs text-white/40">
            步骤 {currentStep}/{totalSteps} • 耗时 {elapsedSeconds}s
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">{percentage.toFixed(1)}%</div>
          <p className="text-xs text-white/40">完成度</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="relative h-2 bg-white/5 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-full"
        />
      </div>

      {/* Steps List */}
      <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
        <AnimatePresence>
          {steps.map((step, index) => (
            <motion.div
              key={step.step}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className={`p-3 rounded-lg border ${getStepColor(step.status)}`}
            >
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  {getStepIcon(step.status)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate">
                      {step.step}
                    </span>
                    <span className="text-xs text-white/40">
                      {step.percentage.toFixed(1)}%
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-white/60 space-y-1">
                    {step.status === 'completed' && step.details && (
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(step.details).map(([key, value]) => (
                          <span
                            key={key}
                            className="px-1.5 py-0.5 bg-white/5 rounded text-[10px]"
                          >
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                    {step.status === 'failed' && step.details?.error && (
                      <div className="text-red-400">
                        {step.details.error}
                      </div>
                    )}
                    {step.status === 'in_progress' && step.details && (
                      <div className="text-blue-400">
                        进行中...
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Status Summary */}
      <div className="pt-3 border-t border-white/5">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-400" />
              <span className="text-white/60">已完成</span>
              <span className="text-white">
                {steps.filter(s => s.status === 'completed').length}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-blue-400" />
              <span className="text-white/60">进行中</span>
              <span className="text-white">
                {steps.filter(s => s.status === 'in_progress').length}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-red-400" />
              <span className="text-white/60">失败</span>
              <span className="text-white">
                {steps.filter(s => s.status === 'failed').length}
              </span>
            </div>
          </div>
          <div className="text-white/40">
            预计剩余时间: {percentage > 0 ? Math.max(0, Math.round((elapsedSeconds / percentage) * (100 - percentage))) : "计算中..."}s
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProgressTracker