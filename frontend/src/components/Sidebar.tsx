import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Server,
  Box,
  Gauge,
  ScrollText,
  Settings,
  Download,
  Activity,
  ShoppingBag,
  BarChart3,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/cluster', icon: Server, label: '集群管理' },
  { to: '/models', icon: Box, label: '模型服务' },
  { to: '/download', icon: Download, label: '下载模型' },
  { to: '/benchmark', icon: Gauge, label: '性能测试' },
  { to: '/logs', icon: ScrollText, label: '实时日志' },
  { to: '/audit-logs', icon: Activity, label: '审计日志' },
  { to: '/marketplace', icon: ShoppingBag, label: '模型市场' },
  { to: '/ab-testing', icon: BarChart3, label: 'A/B测试' },
  { to: '/settings', icon: Settings, label: '系统设置' },
]

export default function Sidebar() {
  return (
    <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
              isActive
                ? 'bg-primary-600/20 text-primary-300 border border-primary-500/20'
                : 'text-white/50 hover:text-white hover:bg-white/5 border border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <item.icon
                size={18}
                className={isActive ? 'text-primary-400' : 'text-white/30'}
              />
              <span>{item.label}</span>
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-400"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

