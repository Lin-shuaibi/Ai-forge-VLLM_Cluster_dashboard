import { useState, useEffect, useCallback, useRef } from 'react';
import type { LogEntry } from '@/types';

export function useWebSocket(channel: string | null) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)

  const connect = useCallback(() => {
    if (!channel) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}${channel}`
    
    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected:', channel)
        setConnected(true)
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const entry: LogEntry = JSON.parse(event.data);
          setLogs(prev => [...prev.slice(-500), entry]);
        } catch {}
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setConnected(false)
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason)
        setConnected(false)
        wsRef.current = null
        
        // 自动重连（指数退避）
        if (reconnectAttempts.current < 10) {
          const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts.current), 30000)
          reconnectTimerRef.current = setTimeout(() => {
            reconnectAttempts.current += 1
            connect()
          }, delay)
        }
      }
    } catch (error) {
      console.error('WebSocket connection failed:', error)
      setConnected(false)
    }
  }, [channel])

  useEffect(() => {
    if (channel) {
      connect()
    } else {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setConnected(false)
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      setLogs([])
      setConnected(false)
    }
  }, [channel, connect])

  return { logs, connected }
}

export function useApi() {
  const baseUrl = '/api';

  const get = useCallback(async <T,>(path: string): Promise<T> => {
    const res = await fetch(`${baseUrl}${path}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }, []);

  const post = useCallback(async <T,>(path: string, body?: unknown): Promise<T> => {
    const res = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }, []);

  const put = useCallback(async <T,>(path: string, body?: unknown): Promise<T> => {
    const res = await fetch(`${baseUrl}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }, []);

  const del = useCallback(async <T,>(path: string): Promise<T> => {
    const res = await fetch(`${baseUrl}${path}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }, []);

  return { get, post, put, del };
}