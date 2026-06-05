export interface Cluster {
  id: string;
  name: string;
  image: string;
  use_combined: boolean;
  node_count: number;
  head_ip: string | null;
  status: string;
}

export interface ClusterDetail extends Cluster {
  nodes: NodeSpec[];
  containers: ContainerInfo[];
  network: string;
}

export interface NodeSpec {
  ip: string;
  username: string;
  password: string;
  gpus: number;
}

export interface ContainerInfo {
  id: string;
  name: string;
  ip: string;
  is_head: boolean;
}

export interface ModelInfo {
  id: string;
  name: string;
  path: string;
  cluster_id: string | null;
  port: number;
  status: string;
}

export interface BenchmarkInfo {
  id: string;
  type: 'vllm' | 'api';
  model_path?: string;
  model_name: string;
  status: string;
  result?: BenchmarkResult;
  api_url?: string;
  concurrency?: number;
  
  // Core LLM metrics (new)
  ttft_ms?: number;
  tpot_ms?: number;
  decode_tokens_per_second?: number;
  total_output_tokens?: number;
  total_elapsed_ms?: number;
  
  // Legacy metrics
  avg_latency_ms?: number;
  requests_per_second?: number;
  tokens_per_second?: number;
  total_requests?: number;
  success_count?: number;
  fail_count?: number;
  error?: string;
  latency_viz_data?: { index: number; latency_ms: number }[];
  error_log?: string[];
}

export interface APIBenchResult {
  id: string;
  api_url: string;
  model_name: string;
  concurrency: number;
  total_requests: number;
  success_count: number;
  fail_count: number;
  
  // Core LLM metrics
  ttft_ms: number;
  tpot_ms: number;
  decode_tokens_per_second: number;
  total_output_tokens: number;
  total_elapsed_ms: number;
  
  // Legacy metrics
  avg_latency_ms: number;
  p50_latency_ms: number;
  p90_latency_ms: number;
  p99_latency_ms: number;
  min_latency_ms: number;
  max_latency_ms: number;
  requests_per_second: number;
  tokens_per_second: number;
  latency_viz_data: { index: number; latency_ms: number }[];
  error_log: string[];
}

export interface BenchmarkResult {
  raw_output?: string;
  metrics: Record<string, string>;
}

export interface ImageSettings {
  ray_image: string;
  vllm_image: string;
  ray_vllm_image: string;
  use_combined_image: boolean;
  registry_auth?: string;
}

export interface AIConfig {
  api_url: string;
  api_key: string;
  model_name: string;
  use_local_vllm: boolean;
  local_vllm_url: string;
  local_model_name: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  toolCall?: { name: string; args: Record<string, any> };
  toolResult?: string;
}

export interface ImageCheckResult {
  exists: boolean;
  pulled: boolean;
  error?: string;
  size_mb?: number;
  layers?: number;
}

export interface ProgressStep {
  step: string;
  current: number;
  total: number;
  percentage: number;
  status: 'in_progress' | 'completed' | 'failed';
  details: Record<string, any>;
}

export interface ProgressInfo {
  current_step: number;
  total_steps: number;
  percentage: number;
  elapsed_seconds: number;
  steps: Record<string, any>;
  status?: string;
}

export interface LogEntry {
  timestamp: number;
  level: 'info' | 'success' | 'warn' | 'error';
  message: string;
  channel: string;
}

export interface SystemStatus {
  docker: boolean;
  clusters: number;
  models: number;
  benchmarks: number;
  clusters_list: Cluster[];
  models_list: ModelInfo[];
}