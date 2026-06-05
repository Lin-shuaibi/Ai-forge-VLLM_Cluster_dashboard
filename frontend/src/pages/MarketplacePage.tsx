import React, { useState, useEffect, useCallback } from 'react';
import { Search, Star, Download, Filter, TrendingUp, Clock, Tag, ExternalLink, RefreshCw, Database, Globe, Heart, Zap, Layers, ChevronRight, ChevronLeft, X, Server } from 'lucide-react';

interface ModelTemplate {
  id: string;
  name: string;
  model_name: string;
  description: string;
  category: string;
  tags: string[];
  downloads: number;
  likes: number;
  created_at: string;
  updated_at?: string;
  author?: string;
  framework?: string;
  task?: string;
  is_public: boolean;
  model_card?: string;
  recommended_config: Record<string, any>;
  source: string;
}

interface ModelFile {
  name?: string;
  size?: number;
  [key: string]: any;
}

interface ModelDetails extends ModelTemplate {
  files: ModelFile[];
  config: Record<string, any>;
}

const CATEGORIES = [
  { key: 'all', label: 'All', icon: <Layers size={14} /> },
  { key: 'llm', label: 'LLM', icon: <Zap size={14} /> },
  { key: 'vision', label: 'Vision', icon: <Tag size={14} /> },
  { key: 'audio', label: 'Audio', icon: <Tag size={14} /> },
  { key: 'multimodal', label: 'Multimodal', icon: <Layers size={14} /> },
];

const SORT_OPTIONS = [
  { value: 'popular', label: 'Popular' },
  { value: 'recent', label: 'Recent' },
  { value: 'name', label: 'Name' },
];

import RemoteDownloadDialog from '@/components/RemoteDownloadDialog';

