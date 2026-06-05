import React, { useState, useEffect, useRef } from 'react';
import { Bell, AlertCircle, CheckCircle, Info, X, Filter, Check } from 'lucide-react';
import { useWebSocket } from '../hooks';
import { formatDistanceToNow } from 'date-fns';

interface Notification {
  id: string;
  type: 'gpu_temp' | 'model_error' | 'node_offline' | 'disk_full' | 'system' | 'alert';
  level: 'info' | 'warning' | 'error' | 'critical';
  title: string;
  message: string;
  data?: any;
  read: boolean;
  created_at: string;
}

const NotificationsCenter: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showPanel, setShowPanel] = useState(false);
  const [filter, setFilter] = useState<'all' | 'unread' | 'critical'>('all');
  const [loading, setLoading] = useState(false);
  const { logs } = useWebSocket('/api/features/notifications/ws');
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchNotifications();
  }, []);

  useEffect(() => {
    // Process WebSocket logs into notifications
    const newNotifications: Notification[] = [];
    logs.forEach((log) => {
      try {
        const data = typeof log === 'string' ? JSON.parse(log) : log;
        if (data && data.type === 'notification' && data.data) {
          newNotifications.push(data.data);
        }
      } catch {}
    });
    
    if (newNotifications.length > 0) {
      setNotifications(prev => {
        const existingIds = new Set(prev.map(n => n.id));
        const unique = newNotifications.filter(n => !existingIds.has(n.id));
        const merged = [...unique, ...prev];
        return merged.slice(0, 100);
      });
    }
  }, [logs]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setShowPanel(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/features/notifications');
      const data = await response.json();
      setNotifications(data.notifications || []);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    } finally {
      setLoading(false);
    }
  };

  const markAsRead = async (notificationId: string) => {
    try {
      await fetch(`/api/features/notifications/${notificationId}/read`, { method: 'POST' });
      setNotifications(prev =>
        prev.map(n => n.id === notificationId ? { ...n, read: true } : n)
      );
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  const markAllAsRead = async () => {
    const unreadIds = notifications.filter(n => !n.read).map(n => n.id);
    for (const id of unreadIds) {
      try {
        await fetch(`/api/features/notifications/${id}/read`, { method: 'POST' });
      } catch {}
    }
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const getIcon = (level: string) => {
    switch (level) {
      case 'critical': return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'error': return <AlertCircle className="w-4 h-4 text-orange-500" />;
      case 'warning': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default: return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'critical': return 'bg-red-500/10 border-red-500/30';
      case 'error': return 'bg-orange-500/10 border-orange-500/30';
      case 'warning': return 'bg-yellow-500/10 border-yellow-500/30';
      default: return 'bg-blue-500/10 border-blue-500/30';
    }
  };

  const filteredNotifications = notifications.filter(n => {
    if (filter === 'unread') return !n.read;
    if (filter === 'critical') return n.level === 'critical';
    return true;
  });

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setShowPanel(!showPanel)}
        className="relative p-2 rounded-lg hover:bg-gray-700/50 transition-colors"
      >
        <Bell className="w-5 h-5 text-gray-400" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-red-500 rounded-full">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {showPanel && (
        <div className="absolute right-0 mt-2 w-96 max-h-[32rem] bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
          <div className="p-3 border-b border-gray-700 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-200">通知中心</h3>
            <div className="flex items-center gap-2">
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as any)}
                className="text-xs bg-gray-700 text-gray-300 rounded px-2 py-1 border border-gray-600"
              >
                <option value="all">全部</option>
                <option value="unread">未读</option>
                <option value="critical">严重</option>
              </select>
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                >
                  <Check className="w-3 h-3" />
                  全部已读
                </button>
              )}
              <button
                onClick={() => setShowPanel(false)}
                className="p-1 hover:bg-gray-700 rounded"
              >
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          </div>

          <div className="overflow-y-auto max-h-[28rem]">
            {loading && filteredNotifications.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-500">加载中...</div>
            ) : filteredNotifications.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-500">
                <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-500" />
                暂无通知
              </div>
            ) : (
              filteredNotifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`p-3 border-b border-gray-700/50 hover:bg-gray-750 transition-colors cursor-pointer ${
                    !notification.read ? 'bg-gray-700/30' : ''
                  }`}
                  onClick={() => !notification.read && markAsRead(notification.id)}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">{getIcon(notification.level)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-200 truncate">
                          {notification.title}
                        </span>
                        <span className="text-xs text-gray-500 whitespace-nowrap ml-2">
                          {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                        {notification.message}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationsCenter;
