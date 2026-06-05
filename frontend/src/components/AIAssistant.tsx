import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Sparkles, Send, X, PanelRightClose, PanelRightOpen } from 'lucide-react'
import type { ChatMessage } from '@/types'

export default function AIAssistant() {
  const [chatOpen, setChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [chatMessages])

  const handleChat = async () => {
    if (!chatInput.trim() || chatLoading) return
    const userMsg: ChatMessage = { role: 'user', content: chatInput }
    setChatMessages(prev => [...prev, userMsg])
    setChatInput('')
    setChatLoading(true)

    const assistantIdx = chatMessages.length + 1
    setChatMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      const resp = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: chatInput, session_id: 'dashboard' }),
      })
      if (!resp.ok) throw new Error('AI 服务不可用')

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No reader')

      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'text') {
              fullContent += data.content
              setChatMessages(prev => {
                const clone = [...prev]
                clone[assistantIdx] = { role: 'assistant', content: fullContent }
                return clone
              })
            } else if (data.type === 'tool_call') {
              setChatMessages(prev => {
                const clone = [...prev]
                clone[assistantIdx] = {
                  role: 'assistant',
                  content: `\uD83D\uDD27 \u6B63\u5728\u6267\u884C: ${data.name}(${JSON.stringify(data.args)}) ...`,
                  toolCall: { name: data.name, args: data.args },
                }
                return clone
              })
            } else if (data.type === 'error') {
              setChatMessages(prev => {
                const clone = [...prev]
                clone[assistantIdx] = { role: 'assistant', content: `\u274C ${data.content}` }
                return clone
              })
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e: any) {
      setChatMessages(prev => {
        const clone = [...prev]
        clone[assistantIdx] = { role: 'assistant', content: `\u274C ${e.message}` }
        return clone
      })
    }
    setChatLoading(false)
  }

  return (
    <>
      {/* Backdrop */}
      <AnimatePresence>
        {chatOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setChatOpen(false)}
            className="fixed inset-0 bg-black/40 z-40"
          />
        )}
      </AnimatePresence>

      {/* Right-side sliding panel */}
      <AnimatePresence>
        {chatOpen && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-[400px] max-w-[90vw] z-50 flex flex-col border-l border-white/10 bg-[#0b1120] shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 bg-white/[0.04] border-b border-white/5 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center">
                  <Sparkles size={16} className="text-primary-400" />
                </div>
                <div>
                  <div className="font-semibold text-white text-sm">AI 助手</div>
                  <div className="text-[10px] text-white/30">可控制平台</div>
                </div>
              </div>
              <div className="flex gap-1">
                <button onClick={() => setChatMessages([])} className="p-1.5 text-white/30 hover:text-white/60 transition-colors rounded-md hover:bg-white/5" title="清空对话">
                  <X size={14} />
                </button>
                <button onClick={() => setChatOpen(false)} className="p-1.5 text-white/40 hover:text-white/70 transition-colors rounded-md hover:bg-white/5">
                  <PanelRightClose size={18} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 text-sm">
              {chatMessages.length === 0 && (
                <div className="text-center text-white/30 py-12">
                  <Bot size={36} className="mx-auto mb-4 opacity-30" />
                  <p className="text-sm mb-1">VLLM 集群 AI 助手</p>
                  <p className="text-xs">可帮你管理集群、启动模型、</p>
                  <p className="text-xs">运行测试和评估性能。</p>
                </div>
              )}
              {chatMessages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
                    msg.role === 'user'
                      ? 'bg-primary-500/20 text-white rounded-br-md'
                      : msg.content.startsWith('\uD83D\uDD27')
                        ? 'bg-yellow-500/10 text-yellow-300/80 rounded-bl-md border border-yellow-500/20 text-xs'
                        : msg.content.startsWith('\u274C')
                          ? 'bg-red-500/10 text-red-300/80 rounded-bl-md border border-red-500/20 text-xs'
                          : 'bg-white/[0.06] text-white/90 rounded-bl-md'
                  }`}>
                    {msg.role === 'assistant' && !msg.content && (
                      <span className="flex gap-1"><span className="w-2 h-2 rounded-full bg-white/30 animate-bounce" /><span className="w-2 h-2 rounded-full bg-white/30 animate-bounce" style={{ animationDelay: '0.15s' }} /><span className="w-2 h-2 rounded-full bg-white/30 animate-bounce" style={{ animationDelay: '0.3s' }} /></span>
                    )}
                    {msg.content}
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-white/5 bg-white/[0.02] shrink-0">
              <div className="flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleChat()}
                  placeholder="输入指令..."
                  className="flex-1 bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/20 outline-none focus:border-primary-500/50 transition-colors"
                  disabled={chatLoading}
                />
                <button
                  onClick={handleChat}
                  disabled={chatLoading || !chatInput.trim()}
                  className="btn-primary p-2 rounded-lg disabled:opacity-40 shrink-0"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Trigger button - right edge, vertically centered */}
      {!chatOpen && (
        <motion.button
          initial={{ x: 8, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          whileHover={{ x: -4 }}
          onClick={() => setChatOpen(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 w-10 h-24 rounded-l-2xl bg-gradient-to-b from-primary-600 to-primary-800 flex flex-col items-center justify-center gap-1.5 hover:shadow-lg hover:shadow-primary-500/20 transition-all z-30 group"
          title="AI 助手"
        >
          <PanelRightOpen size={16} className="text-white/80 group-hover:text-white transition-colors" />
          <span className="text-[9px] text-white/60 group-hover:text-white/80 transition-colors writing-vertical">AI</span>
        </motion.button>
      )}
    </>
  )
}