const MarketplacePage: React.FC = () => {
  const [templates, setTemplates] = useState<ModelTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [sortBy, setSortBy] = useState<'popular' | 'recent' | 'name'>('popular');
  const [source, setSource] = useState<'all' | 'modelscope' | 'local'>('all');
  const [page, setPage] = useState(1);
  const [selectedModel, setSelectedModel] = useState<ModelDetails | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [remoteOpen, setRemoteOpen] = useState(false);
  const [remoteModel, setRemoteModel] = useState<{ id: string; name: string; source: string } | null>(null);

  const PER_PAGE = 12;

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        source,
        page: String(page),
        per_page: String(PER_PAGE),
      });
      if (selectedCategory !== 'all') params.append('category', selectedCategory);
      if (search) params.append('search', search);

      const response = await fetch(`/api/marketplace/templates?${params}`);
      const data = await response.json();
      const list = data.templates || [];

      let sorted = [...list];
      switch (sortBy) {
        case 'popular':
          sorted.sort((a, b) => (b.downloads || 0) - (a.downloads || 0));
          break;
        case 'recent':
          sorted.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
          break;
        case 'name':
          sorted.sort((a, b) => a.name.localeCompare(b.name));
          break;
      }

      setTemplates(sorted);
    } catch (error) {
      console.error('Failed to fetch templates:', error);
      showNotification('Failed to fetch models', 'error');
    } finally {
      setLoading(false);
    }
  }, [source, page, selectedCategory, search, sortBy]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const viewModelDetails = async (modelId: string) => {
    setDetailLoading(true);
    try {
      const response = await fetch(`/api/marketplace/templates/${modelId}`);
      if (!response.ok) throw new Error('Model not found');
      const data: ModelDetails = await response.json();
      setSelectedModel(data);
    } catch (error) {
      showNotification('Failed to fetch model details', 'error');
    } finally {
      setDetailLoading(false);
    }
  };

  const useTemplate = async (templateId: string) => {
    try {
      const response = await fetch(`/api/marketplace/templates/${templateId}/use`, { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        const msg = data.download_task_id
          ? `Download started for "${data.model.name}". Check Downloads page for progress.`
          : `Template "${data.model.name}" loaded! Config applied.`;
        showNotification(msg, 'success');
      }
    } catch (error) {
      showNotification('Failed to load template', 'error');
    }
  };

  const toggleFavorite = async (modelId: string) => {
    try {
      if (favorites.has(modelId)) {
        await fetch(`/api/marketplace/favorites/${modelId}`, { method: 'DELETE' });
        setFavorites(prev => { const n = new Set(prev); n.delete(modelId); return n; });
      } else {
        await fetch(`/api/marketplace/favorites/${modelId}`, { method: 'POST' });
        setFavorites(prev => new Set(prev).add(modelId));
      }
    } catch {
      showNotification('Favorite operation failed', 'error');
    }
  };

  const formatNumber = (n: number) => n > 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

  const getSourceBadge = (s: string) => {
    if (s === 'modelscope') return { icon: <Globe size={12} />, label: 'ModelScope', cls: 'badge-modelscope' };
    return { icon: <Database size={12} />, label: 'Local', cls: 'badge-local' };
  };

  return (
    <div className="marketplace-page">
      {/* Notification Toast */}
      {notification && (
        <div className={`notification-toast ${notification.type}`}>
          {notification.type === 'success' ? '✅' : '❌'} {notification.message}
        </div>
      )}

      {/* Header */}
      <div className="marketplace-header">
        <div className="header-top">
          <div className="header-title-group">
            <h1 className="header-title">
              <Globe className="header-icon" size={28} />
              Model Marketplace
            </h1>
            <span className="header-subtitle">Explore & deploy AI models from ModelScope & local</span>
          </div>
          <button className="btn-refresh" onClick={fetchTemplates} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
          </button>
        </div>

        {/* Toolbar */}
        <div className="marketplace-toolbar">
          {/* Search */}
          <div className="search-box">
            <Search size={18} />
            <input
              type="text"
              placeholder="Search models by name, description, or tags..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
            />
            {search && (
              <button className="btn-clear" onClick={() => { setSearch(''); setPage(1); }}>
                <X size={14} />
              </button>
            )}
          </div>

          {/* Source Toggle */}
          <div className="source-toggle">
            <button className={`source-btn ${source === 'all' ? 'active' : ''}`} onClick={() => setSource('all')}>
              <Globe size={14} /> All
            </button>
            <button className={`source-btn ${source === 'modelscope' ? 'active' : ''}`} onClick={() => setSource('modelscope')}>
              <Globe size={14} /> ModelScope
            </button>
            <button className={`source-btn ${source === 'local' ? 'active' : ''}`} onClick={() => setSource('local')}>
              <Database size={14} /> Local
            </button>
          </div>

          {/* Sort */}
          <select className="sort-select" value={sortBy} onChange={e => setSortBy(e.target.value as any)}>
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* Category Filter */}
        <div className="category-filter">
          {CATEGORIES.map(cat => (
            <button
              key={cat.key}
              className={`cat-btn ${selectedCategory === cat.key ? 'active' : ''}`}
              onClick={() => { setSelectedCategory(cat.key); setPage(1); }}
            >
              {cat.icon} {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="marketplace-content">
        {loading ? (
          <div className="loading-skeleton">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton-card">
                <div className="skeleton-line w-60" />
                <div className="skeleton-line w-80" />
                <div className="skeleton-line w-40" />
              </div>
            ))}
          </div>
        ) : templates.length === 0 ? (
          <div className="empty-state">
            <Database size={48} />
            <h3>No models found</h3>
            <p>Try changing filters or search terms</p>
          </div>
        ) : (
          <>
            <div className="model-grid">
              {templates.map(model => {
                const badge = getSourceBadge(model.source || 'local');
                return (
                  <div key={model.id} className="model-card card-3d" onClick={() => viewModelDetails(model.id)}>
                    <div className="card-header">
                      <span className={`source-badge ${badge.cls}`}>
                        {badge.icon} {badge.label}
                      </span>
                      <div className="card-actions" onClick={e => e.stopPropagation()}>
                        <button
                          className={`btn-fav ${favorites.has(model.id) ? 'active' : ''}`}
                          onClick={() => toggleFavorite(model.id)}
                        >
                          <Heart size={14} fill={favorites.has(model.id) ? 'currentColor' : 'none'} />
                        </button>
                      </div>
                    </div>
                    <h3 className="card-name">{model.name}</h3>
                    <p className="card-model-name">{model.model_name}</p>
                    <p className="card-desc">{model.description?.slice(0, 100) || 'No description'}</p>
                    <div className="card-tags">
                      <span className="cat-tag">{model.category}</span>
                      {(model.tags || []).slice(0, 3).map(tag => (
                        <span key={tag} className="tag">{tag}</span>
                      ))}
                    </div>
                    <div className="card-stats">
                      <span title="Downloads"><Download size={14} /> {formatNumber(model.downloads || 0)}</span>
                      <span title="Likes"><Star size={14} /> {formatNumber(model.likes || 0)}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            <div className="pagination">
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                <ChevronLeft size={16} /> Prev
              </button>
              <span className="page-info">Page {page}</span>
              <button disabled={templates.length < PER_PAGE} onClick={() => setPage(p => p + 1)}>
                Next <ChevronRight size={16} />
              </button>
            </div>
          </>
        )}
      </div>

      {/* Model Detail Modal */}
      {selectedModel && (
        <div className="modal-overlay" onClick={() => setSelectedModel(null)}>
          <div className="modal-content detail-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{selectedModel.name}</h2>
                <p className="modal-model-name">
                  {selectedModel.model_name}
                  {selectedModel.source === 'modelscope' && (
                    <a href={selectedModel.model_card} target="_blank" className="model-link" rel="noopener noreferrer">
                      <ExternalLink size={14} /> View on ModelScope
                    </a>
                  )}
                </p>
              </div>
              <button className="btn-close" onClick={() => setSelectedModel(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div className="detail-section">
                <h4>Description</h4>
                <p>{selectedModel.description || 'No description available.'}</p>
              </div>

              <div className="detail-grid">
                <div className="detail-item">
                  <span className="detail-label">Category</span>
                  <span className="detail-value">{selectedModel.category}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Framework</span>
                  <span className="detail-value">{selectedModel.framework || 'N/A'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Task</span>
                  <span className="detail-value">{selectedModel.task || 'N/A'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Author</span>
                  <span className="detail-value">{selectedModel.author || 'N/A'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Downloads</span>
                  <span className="detail-value"><Download size={14} /> {formatNumber(selectedModel.downloads || 0)}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Likes</span>
                  <span className="detail-value"><Star size={14} /> {formatNumber(selectedModel.likes || 0)}</span>
                </div>
              </div>

              <div className="detail-section">
                <h4>Tags</h4>
                <div className="tag-cloud">
                  {(selectedModel.tags || []).map(tag => (
                    <span key={tag} className="tag">{tag}</span>
                  ))}
                </div>
              </div>

              {selectedModel.recommended_config && Object.keys(selectedModel.recommended_config).length > 0 && (
                <div className="detail-section">
                  <h4>Recommended VLLM Config</h4>
                  <pre className="config-block">
                    {JSON.stringify(selectedModel.recommended_config, null, 2)}
                  </pre>
                </div>
              )}

              {selectedModel.files && selectedModel.files.length > 0 && (
                <div className="detail-section">
                  <h4>Files ({selectedModel.files.length})</h4>
                  <div className="file-list">
                    {selectedModel.files.slice(0, 20).map((file, i) => (
                      <div key={i} className="file-item">
                        <span className="file-name">{file.name || String(file)}</span>
                        {file.size && <span className="file-size">{(file.size / 1024 / 1024).toFixed(1)} MB</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setSelectedModel(null)}>Close</button>
              <button 
                className="btn-fav-modal"
                onClick={() => toggleFavorite(selectedModel.id)}
              >
                <Heart size={16} fill={favorites.has(selectedModel.id) ? 'currentColor' : 'none'} />
                {favorites.has(selectedModel.id) ? 'Unfavorite' : 'Favorite'}
              </button>
              <button
                className="btn-secondary"
                onClick={() => {
                  setRemoteModel({
                    id: selectedModel.model_name,
                    name: selectedModel.name,
                    source: selectedModel.source || 'local',
                  });
                  setRemoteOpen(true);
                }}
              >
                <Server size={16} /> 远程下载
              </button>
              <button className="btn-primary" onClick={() => useTemplate(selectedModel.id)}>
                <Zap size={16} /> Use This Model
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Remote Download Dialog */}
      <RemoteDownloadDialog
        open={remoteOpen}
        onClose={() => setRemoteOpen(false)}
        modelId={remoteModel?.id || ''}
        modelName={remoteModel?.name || ''}
        source={remoteModel?.source || 'huggingface'}
      />
    </div>
  );
};

export default MarketplacePage;