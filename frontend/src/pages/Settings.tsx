import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Save, HardDrive, Image, CheckCircle, Check, Key, Download, AlertCircle, Bot, Cpu } from 'lucide-react'
import { useApi } from '@/hooks'
import type { ImageSettings, AIConfig } from '@/types'

interface ImageCheckResult {
  exists: boolean
  pulled: boolean
  error?: string
  size_mb?: number
  layers?: number
}

interface RegistryAuth {
  username: string
  password: string
  registry: string
}

export default function Settings() {
  const { get, put, post } = useApi()
  const [settings, setSettings] = useState<ImageSettings>({
    ray_image: '',
    vllm_image: '',
    ray_vllm_image: '',
    use_combined_image: false,
    registry_auth: '',
  })
  const [saved, setSaved] = useState(false)
  const [checking, setChecking] = useState<string | null>(null)
  const [checkResults, setCheckResults] = useState<Record<string, ImageCheckResult>>({})
  const [showRegistryAuth, setShowRegistryAuth] = useState(false)
  const [registryAuth, setRegistryAuth] = useState<RegistryAuth>({
    username: '',
    password: '',
    registry: '',
  })

  // AI Config state
  const [aiConfig, setAiConfig] = useState<AIConfig>({
    api_url: 'https://api.openai.com/v1',
    api_key: '',
    model_name: 'gpt-4o',
    use_local_vllm: false,
    local_vllm_url: 'http://localhost:8000/v1',
    local_model_name: 'llm',
  })
  const [aiSaved, setAiSaved] = useState(false)

  useEffect(() => {
    get<ImageSettings>('/settings').then(data => {
      setSettings(data)
      // Parse registry auth if exists
      if (data.registry_auth) {
        try {
          const authData = JSON.parse(atob(data.registry_auth))
          setRegistryAuth({
            username: authData.username || '',
            password: authData.password || '',
            registry: authData.registry || '',
          })
        } catch (e) {
          console.error('Failed to parse registry auth:', e)
        }
      }
    }).catch(() => {})

    // Load AI config
    get<AIConfig>('/ai/config').then(data => {
      if (data) setAiConfig(data)
    }).catch(() => {})
  }, [])

  const handleSave = async () => {
    try {
      let updatedSettings = { ...settings }
      if (registryAuth.username && registryAuth.password) {
        const authData = {
          username: registryAuth.username,
          password: registryAuth.password,
          registry: registryAuth.registry,
        }
        const encodedAuth = btoa(JSON.stringify(authData))
        updatedSettings = { ...settings, registry_auth: encodedAuth }
      }
      await put<ImageSettings>('/settings/images', updatedSettings)
      setSettings(updatedSettings)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (err) {
      console.error('Save failed:', err)
    }
  }

  const handleCheckImage = async (imageName: string, field: keyof ImageSettings) => {
    if (!settings[field]) {
      alert(`请输入 ${field.replace('_', ' ')} 镜像名称`)
      return
    }

    setChecking(field)
    try {
      const result = await post<ImageCheckResult>('/settings/check-image', {
        image_name: settings[field],
        registry_auth: settings.registry_auth,
      })
      setCheckResults(prev => ({ ...prev, [field]: result }))
    } catch (error) {
      setCheckResults(prev => ({ 
        ...prev, 
        [field]: { 
          exists: false, 
          pulled: false, 
          error: error instanceof Error ? error.message : '检查失败' 
        } 
      }))
    } finally {
      setChecking(null)
    }
  }

  const handleRegistryAuthSave = () => {
    if (registryAuth.username && registryAuth.password) {
      const authData = {
        username: registryAuth.username,
        password: registryAuth.password,
        registry: registryAuth.registry,
      }
      const encodedAuth = btoa(JSON.stringify(authData))
      setSettings({ ...settings, registry_auth: encodedAuth })
      setShowRegistryAuth(false)
    }
  }

  const handleAiConfigSave = async () => {
    await put<AIConfig>('/ai/config', aiConfig)
    setAiSaved(true)
    setTimeout(() => setAiSaved(false), 2500)
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold text-white">系统设置</h2>
        <p className="text-white/40 text-sm mt-1">配置镜像环境与运行参数</p>
      </motion.div>

      {/* Image Configuration */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
            <Image size={20} className="text-blue-400" />
          </div>
          <div>
            <h3 className="font-semibold">镜像配置</h3>
            <p className="text-xs text-white/40">设置 Ray 和 vLLM 的 Docker 镜像</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Ray Image */}
          <div>
            <label className="label">Ray 镜像</label>
            <div className="flex gap-2">
              <input
                className="input-field flex-1"
                value={settings.ray_image}
                onChange={(e) => setSettings({ ...settings, ray_image: e.target.value })}
                placeholder="rayproject/ray:latest"
              />
              <button
                onClick={() => handleCheckImage(settings.ray_image, 'ray_image')}
                disabled={checking === 'ray_image'}
                className="btn-secondary flex items-center gap-1 px-3 py-2 text-sm"
              >
                {checking === 'ray_image' ? (
                  <span className="animate-spin">⟳</span>
                ) : (
                  <Check size={16} />
                )}
                检查
              </button>
            </div>
            <p className="text-[10px] text-white/25 mt-1">用于创建纯 Ray 集群</p>
            {checkResults.ray_image && (
              <div className={`mt-2 p-2 rounded-lg text-xs ${
                checkResults.ray_image.exists 
                  ? 'bg-green-500/10 text-green-400 border border-green-500/20' 
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {checkResults.ray_image.exists ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle size={14} />
                    <span>
                      镜像已存在
                      {checkResults.ray_image.pulled && ' (已拉取)'}
                      {checkResults.ray_image.size_mb && ` - ${checkResults.ray_image.size_mb} MB`}
                      {checkResults.ray_image.layers && ` - ${checkResults.ray_image.layers} 层`}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <AlertCircle size={14} />
                    <span>{checkResults.ray_image.error || '镜像不存在'}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* vLLM Image */}
          <div>
            <label className="label">vLLM 镜像</label>
            <div className="flex gap-2">
              <input
                className="input-field flex-1"
                value={settings.vllm_image}
                onChange={(e) => setSettings({ ...settings, vllm_image: e.target.value })}
                placeholder="vllm/vllm-openai:latest"
              />
              <button
                onClick={() => handleCheckImage(settings.vllm_image, 'vllm_image')}
                disabled={checking === 'vllm_image'}
                className="btn-secondary flex items-center gap-1 px-3 py-2 text-sm"
              >
                {checking === 'vllm_image' ? (
                  <span className="animate-spin">⟳</span>
                ) : (
                  <Check size={16} />
                )}
                检查
              </button>
            </div>
            <p className="text-[10px] text-white/25 mt-1">用于独立启动模型</p>
            {checkResults.vllm_image && (
              <div className={`mt-2 p-2 rounded-lg text-xs ${
                checkResults.vllm_image.exists 
                  ? 'bg-green-500/10 text-green-400 border border-green-500/20' 
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {checkResults.vllm_image.exists ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle size={14} />
                    <span>
                      镜像已存在
                      {checkResults.vllm_image.pulled && ' (已拉取)'}
                      {checkResults.vllm_image.size_mb && ` - ${checkResults.vllm_image.size_mb} MB`}
                      {checkResults.vllm_image.layers && ` - ${checkResults.vllm_image.layers} 层`}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <AlertCircle size={14} />
                    <span>{checkResults.vllm_image.error || '镜像不存在'}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Ray + vLLM Combined Image */}
          <div>
            <label className="label">Ray + vLLM 合并镜像</label>
            <div className="flex gap-2">
              <input
                className="input-field flex-1"
                value={settings.ray_vllm_image}
                onChange={(e) => setSettings({ ...settings, ray_vllm_image: e.target.value })}
                placeholder="your-registry/ray-vllm:latest"
              />
              <button
                onClick={() => handleCheckImage(settings.ray_vllm_image, 'ray_vllm_image')}
                disabled={checking === 'ray_vllm_image'}
                className="btn-secondary flex items-center gap-1 px-3 py-2 text-sm"
              >
                {checking === 'ray_vllm_image' ? (
                  <span className="animate-spin">⟳</span>
                ) : (
                  <Check size={16} />
                )}
                检查
              </button>
            </div>
            <p className="text-[10px] text-white/25 mt-1">同时包含 Ray 和 vLLM，集群容器中直接启动模型</p>
            {checkResults.ray_vllm_image && (
              <div className={`mt-2 p-2 rounded-lg text-xs ${
                checkResults.ray_vllm_image.exists 
                  ? 'bg-green-500/10 text-green-400 border border-green-500/20' 
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {checkResults.ray_vllm_image.exists ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle size={14} />
                    <span>
                      镜像已存在
                      {checkResults.ray_vllm_image.pulled && ' (已拉取)'}
                      {checkResults.ray_vllm_image.size_mb && ` - ${checkResults.ray_vllm_image.size_mb} MB`}
                      {checkResults.ray_vllm_image.layers && ` - ${checkResults.ray_vllm_image.layers} 层`}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <AlertCircle size={14} />
                    <span>{checkResults.ray_vllm_image.error || '镜像不存在'}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Registry Auth Section */}
          <div className="border-t border-white/5 pt-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Key size={16} className="text-yellow-400" />
                <span className="text-sm font-medium">镜像仓库认证</span>
              </div>
              <button
                onClick={() => setShowRegistryAuth(!showRegistryAuth)}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                {showRegistryAuth ? '收起' : '配置'}
              </button>
            </div>
            
            {showRegistryAuth && (
              <div className="space-y-3 p-4 rounded-xl bg-white/[0.03] border border-white/5">
                <div>
                  <label className="text-xs text-white/60 mb-1 block">仓库地址</label>
                  <input
                    className="input-field"
                    value={registryAuth.registry}
                    onChange={(e) => setRegistryAuth({ ...registryAuth, registry: e.target.value })}
                    placeholder="registry.example.com (可选)"
                  />
                </div>
                <div>
                  <label className="text-xs text-white/60 mb-1 block">用户名</label>
                  <input
                    className="input-field"
                    value={registryAuth.username}
                    onChange={(e) => setRegistryAuth({ ...registryAuth, username: e.target.value })}
                    placeholder="username"
                  />
                </div>
                <div>
                  <label className="text-xs text-white/60 mb-1 block">密码</label>
                  <input
                    type="password"
                    className="input-field"
                    value={registryAuth.password}
                    onChange={(e) => setRegistryAuth({ ...registryAuth, password: e.target.value })}
                    placeholder="••••••••"
                  />
                </div>
                <button
                  onClick={handleRegistryAuthSave}
                  className="btn-secondary flex items-center gap-1 px-3 py-1.5 text-xs"
                >
                  <Save size={14} />
                  保存认证信息
                </button>
              </div>
            )}
            
            {registryAuth.username && !showRegistryAuth && (
              <div className="flex items-center gap-2 text-xs text-green-400">
                <CheckCircle size={12} />
                <span>已配置认证: {registryAuth.username}@{registryAuth.registry || '默认仓库'}</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/5">
            <input
              type="checkbox"
              id="combined"
              checked={settings.use_combined_image}
              onChange={(e) => setSettings({ ...settings, use_combined_image: e.target.checked })}
              className="w-4 h-4 rounded accent-primary-500"
            />
            <div>
              <label htmlFor="combined" className="text-sm font-medium cursor-pointer">
                使用 Ray + vLLM 合并镜像
              </label>
              <p className="text-[10px] text-white/40 mt-0.5">
                开启后，创建集群和启动模型都使用合并镜像，模型将在集群容器内直接启动
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* AI Configuration */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="card space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
            <Bot size={20} className="text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold">AI 配置</h3>
            <p className="text-xs text-white/40">配置 Dashboard AI 助手的模型后端</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/5">
            <input
              type="checkbox"
              id="useLocalVllm"
              checked={aiConfig.use_local_vllm}
              onChange={(e) => setAiConfig({ ...aiConfig, use_local_vllm: e.target.checked })}
              className="w-4 h-4 rounded accent-primary-500"
            />
            <div>
              <label htmlFor="useLocalVllm" className="text-sm font-medium cursor-pointer flex items-center gap-1.5">
                <Cpu size={14} className="text-purple-400" />
                使用本地 VLLM 部署的模型
              </label>
              <p className="text-[10px] text-white/40 mt-0.5">
                使用本地 VLLM 推理服务作为 AI 助手后端
              </p>
            </div>
          </div>

          {aiConfig.use_local_vllm ? (
            <>
              <div>
                <label className="label">本地 VLLM API 地址</label>
                <input
                  className="input-field"
                  value={aiConfig.local_vllm_url || ''}
                  onChange={(e) => setAiConfig({ ...aiConfig, local_vllm_url: e.target.value })}
                  placeholder="http://localhost:8000/v1"
                />
              </div>
              <div>
                <label className="label">本地模型名称</label>
                <input
                  className="input-field"
                  value={aiConfig.local_model_name || ''}
                  onChange={(e) => setAiConfig({ ...aiConfig, local_model_name: e.target.value })}
                  placeholder="llm"
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="label">API 地址</label>
                <input
                  className="input-field"
                  value={aiConfig.api_url}
                  onChange={(e) => setAiConfig({ ...aiConfig, api_url: e.target.value })}
                  placeholder="https://api.openai.com/v1"
                />
              </div>
              <div>
                <label className="label">API 密钥</label>
                <input
                  type="password"
                  className="input-field"
                  value={aiConfig.api_key}
                  onChange={(e) => setAiConfig({ ...aiConfig, api_key: e.target.value })}
                  placeholder="sk-..."
                />
              </div>
              <div>
                <label className="label">模型名称</label>
                <input
                  className="input-field"
                  value={aiConfig.model_name}
                  onChange={(e) => setAiConfig({ ...aiConfig, model_name: e.target.value })}
                  placeholder="gpt-4o"
                />
              </div>
            </>
          )}

          <button
            onClick={handleAiConfigSave}
            className={`btn-secondary flex items-center gap-2 ${aiSaved ? 'bg-green-600 hover:bg-green-500' : ''}`}
          >
            {aiSaved ? <CheckCircle size={16} /> : <Save size={16} />}
            {aiSaved ? '已保存' : '保存 AI 配置'}
          </button>
        </div>
      </motion.div>

      {/* Docker Status */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="card">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center">
            <HardDrive size={20} className="text-green-400" />
          </div>
          <div>
            <h3 className="font-semibold">Docker 状态</h3>
            <p className="text-xs text-green-400 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              服务运行中 (x86/AMD64)
            </p>
          </div>
        </div>
      </motion.div>

      {/* Save Button */}
      <motion.button
        onClick={handleSave}
        whileTap={{ scale: 0.97 }}
        className={`btn-primary flex items-center gap-2 ${saved ? 'bg-green-600 hover:bg-green-500' : ''}`}
      >
        {saved ? <CheckCircle size={18} /> : <Save size={18} />}
        {saved ? '已保存' : '保存设置'}
      </motion.button>
    </div>
  )
}