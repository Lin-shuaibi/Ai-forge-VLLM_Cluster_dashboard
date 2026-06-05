import { ButtonHTMLAttributes, ReactNode } from 'react'
import { motion } from 'framer-motion'

interface NeonButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  glow?: boolean
  fullWidth?: boolean
}

export default function NeonButton({
  children,
  variant = 'primary',
  size = 'md',
  glow = true,
  fullWidth = false,
  className = '',
  disabled,
  ...props
}: NeonButtonProps) {
  const variantClasses = {
    primary: 'bg-gradient-to-r from-cyan-500 to-purple-600',
    secondary: 'bg-gradient-to-r from-gray-800 to-gray-900 border border-gray-700',
    danger: 'bg-gradient-to-r from-red-600 to-pink-600'
  }
  
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2.5',
    lg: 'px-6 py-3 text-lg'
  }
  
  const glowEffect = glow ? {
    primary: 'shadow-[0_0_20px_rgba(0,217,255,0.4)] hover:shadow-[0_0_30px_rgba(0,217,255,0.6)]',
    secondary: 'shadow-[0_0_10px_rgba(100,100,100,0.3)] hover:shadow-[0_0_20px_rgba(100,100,100,0.4)]',
    danger: 'shadow-[0_0_20px_rgba(255,0,0,0.4)] hover:shadow-[0_0_30px_rgba(255,0,0,0.6)]'
  }[variant] : ''
  
  return (
    <motion.button
      whileHover={{ scale: disabled ? 1 : 1.05 }}
      whileTap={{ scale: disabled ? 1 : 0.95 }}
      className={`
        relative rounded-xl font-medium
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${glowEffect}
        ${fullWidth ? 'w-full' : ''}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${className}
        overflow-hidden
        transition-all duration-200
      `}
      disabled={disabled}
      {...props as any}
    >
      {/* 流光效果 */}
      {!disabled && (
        <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
      )}
      
      {/* 内容 */}
      <span className="relative z-10 text-white font-medium">
        {children}
      </span>
      
      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        .animate-shimmer {
          animation: shimmer 2s infinite;
        }
      `}</style>
    </motion.button>
  )
}
