import { useState, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X, Cpu, Zap } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import NotificationsCenter from './NotificationsCenter'
import AIAssistant from './AIAssistant'
import ParticlesBackground from './ParticlesBackground'

export default function Layout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const location = useLocation()

  return (
    <div className="flex h-screen overflow-hidden">
      <ParticlesBackground />
      {/* Mobile overlay */}
      <AnimatePresence>
        {!sidebarOpen && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSidebarOpen(true)}
            className="fixed top-4 left-4 z-50 p-2 glass-hover lg:hidden"
          >
            <Menu size={20} />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: sidebarOpen ? 260 : 0, opacity: sidebarOpen ? 1 : 0 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="h-full overflow-hidden border-r border-white/5 bg-surface-900/80 backdrop-blur-xl flex-shrink-0"
      >
        {sidebarOpen && (
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between p-5 border-b border-white/5">
              <Link to="/" className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg shadow-primary-500/25">
                  <Cpu size={18} className="text-white" />
                </div>
                <div>
                  <h1 className="text-sm font-bold text-white">VLLM Cluster</h1>
                  <p className="text-[10px] text-white/40">Dashboard</p>
                </div>
              </Link>
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-1.5 rounded-lg hover:bg-white/5 text-white/40 hover:text-white/80 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <Sidebar />
            <div className="p-5 border-t border-white/5 mt-auto">
              <div className="flex items-center gap-2 text-xs text-white/40">
                <Zap size={12} className="text-primary-400" />
                <span>AMD64 Ready</span>
              </div>
            </div>
          </div>
        )}
      </motion.aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Top bar with notifications and AI assistant */}
        <div className="sticky top-0 z-40 flex items-center justify-end px-6 py-3 bg-surface-900/60 backdrop-blur-xl border-b border-white/5 gap-3">
          <NotificationsCenter />
          <AIAssistant />
        </div>
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  )
}
