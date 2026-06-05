import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Gauge, Play, BarChart3, Clock, Zap, Activity, Globe,
  Download, Table, TrendingUp, AlertCircle, CheckCircle2,
  Trash2, CheckSquare, Square, FileText
} from 'lucide-react'
import { useApi, useWebSocket } from '@/hooks'
import type { ModelInfo, BenchmarkInfo } from '@/types'
import LogViewer from '@/components/LogViewer'
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  Legend, Cell, ComposedChart, Area
} from 'recharts'

function parseMetricNumber(val: string | number | undefined): number {
  if (val === undefined || val === null) return 0
  if (typeof val === 'number') return isNaN(val) ? 0 : val
  const num = parseFloat(String(val).replace(/[^0-9.]/g, ''))
  return isNaN(num) ? 0 : num
}

type BenchTab = 'vllm' | 'api'

// ── Comparison Panel ───────────────────────────────────────
function ComparisonPanel({ list, onClose }: { list: BenchmarkInfo[]; onClose: () => void }) {
  const completed = list.filter(b => b.status === 'completed')
  if (completed.length === 0) return null

  const isApi = completed[0]?.type === 'api'

  const barData = completed.map(b => ({
    name: b.model_name + ' (' + b.id.slice(-6) + ')',
    TTFT: Math.round((b as any).ttft_ms || 0),
    TPOT: Math.round((b as any).tpot_ms || 0),
    DecodeTok: Math.round((b as any).decode_tokens_per_second || 0),
    AvgLat: Math.round(b.avg_latency_ms || 0),
    QPS: Math.round((b as any).requests_per_second || 0),
    TokS: Math.round((b as any).tokens_per_second || 0),
  }))

  const scatterData = completed.map(b => ({
    x: Math.round((b as any).ttft_ms || 0),
    y: Math.round((b as any).decode_tokens_per_second || 0),
    name: b.model_name + ' (' + b.id.slice(-6) + ')',
  }))

  const handleExport = () => {
    const rows = completed.map(b => {
      if (isApi) {
        return {
          '模型': b.model_name,
          '测试ID': b.id,
          'API地址': (b as any).api_url || '-',
          'TTFT(ms)': (b as any).ttft_ms?.toFixed(1) || '-',
          'TPOT(ms)': (b as any).tpot_ms?.toFixed(1) || '-',
          '解码速度(tok/s)': (b as any).decode_tokens_per_second?.toFixed(1) || '-',
          '总输出Token': (b as any).total_output_tokens || '-',
          '总耗时(ms)': (b as any).total_elapsed_ms?.toFixed(0) || '-',
          '平均延迟(ms)': b.avg_latency_ms?.toFixed(1) || '-',
          'QPS': (b as any).requests_per_second?.toFixed(1) || '-',
          'Tokens/s': (b as any).tokens_per_second?.toFixed(1) || '-',
          '总请求数': (b as any).total_requests || '-',
          '成功数': (b as any).success_count || '-',
          '失败数': (b as any).fail_count || '-',
        }
      } else {
        return {
          '模型': b.model_name,
          '测试ID': b.id,
          '平均延迟(ms)': b.avg_latency_ms?.toFixed(1) || '-',
        }
      }
    })
    const html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>性能对比报告</title>' +
      '<style>body{font-family:"Segoe UI",sans-serif;max-width:1200px;margin:40px auto;padding:20px;color:#1e293b}' +
      'h1{color:#6366f1}table{width:100%;border-collapse:collapse;margin:20px 0}' +
      'th{background:#6366f1;color:#fff;padding:10px;text-align:left}' +
      'td{padding:10px;border-bottom:1px solid #e2e8f0}' +
      'tr:nth-child(even){background:#f8fafc}' +
      '.footer{margin-top:40px;color:#94a3b8;font-size:12px}</style></head><body>' +
      '<h1>性能对比报告</h1><p>共 ' + completed.length + ' 条记录 | 类型: ' + (isApi ? 'API' : 'vLLM') + '</p>' +
      '<table><thead><tr>' + Object.keys(rows[0] || {}).map(k => '<th>' + k + '</th>').join('') + '</tr></thead><tbody>' +
      rows.map(r => '<tr>' + Object.values(r).map(v => '<td>' + v + '</td>').join('') + '</tr>').join('') +
      '</tbody></table><div class="footer">生成于 vLLM Dashboard · 性能对比模块</div></body></html>'
    const blob = new Blob([html], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'benchmark-comparison-' + Date.now() + '.html'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="card space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <BarChart3 size={18} className="text-primary-400" />
          汇总对比 ({completed.length} 条记录)
        </h3>
        <div className="flex gap-2">
          <button onClick={handleExport} className="btn-secondary text-xs flex items-center gap-1">
            <FileText size={14} /> 导出对比 (HTML)
          </button>
          <button onClick={onClose} className="btn-secondary text-xs">关闭</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-green-400" /> 核心指标对比
          </h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="name" tick={{ fill: '#ffffff60', fontSize: 10 }} />
              <YAxis tick={{ fill: '#ffffff30', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', color: '#fff' }} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              <Bar dataKey="TTFT" name="TTFT(ms)" fill="#818cf8" radius={[6, 6, 0, 0]} />
              <Bar dataKey="TPOT" name="TPOT(ms)" fill="#22c55e" radius={[6, 6, 0, 0]} />
              <Bar dataKey="DecodeTok" name="解码速度(tok/s)" fill="#f59e0b" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Activity size={16} className="text-blue-400" /> TTFT vs 解码速度
          </h4>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="x" name="TTFT(ms)" tick={{ fill: '#ffffff60', fontSize: 10 }} label={{ value: 'TTFT (ms)', fill: '#ffffff40', fontSize: 11, position: 'bottom', offset: -4 }} />
              <YAxis dataKey="y" name="解码速度(tok/s)" tick={{ fill: '#ffffff30', fontSize: 10 }} label={{ value: '解码速度 (tok/s)', fill: '#ffffff40', fontSize: 11, angle: -90, position: 'left' }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', color: '#fff' }}
                formatter={(value: number, name: string) => [value.toFixed(0), name === 'x' ? 'TTFT(ms)' : '解码速度(tok/s)']}
              />
              <Scatter data={scatterData} fill="#6366f1" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        <div className="card lg:col-span-2">
          <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Zap size={16} className="text-yellow-400" /> 吞吐量对比
          </h4>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="name" tick={{ fill: '#ffffff60', fontSize: 10 }} />
              <YAxis tick={{ fill: '#ffffff30', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', color: '#fff' }} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              <Bar dataKey="QPS" name="QPS" fill="#6366f1" radius={[6, 6, 0, 0]} />
              <Bar dataKey="TokS" name="Tokens/s" fill="#22c55e" radius={[6, 6, 0, 0]} />
              <Bar dataKey="AvgLat" name="平均延迟(ms)" fill="#ef4444" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-white/40 border-b border-white/10">
              <th className="text-left py-2 px-3">模型</th>
              <th className="text-left py-2 px-3">TTFT (ms)</th>
              <th className="text-left py-2 px-3">TPOT (ms)</th>
              <th className="text-left py-2 px-3">解码速度 (tok/s)</th>
              <th className="text-left py-2 px-3">总输出Token</th>
              <th className="text-left py-2 px-3">平均延迟 (ms)</th>
              <th className="text-left py-2 px-3">QPS</th>
              <th className="text-left py-2 px-3">Tokens/s</th>
              <th className="text-left py-2 px-3">成功/总请求</th>
              <th className="text-left py-2 px-3">状态</th>
            </tr>
          </thead>
          <tbody>
            {completed.map((b, i) => (
              <tr key={b.id} className={'border-b border-white/5 ' + (i % 2 === 0 ? 'bg-white/[0.02]' : '')}>
                <td className="py-2 px-3 font-medium">{b.model_name}</td>
                <td className="py-2 px-3 font-mono text-blue-300">{(b as any).ttft_ms?.toFixed(0) || '-'}</td>
                <td className="py-2 px-3 font-mono text-green-300">{(b as any).tpot_ms?.toFixed(0) || '-'}</td>
                <td className="py-2 px-3 font-mono text-yellow-300">{(b as any).decode_tokens_per_second?.toFixed(1) || '-'}</td>
                <td className="py-2 px-3 font-mono">{(b as any).total_output_tokens || '-'}</td>
                <td className="py-2 px-3 font-mono text-red-300">{b.avg_latency_ms?.toFixed(0) || '-'}</td>
                <td className="py-2 px-3 font-mono">{(b as any).requests_per_second?.toFixed(1) || '-'}</td>
                <td className="py-2 px-3 font-mono">{(b as any).tokens_per_second?.toFixed(1) || '-'}</td>
                <td className="py-2 px-3 font-mono">{(b as any).success_count || '-'}/{(b as any).total_requests || '-'}</td>
                <td className="py-2 px-3">
                  <span className={'text-[10px] px-2 py-0.5 rounded-full font-mono ' +
                    (b.status === 'completed' ? 'bg-green-500/20 text-green-300' : 'bg-yellow-500/20 text-yellow-300')
                  }>{b.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}

// ── VLLM Result Panel ──────────────────────────────────────
function VllmResultPanel({ result }: { result: BenchmarkInfo['result'] }) {
  if (!result?.metrics) return null
  const metrics = result.metrics

  const latencyData = [
    { name: 'TTFT Mean', value: parseMetricNumber(metrics.mean_ttft_ms) },
    { name: 'TTFT Med', value: parseMetricNumber(metrics.median_ttft_ms) },
    { name: 'TTFT P99', value: parseMetricNumber(metrics.p99_ttft_ms) },
    { name: 'TPOT Mean', value: parseMetricNumber(metrics.mean_tpot_ms) },
    { name: 'TPOT P99', value: parseMetricNumber(metrics.p99_tpot_ms) },
    { name: 'ITL Mean', value: parseMetricNumber(metrics.mean_itl_ms) },
  ]

  const throughputData = [
    { name: 'Req/s', value: parseMetricNumber(metrics.request_throughput) },
    { name: 'Tok/s', value: parseMetricNumber(metrics.token_throughput) },
    { name: 'Total Tok/s', value: parseMetricNumber(metrics.total_token_throughput) },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Clock size={16} className="text-blue-400" /> 延迟指标 (ms)
          </h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={latencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="name" tick={{ fill: '#ffffff60', fontSize: 10 }} />
              <YAxis tick={{ fill: '#ffffff30', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', color: '#fff' }} />
              <Bar dataKey="value" fill="#6366f1" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Zap size={16} className="text-yellow-400" /> 吞吐量指标
          </h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={throughputData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="name" tick={{ fill: '#ffffff60', fontSize: 10 }} />
              <YAxis tick={{ fill: '#ffffff30', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', color: '#fff' }} />
              <Bar dataKey="value" fill="#22c55e" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

// ── API Result Panel ───────────────────────────────────────
function ApiResultPanel({ bench }: { bench: BenchmarkInfo }) {
  if (!(bench as any).ttft_ms && !(bench as any).avg_latency_ms) return null
  const r = bench as any

  const latencyData = [
    { name: 'TTFT (ms)', value: parseMetricNumber(r.ttft_ms) },
    { name: 'TPOT (ms)', value: parseMetricNumber(r.tpot_ms) },
    { name: '平均延迟 (ms)', value: r.avg_latency_ms ?? '-' },
  ]

  const throughputData = [
    { name: '解码速度 (tok/s)', value: parseMetricNumber(r.decode_tokens_per_second) },
    { name: 'QPS', value: parseMetricNumber(r.requests_per_second) },
    { name: 'Tokens/s', value: parseMetricNumber(r.tokens_per_second) },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Clock size={16} className="text-blue-400" /> 延迟指标
          </h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={latencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="name" tick={{ fill: '#ffffff60', fontSize: 10 }} />
              <YAxis tick={{ fill: '#ffffff30', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', color: '#fff' }} />
              <Bar dataKey="value" fill="#6366f1" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Zap size={16} className="text-yellow-400" /> 吞吐量指标
          </h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={throughputData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis dataKey="name" tick={{ fill: '#ffffff60', fontSize: 10 }} />
              <YAxis tick={{ fill: '#ffffff30', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', color: '#fff' }} />
              <Bar dataKey="value" fill="#22c55e" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card">
          <h4 className="text-sm font-semibold mb-2">请求统计</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-white/60">总请求数</span>
              <span className="font-mono">{r.total_requests || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">成功数</span>
              <span className="font-mono text-green-400">{r.success_count || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">失败数</span>
              <span className="font-mono text-red-400">{r.fail_count || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">成功率</span>
              <span className="font-mono">
                {r.total_requests ? ((r.success_count || 0) / r.total_requests * 100).toFixed(1) : 0}%
              </span>
            </div>
          </div>
        </div>

        <div className="card">
          <h4 className="text-sm font-semibold mb-2">Token 统计</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-white/60">总输出 Token</span>
              <span className="font-mono">{r.total_output_tokens || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">总耗时 (ms)</span>
              <span className="font-mono">{r.total_elapsed_ms?.toFixed(0) || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">平均每 Token (ms)</span>
              <span className="font-mono">
                {r.total_output_tokens ? (r.total_elapsed_ms || 0) / r.total_output_tokens : 0}
              </span>
            </div>
          </div>
        </div>

        <div className="card">
          <h4 className="text-sm font-semibold mb-2">性能指标</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-white/60">TTFT (ms)</span>
              <span className="font-mono text-blue-300">{r.ttft_ms?.toFixed(1) || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">TPOT (ms)</span>
              <span className="font-mono text-green-300">{r.tpot_ms?.toFixed(1) || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-white/60">解码速度 (tok/s)</span>
              <span className="font-mono text-yellow-300">{r.decode_tokens_per_second?.toFixed(1) || '-'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────
export default function Benchmark() {
  const { get, post, del } = useApi()
  const [models, setModels] = useState<ModelInfo[]>([])
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([])
  const [tab, setTab] = useState<BenchTab>('vllm')
  const [showForm, setShowForm] = useState(false)
  const [activeBenchLog, setActiveBenchLog] = useState<string | null>(null)
  const [selectedResult, setSelectedResult] = useState<BenchmarkInfo | null>(null)
  const [running, setRunning] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showComparison, setShowComparison] = useState(false)

  // vLLM form state
  const [modelPath, setModelPath] = useState('')
  const [tokenizerPath, setTokenizerPath] = useState('')
  const [datasetName, setDatasetName] = useState('random')
  const [randomInputLen, setRandomInputLen] = useState(2048)
  const [randomOutputLen, setRandomOutputLen] = useState(2048)
  const [numPrompts, setNumPrompts] = useState(5)
  const [trustRemoteCode, setTrustRemoteCode] = useState(true)
  const [ignoreEos, setIgnoreEos] = useState(true)
  const [servedModelName, setServedModelName] = useState('llm')
  const [port, setPort] = useState(8000)
  const [maxConcurrency, setMaxConcurrency] = useState('')

  // API form state
  const [apiUrl, setApiUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiModelName, setApiModelName] = useState('')
  const [apiConcurrency, setApiConcurrency] = useState(1)
  const [apiInputTokens, setApiInputTokens] = useState(256)
  const [apiOutputTokens, setApiOutputTokens] = useState(256)
  const [apiNumRequests, setApiNumRequests] = useState(10)

  const { logs, connected } = useWebSocket(
    activeBenchLog ? `/api/benchmarks/${activeBenchLog}/logs` : null
  )

  const refresh = useCallback(async () => {
    const [m, b] = await Promise.all([
      get<ModelInfo[]>('/models').catch(() => []),
      get<BenchmarkInfo[]>('/benchmarks').catch(() => []),
    ])
    setModels(m || [])
    setBenchmarks((b || []).sort((a, b) => (a.id > b.id ? -1 : 1)))
  }, [])

  useEffect(() => { refresh() }, [])

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const handleSelectAll = useCallback(() => {
    const allIds = benchmarks.map(b => b.id)
    setSelectedIds(prev => prev.size === allIds.length ? new Set() : new Set(allIds))
  }, [benchmarks])

  const handleDeleteSelected = useCallback(async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`确定删除 ${selectedIds.size} 条记录吗？`)) return
    try {
      for (const id of Array.from(selectedIds)) {
        await del(`/benchmarks/${id}`)
      }
      setSelectedIds(new Set())
      refresh()
    } catch (e: any) {
      alert('删除失败: ' + (e?.message || e))
    }
  }, [selectedIds])

  const handleExportSelected = useCallback(() => {
    const selected = benchmarks.filter(b => selectedIds.has(b.id))
    if (selected.length === 0) return
    const rows = selected.map(b => ({
      '模型': b.model_name,
      '测试ID': b.id,
      '类型': b.type,
      '状态': b.status,
      '平均延迟(ms)': b.avg_latency_ms?.toFixed(1) || '-',
      '总输出Token': (b as any).total_output_tokens || '-',
      '总耗时(ms)': (b as any).total_elapsed_ms?.toFixed(0) || '-',
      'TTFT(ms)': (b as any).ttft_ms?.toFixed(1) || '-',
      'TPOT(ms)': (b as any).tpot_ms?.toFixed(1) || '-',
      '解码速度(tok/s)': (b as any).decode_tokens_per_second?.toFixed(1) || '-',
      'QPS': (b as any).requests_per_second?.toFixed(1) || '-',
      'Tokens/s': (b as any).tokens_per_second?.toFixed(1) || '-',
      '总请求数': (b as any).total_requests || '-',
      '成功数': (b as any).success_count || '-',
      '失败数': (b as any).fail_count || '-',
    }))
    const csv = 'data:text/csv;charset=utf-8,' + String.fromCharCode(0xFEFF) +
      Object.keys(rows[0] || {}).join(',') + '\n' +
      rows.map(r => Object.values(r).join(',')).join('\n')
    const a = document.createElement('a')
    a.href = encodeURI(csv)
    a.download = 'benchmark-export-' + Date.now() + '.csv'
    a.click()
  }, [selectedIds, benchmarks])

  const handleRunVllm = async () => {
    if (!modelPath) return
    setRunning(true)
    try {
      const result = await post<{ bench_id: string }>('/benchmarks/vllm/run', {
        model_path: modelPath,
        tokenizer_path: tokenizerPath || undefined,
        dataset_name: datasetName,
        random_input_len: randomInputLen,
        random_output_len: randomOutputLen,
        num_prompts: numPrompts,
        trust_remote_code: trustRemoteCode,
        ignore_eos: ignoreEos,
        served_model_name: servedModelName,
        port: port,
        max_concurrency: maxConcurrency ? parseInt(maxConcurrency) : undefined,
      })
      setActiveBenchLog(result.bench_id)
      setShowForm(false)
      setTimeout(() => refresh(), 500)
    } catch (e: any) {
      alert('测试失败: ' + (e?.message || e))
    }
    setRunning(false)
  }

  const handleRunApi = async () => {
    if (!apiUrl || !apiModelName) return
    setRunning(true)
    try {
      const result = await post<{ bench_id: string }>('/benchmarks/api/run', {
        api_url: apiUrl,
        api_key: apiKey || undefined,
        model_name: apiModelName,
        concurrency: apiConcurrency,
        input_tokens: apiInputTokens,
        output_tokens: apiOutputTokens,
        num_requests: apiNumRequests,
      })
      setActiveBenchLog(result.bench_id)
      setShowForm(false)
      setTimeout(() => refresh(), 500)
    } catch (e: any) {
      alert('测试失败: ' + (e?.message || e))
    }
    setRunning(false)
  }

  const viewResult = (benchId: string) => {
    const bench = benchmarks.find(b => b.id === benchId)
    if (bench) setSelectedResult(bench)
  }

  const exportPDF = (benchId: string) => {
    window.open(`/api/benchmarks/${benchId}/export-report`, '_blank')
  }

  // 防 Tree-shaking
  if (false) {
    const dummy = ComparisonPanel
    console.log(dummy)
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <h2 className="text-2xl font-bold text-white">性能测试</h2>
          <p className="text-white/40 text-sm mt-1">vLLM Bench & 公网API 模型性能压测</p>
        </motion.div>
        <motion.button
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          onClick={() => { setShowForm(!showForm); setSelectedResult(null) }}
          className="btn-primary flex items-center gap-2"
        >
          <Play size={18} />
          创建测试任务
        </motion.button>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 p-1 rounded-xl bg-white/[0.04] w-fit">
        {(['vllm', 'api'] as BenchTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t ? 'bg-primary-500/20 text-primary-400 shadow-lg' : 'text-white/40 hover:text-white/70'
            }`}
          >
            {t === 'vllm' ? 'vLLM Bench' : '公网 API 测试'}
          </button>
        ))}
      </div>

      {/* Form */}
      <AnimatePresence>
        {showForm && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            {tab === 'vllm' ? (
              // ═══ vLLM Bench Form ═══
              <div className="card space-y-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Gauge size={18} className="text-primary-400" />
                  vLLM 性能测试
                </h3>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div>
                    <label className="label">模型路径</label>
                    <input
                      type="text"
                      value={modelPath}
                      onChange={(e) => setModelPath(e.target.value)}
                      className="input-field"
                      placeholder="/path/to/model"
                    />
                  </div>
                  <div>
                    <label className="label">Tokenizer 路径 (可选)</label>
                    <input
                      type="text"
                      value={tokenizerPath}
                      onChange={(e) => setTokenizerPath(e.target.value)}
                      className="input-field"
                      placeholder="/path/to/tokenizer"
                    />
                  </div>
                  <div>
                    <label className="label">数据集</label>
                    <select
                      value={datasetName}
                      onChange={(e) => setDatasetName(e.target.value)}
                      className="input-field"
                    >
                      <option value="random">随机生成</option>
                      <option value="sharegpt">ShareGPT</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">服务模型名称</label>
                    <input
                      type="text"
                      value={servedModelName}
                      onChange={(e) => setServedModelName(e.target.value)}
                      className="input-field"
                      placeholder="llm"
                    />
                  </div>
                  <div>
                    <label className="label">输入长度</label>
                    <input
                      type="number"
                      value={randomInputLen}
                      onChange={(e) => setRandomInputLen(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="100000"
                    />
                  </div>
                  <div>
                    <label className="label">输出长度</label>
                    <input
                      type="number"
                      value={randomOutputLen}
                      onChange={(e) => setRandomOutputLen(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="100000"
                    />
                  </div>
                  <div>
                    <label className="label">提示词数量</label>
                    <input
                      type="number"
                      value={numPrompts}
                      onChange={(e) => setNumPrompts(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="1000"
                    />
                  </div>
                  <div>
                    <label className="label">端口</label>
                    <input
                      type="number"
                      value={port}
                      onChange={(e) => setPort(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="65535"
                    />
                  </div>
                  <div>
                    <label className="label">最大并发数 (可选)</label>
                    <input
                      type="number"
                      value={maxConcurrency}
                      onChange={(e) => setMaxConcurrency(e.target.value)}
                      className="input-field"
                      placeholder="默认自动检测"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="trust-remote-code"
                      checked={trustRemoteCode}
                      onChange={(e) => setTrustRemoteCode(e.target.checked)}
                      className="checkbox"
                    />
                    <label htmlFor="trust-remote-code" className="text-sm">信任远程代码</label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="ignore-eos"
                      checked={ignoreEos}
                      onChange={(e) => setIgnoreEos(e.target.checked)}
                      className="checkbox"
                    />
                    <label htmlFor="ignore-eos" className="text-sm">忽略 EOS Token</label>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button onClick={handleRunVllm} disabled={running || !modelPath} className="btn-primary flex-1 flex items-center justify-center gap-2">
                    {running ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        测试中...
                      </>
                    ) : (
                      <>
                        <Play size={16} />
                        启动 vLLM 测试
                      </>
                    )}
                  </button>
                  <button onClick={() => setShowForm(false)} className="btn-secondary">取消</button>
                </div>
              </div>
            ) : (
              // ═══ API Bench Form ═══
              <div className="card space-y-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Globe size={18} className="text-blue-400" />
                  公网 API 性能测试
                </h3>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="lg:col-span-2">
                    <label className="label">API 地址</label>
                    <input
                      type="text"
                      value={apiUrl}
                      onChange={(e) => setApiUrl(e.target.value)}
                      className="input-field"
                      placeholder="https://api.openai.com/v1/chat/completions"
                    />
                  </div>
                  <div>
                    <label className="label">API Key (可选)</label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="input-field"
                      placeholder="sk-..."
                    />
                  </div>
                  <div>
                    <label className="label">模型名称</label>
                    <input
                      type="text"
                      value={apiModelName}
                      onChange={(e) => setApiModelName(e.target.value)}
                      className="input-field"
                      placeholder="gpt-4"
                    />
                  </div>
                  <div>
                    <label className="label">并发数</label>
                    <input
                      type="number"
                      value={apiConcurrency}
                      onChange={(e) => setApiConcurrency(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="100"
                    />
                  </div>
                  <div>
                    <label className="label">输入 Token 数</label>
                    <input
                      type="number"
                      value={apiInputTokens}
                      onChange={(e) => setApiInputTokens(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="100000"
                    />
                  </div>
                  <div>
                    <label className="label">输出 Token 数</label>
                    <input
                      type="number"
                      value={apiOutputTokens}
                      onChange={(e) => setApiOutputTokens(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="100000"
                    />
                  </div>
                  <div>
                    <label className="label">请求数量</label>
                    <input
                      type="number"
                      value={apiNumRequests}
                      onChange={(e) => setApiNumRequests(parseInt(e.target.value))}
                      className="input-field"
                      min="1"
                      max="10000"
                    />
                  </div>
                </div>

                <div className="flex gap-3">
                  <button onClick={handleRunApi} disabled={running || !apiUrl || !apiModelName} className="btn-primary flex-1 flex items-center justify-center gap-2">
                    {running ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        测试中...
                      </>
                    ) : (
                      <>
                        <Play size={16} />
                        启动 API 测试
                      </>
                    )}
                  </button>
                  <button onClick={() => setShowForm(false)} className="btn-secondary">取消</button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toolbar */}
      {benchmarks.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleSelectAll}
            className="btn-secondary text-xs flex items-center gap-1"
          >
            {selectedIds.size === benchmarks.length ? <CheckSquare size={14} /> : <Square size={14} />}
            {selectedIds.size === benchmarks.length ? '取消全选' : '全选'}
          </button>
          {selectedIds.size > 0 && (
            <>
              <button
                onClick={() => setShowComparison(true)}
                className="btn-secondary text-xs flex items-center gap-1"
              >
                <BarChart3 size={14} /> 对比选中 ({selectedIds.size})
              </button>
              <button
                onClick={handleExportSelected}
                className="btn-secondary text-xs flex items-center gap-1"
              >
                <FileText size={14} /> 导出 CSV
              </button>
              <button
                onClick={handleDeleteSelected}
                className="btn-secondary text-xs flex items-center gap-1 text-red-400"
              >
                <Trash2 size={14} /> 删除 ({selectedIds.size})
              </button>
            </>
          )}
          <span className="text-xs text-white/30 ml-auto">
            {benchmarks.filter(b => b.type === 'vllm').length} vLLM / {benchmarks.filter(b => b.type === 'api').length} API
          </span>
        </div>
      )}

      {/* Comparison */}
      {showComparison && (
        <ComparisonPanel
          list={benchmarks.filter(b => selectedIds.has(b.id))}
          onClose={() => setShowComparison(false)}
        />
      )}

      {/* History */}
      <div className="card">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <BarChart3 size={16} className="text-primary-400" />
          测试历史
        </h3>
        {benchmarks.length === 0 ? (
          <p className="text-white/25 text-sm text-center py-8">暂无测试记录</p>
        ) : (
          <div className="space-y-2">
            {benchmarks.map((b) => (
              <div key={b.id} className="glass-hover p-4 flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => toggleSelect(b.id)}
                    className="text-white/40 hover:text-primary-400 transition-colors"
                  >
                    {selectedIds.has(b.id) ? <CheckSquare size={16} /> : <Square size={16} />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
                        b.type === 'api' ? 'bg-blue-500/20 text-blue-300' : 'bg-purple-500/20 text-purple-300'
                      }`}>
                        {b.type === 'api' ? 'API' : 'vLLM'}
                      </span>
                      <p className="text-sm font-medium truncate">{b.model_name}</p>
                    </div>
                    <p className="text-xs text-white/40 font-mono mt-1">{b.id}</p>
                    {b.type === 'api' && (
                      <p className="text-xs text-white/30 mt-0.5">{b.api_url}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`badge text-xs ${
                    b.status === 'completed' ? 'badge-running' : b.status === 'running' ? 'badge-starting' : 'badge-stopped'
                  }`}>
                    {b.status}
                  </span>
                  {b.status === 'completed' && (
                    <>
                      <button onClick={() => viewResult(b.id)} className="btn-secondary text-xs px-2 py-1">
                        查看结果
                      </button>
                      <button onClick={() => exportPDF(b.id)} className="btn-secondary text-xs px-2 py-1 flex items-center gap-1">
                        <Download size={12} /> 导出
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Result Panel */}
      <AnimatePresence>
        {selectedResult && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <BarChart3 size={18} className="text-primary-400" />
                {selectedResult.model_name} 测试结果
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
                  selectedResult.type === 'api' ? 'bg-blue-500/20 text-blue-300' : 'bg-purple-500/20 text-purple-300'
                }`}>
                  {selectedResult.type === 'api' ? 'API' : 'vLLM'}
                </span>
              </h3>
              <button onClick={() => setSelectedResult(null)} className="btn-secondary text-sm">关闭</button>
            </div>
            {selectedResult.type === 'vllm' ? (
              <VllmResultPanel result={selectedResult.result} />
            ) : (
              <ApiResultPanel bench={selectedResult} />
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live Logs */}
      <AnimatePresence>
        {activeBenchLog && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}>
            <LogViewer logs={logs} connected={connected} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
