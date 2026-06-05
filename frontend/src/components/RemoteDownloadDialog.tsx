import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Download, Server, Key, FolderOpen, Globe, Zap, Loader2, CheckCircle, XCircle } from 'lucide-react';

interface RemoteDownloadDialogProps {
  open: boolean;
  onClose: () => void;
  modelId: string;
  modelName: string;
  source: string;
}

interface DownloadStatus {
  status: string;
  progress: number;
  message?: string;
  speed?: string;
  downloaded?: string;
}

const RemoteDownloadDialog: React.FC<RemoteDownloadDialogProps> = ({
  open, onClose, modelId, modelName, source
}) => {
  const [host, setHost] = useState('');
  const [username, setUsername] = useState('root');
  const [password, setPassword] = useState('');
  const [targetDir, setTargetDir] = useState('/data/models');
  const [downloadSource, setDownloadSource] = useState<'huggingface' | 'modelscope'>(
    source === 'modelscope' ? 'modelscope' : 'huggingface'
  );
  const [hfToken, setHfToken] = useState('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<DownloadStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Connect WebSocket for progress
  useEffect(() => {
    if (!taskId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/logs/download`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[RemoteDownload] WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const channel = data.channel || '';
        if (!channel.includes('download:')) return;

        const msg = data.message || '';
        setLogs(prev => [...prev.slice(-199), msg]);

        if (data.status) {
          setStatus(prev => ({
            ...prev,
            status: data.status,
            progress: data.progress || prev?.progress || 0,
            speed: data.speed || prev?.speed,
            message: msg,
          } as DownloadStatus));
        }

        if (data.level === 'success' && msg.includes('completed')) {
          setStatus(prev => ({ ...prev, status: 'completed', progress: 1.0 } as DownloadStatus));
        }
        if (data.level === 'error') {
          setStatus(prev => ({ ...prev, status: 'failed', message: msg } as DownloadStatus));
        }
      } catch (e) {
        console.error('[RemoteDownload] WS parse error:', e);
      }
    };

    ws.onerror = (e) => {
      console.error('[RemoteDownload] WebSocket error:', e);
    };

    ws.onclose = () => {
      console.log('[RemoteDownload] WebSocket closed');
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [taskId]);

  // Poll status if no WebSocket
  useEffect(() => {
    if (!taskId || status?.status === 'completed' || status?.status === 'failed') return;

    const interval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/download/status/${taskId}`);
        if (resp.ok) {
          const data = await resp.json();
          setStatus({
            status: data.status || 'downloading',
            progress: data.progress || 0,
            message: data.message || '',
            speed: data.speed || '',
          });
          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(interval);
          }
        }
      } catch (e) {
        console.error('[RemoteDownload] Status poll error:', e);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [taskId, status?.status]);

  const handleSubmit = async () => {
    if (!host || !username || !password || !modelId) {
      setError('请填写目标主机、用户名、密码');
      return;
    }
    setError('');
    setSubmitting(true);
    setLogs([]);
    setStatus({ status: 'connecting', progress: 0 });

    try {
      const resp = await fetch('/api/download/remote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host,
          username,
          password,
          model_id: modelId,
          target_dir: targetDir,
          source: downloadSource,
          hf_token: hfToken || undefined,
        }),
      });

      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Request failed');

      setTaskId(data.task_id);
      setStatus({ status: 'downloading', progress: 0.01 });
    } catch (e: any) {
      setError(e.message || '提交失败');
      setStatus(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setTaskId(null);
    setStatus(null);
    setLogs([]);
    setError('');
    onClose();
  };

  if (!open) return null;

  const isDone = status?.status === 'completed' || status?.status === 'failed' || status?.status === 'cancelled';
  const pct = Math.round((status?.progress || 0) * 100);

  return (
    <div className="modal-overlay" onClick={isDone ? handleClose : undefined}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="flex items-center gap-2">
            <Server size={20} />
            远程下载模型
          </h2>
          <button className="btn-close" onClick={handleClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body space-y-4">
          {/* Model Info */}
          <div className="p-3 rounded-lg bg-white/5 border border-white/10">
            <p className="text-xs text-white/40">模型</p>
            <p className="font-semibold text-white">{modelName}</p>
            <p className="text-xs text-white/40 font-mono">{modelId}</p>
          </div>

          {!taskId ? (
            /* Form */
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">目标主机 IP *</label>
                  <input
                    className="input-field"
                    placeholder="192.168.1.100"
                    value={host}
                    onChange={e => setHost(e.target.value)}
                  />
                </div>
                <div>
                  <label className="label">用户名 *</label>
                  <input
                    className="input-field"
                    placeholder="root"
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className="label">密码 *</label>
                <input
                  type="password"
                  className="input-field"
                  placeholder="请输入密码"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">目标目录</label>
                  <input
                    className="input-field"
                    placeholder="/data/models"
                    value={targetDir}
                    onChange={e => setTargetDir(e.target.value)}
                  />
                </div>
                <div>
                  <label className="label">下载源</label>
                  <select
                    className="input-field"
                    value={downloadSource}
                    onChange={e => setDownloadSource(e.target.value as any)}
                  >
                    <option value="huggingface">HuggingFace</option>
                    <option value="modelscope">ModelScope</option>
                  </select>
                </div>
              </div>

              {downloadSource === 'huggingface' && (
                <div>
                  <label className="label">
                    HF Token <span className="text-white/30">(可选)</span>
                  </label>
                  <input
                    type="password"
                    className="input-field"
                    placeholder="hf_..."
                    value={hfToken}
                    onChange={e => setHfToken(e.target.value)}
                  />
                </div>
              )}

              {error && (
                <div className="text-red-400 text-sm bg-red-500/10 p-2 rounded">
                  {error}
                </div>
              )}
            </div>
          ) : (
            /* Progress */
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                {status?.status === 'connecting' && <Loader2 size={16} className="animate-spin text-yellow-400" />}
                {status?.status === 'preparing' && <Loader2 size={16} className="animate-spin text-blue-400" />}
                {status?.status === 'downloading' && <Download size={16} className="text-primary-400" />}
                {status?.status === 'completed' && <CheckCircle size={16} className="text-green-400" />}
                {status?.status === 'failed' && <XCircle size={16} className="text-red-400" />}
                <span className="capitalize">{status?.status || 'unknown'}</span>
              </div>

              {/* Progress Bar */}
              <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: status?.status === 'failed' ? '#ef4444' : '#3b82f6',
                  }}
                />
              </div>
              <div className="flex justify-between text-xs text-white/40">
                <span>{pct}%</span>
                {status?.speed && <span>{status.speed}</span>}
              </div>

              {/* Logs */}
              {logs.length > 0 && (
                <div className="bg-black/40 rounded-lg p-2 max-h-48 overflow-y-auto font-mono text-xs text-white/70 space-y-0.5">
                  {logs.map((log, i) => (
                    <div key={i} className="truncate">{log}</div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}

              {status?.message && status?.status === 'failed' && (
                <div className="text-red-400 text-sm bg-red-500/10 p-2 rounded">
                  {status.message}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          {!taskId ? (
            <>
              <button className="btn-secondary" onClick={handleClose}>取消</button>
              <button
                className="btn-primary flex items-center gap-2"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                {submitting ? '提交中...' : '开始下载'}
              </button>
            </>
          ) : isDone ? (
            <button className="btn-primary" onClick={handleClose}>关闭</button>
          ) : (
            <button
              className="btn-danger"
              onClick={() => {
                if (taskId) {
                  fetch(`/api/download/${taskId}`, { method: 'DELETE' }).catch(() => {});
                  setStatus(s => ({ ...s, status: 'cancelled' } as DownloadStatus));
                }
              }}
            >
              取消下载
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default RemoteDownloadDialog;
