import { ReactNode } from 'react'
import { motion } from 'framer-motion'

interface HolographicDisplayProps {
  children: ReactNode
  title?: string
  intensity?: 'low' | 'medium' | 'high'
  className?: string
}

export default function HolographicDisplay({ 
  children, 
  title, 
  intensity = 'medium',
  className = '' 
}: HolographicDisplayProps) {
  const intensityMap = {
    low: 'opacity-30',
    medium: 'opacity-50',
    high: 'opacity-70'
  }
  
  return (
    <div className={`relative ${className}`}>
      {/* 全息背景 */}
      <div className="absolute inset-0 rounded-2xl overflow-hidden">
        <div className={`absolute inset-0 bg-gradient-to-br from-cyan-500/10 to-purple-500/10 ${intensityMap[intensity]}`} />
        
        {/* 扫描线 */}
        <div className="absolute inset-0">
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent animate-scanline" />
          <div className="absolute top-1/4 left-0 right-0 h-px bg-gradient-to-r from-transparent via-purple-400 to-transparent animate-scanline" style={{ animationDelay: '1s' }} />
          <div className="absolute top-2/4 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent animate-scanline" style={{ animationDelay: '2s' }} />
          <div className="absolute top-3/4 left-0 right-0 h-px bg-gradient-to-r from-transparent via-purple-400 to-transparent animate-scanline" style={{ animationDelay: '3s' }} />
        </div>
        
        {/* 数据流效果 */}
        <div className="absolute inset-0 data-stream" />
      </div>
      
      {/* 内容 */}
      <div className="relative z-10 p-6">
        {title && (
          <div className="flex items-center gap-2 mb-4">
            <div className="w-1 h-4 bg-gradient-to-b from-cyan-400 to-purple-400 rounded-full" />
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            <div className="ml-auto flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-xs text-white/40">LIVE</span>
            </div>
          </div>
        )}
        
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          {children}
        </motion.div>
      </div>
      
      {/* 边框发光 */}
      <div className="absolute inset-0 rounded-2xl border border-cyan-500/20 pointer-events-none" />
      <div className="absolute -inset-1 rounded-2xl border border-purple-500/10 blur-sm pointer-events-none" />
      
      <style>{`
        @keyframes scanline {
          0% { transform: translateY(-100%); opacity: 0; }
          10% { opacity: 0.5; }
          20% { opacity: 0; }
          100% { transform: translateY(400%); opacity: 0; }
        }
        .animate-scanline {
          animation: scanline 4s linear infinite;
        }
      `}</style>
    </div>
  )
}
