"""Public API benchmark service."""
import asyncio
import uuid
import time
import json
import httpx
import aiohttp
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

from services.log_manager import log_manager


@dataclass
class APIBenchRequestMetrics:
    """Per-request detailed metrics for streaming API."""
    ttft_ms: float = 0.0  # Time to First Token
    tpot_ms: float = 0.0  # Time Per Output Token (avg)
    decode_tokens_per_second: float = 0.0  # Tokens/s after first token
    total_output_tokens: int = 0
    total_latency_ms: float = 0.0
    success: bool = False
    error: str = ""


@dataclass
class APIBenchResult:
    id: str
    api_url: str
    model_name: str
    concurrency: int
    input_tokens: int
    output_tokens: int
    status: str = "pending"
    start_time: float = 0.0
    end_time: float = 0.0
    
    # Core LLM metrics
    ttft_ms: float = 0.0  # avg TTFT
    tpot_ms: float = 0.0  # avg TPOT
    decode_tokens_per_second: float = 0.0  # avg decode speed
    total_output_tokens: int = 0  # sum of all output tokens
    total_elapsed_ms: float = 0.0  # total test duration
    
    # Legacy compatibility
    total_requests: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    requests_per_second: float = 0.0
    tokens_per_second: float = 0.0
    latencies: List[float] = field(default_factory=list)
    latency_viz_data: List[dict] = field(default_factory=list)
    error_log: List[str] = field(default_factory=list)
    
    # Detailed per-request metrics
    request_metrics: List[APIBenchRequestMetrics] = field(default_factory=list)


class APIBenchService:
    def __init__(self):
        self.benchmarks: Dict[str, APIBenchResult] = {}

    def create_bench_entry(
        self,
        api_url: str,
        model_name: str,
        concurrency: int = 1,
        input_tokens: int = 256,
        output_tokens: int = 256,
    ) -> str:
        """Create a bench entry and return its ID immediately."""
        bench_id = f"api-bench-{uuid.uuid4().hex[:8]}"
        result = APIBenchResult(
            id=bench_id,
            api_url=api_url,
            model_name=model_name,
            concurrency=concurrency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="running",
            start_time=time.time(),
        )
        self.benchmarks[bench_id] = result
        return bench_id

    async def run_api_bench(
        self,
        bench_id: str,
        api_url: str,
        api_key: str,
        model_name: str,
        concurrency: int = 1,
        input_tokens: int = 256,
        output_tokens: int = 256,
        num_requests: int = 10,
    ) -> None:
        """Execute the benchmark in background using streaming API."""
        channel = f"bench:{bench_id}"
        log_manager.emit(channel, "info", f"API性能测试(流式): {model_name} @ {api_url}")
        
        result = self.benchmarks.get(bench_id)
        if not result:
            log_manager.emit(channel, "error", f"Bench entry {bench_id} not found")
            return

        # Build endpoint
        base = api_url.rstrip('/')
        if base.endswith('/chat/completions') or base.endswith('/completions'):
            endpoint = base
        else:
            endpoint = f"{base}/chat/completions"

        # Structured prompt for consistent output
        prompt = (
            "You are a helpful assistant. Provide a concise explanation about machine learning. "
            "Cover these points briefly: 1) definition, 2) main types (supervised, unsupervised, reinforcement), "
            "3) common algorithms, 4) real-world applications. Keep it under 300 words."
        )

        async def single_streaming_request(idx: int) -> APIBenchRequestMetrics:
            """Streaming request that measures TTFT and per-token timing."""
            m = APIBenchRequestMetrics()
            req_start = time.time()
            first_token_time = None
            token_timestamps: List[float] = []
            output_content = ""
            
            try:
                timeout = aiohttp.ClientTimeout(total=60, connect=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": output_tokens,
                            "temperature": 0.0,
                            "stream": True,
                        },
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            m.total_latency_ms = (time.time() - req_start) * 1000
                            m.error = f"HTTP {resp.status}: {error_text[:200]}"
                            return m

                        async for line in resp.content:
                            raw = line.decode("utf-8", errors="replace").strip()
                            if not raw or raw.startswith(":"):
                                continue
                            if raw == "data: [DONE]":
                                break
                            if raw.startswith("data: "):
                                data_str = raw[6:]
                                try:
                                    data = json.loads(data_str)
                                    choices = data.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            now = time.time()
                                            if first_token_time is None:
                                                first_token_time = now
                                            token_timestamps.append(now)
                                            output_content += content
                                except json.JSONDecodeError:
                                    continue

                m.total_latency_ms = (time.time() - req_start) * 1000
                
                if first_token_time and token_timestamps:
                    m.ttft_ms = (first_token_time - req_start) * 1000
                    m.total_output_tokens = len(token_timestamps)
                    
                    if m.total_output_tokens >= 2:
                        # Decode duration: from first token to last token
                        decode_duration = token_timestamps[-1] - first_token_time
                        if decode_duration > 0:
                            decode_tokens = m.total_output_tokens - 1  # exclude first token
                            m.tpot_ms = (decode_duration / decode_tokens) * 1000
                            m.decode_tokens_per_second = decode_tokens / decode_duration
                        else:
                            # Single token output
                            m.tpot_ms = 0
                            m.decode_tokens_per_second = float('inf')
                    elif m.total_output_tokens == 1:
                        m.tpot_ms = 0
                        m.decode_tokens_per_second = 1.0 / max(m.ttft_ms / 1000, 0.001)
                    
                    m.success = True
                elif output_content and not first_token_time:
                    # Non-streaming fallback: received content but no per-token timing
                    m.success = True
                    m.total_output_tokens = len(output_content.split())
                    m.ttft_ms = m.total_latency_ms
                    
            except asyncio.TimeoutError:
                m.total_latency_ms = (time.time() - req_start) * 1000
                m.error = "timeout"
            except Exception as e:
                m.total_latency_ms = (time.time() - req_start) * 1000
                m.error = str(e)[:200]
            
            return m

        log_manager.emit(channel, "info", f"并发度: {concurrency}, 请求数: {num_requests}, 最大输出token: {output_tokens}")
        
        # Run requests with concurrency control
        sem = asyncio.Semaphore(concurrency)
        
        async def bounded_request(idx):
            async with sem:
                return await single_streaming_request(idx)

        tasks = [bounded_request(i) for i in range(num_requests)]
        
        completed = 0
        for coro in asyncio.as_completed(tasks):
            m: APIBenchRequestMetrics = await coro
            completed += 1
            result.request_metrics.append(m)
            
            if m.success:
                result.success_count += 1
                result.latencies.append(m.total_latency_ms)
            else:
                result.fail_count += 1
                if len(result.error_log) < 20:
                    result.error_log.append(m.error)
            
            if completed % max(1, num_requests // 10) == 0:
                log_manager.emit(channel, "info", f"进度: {completed}/{num_requests}")

        result.total_requests = num_requests
        result.end_time = time.time()

        if result.latencies:
            sorted_lats = sorted(result.latencies)
            n = len(sorted_lats)
            result.total_latency_ms = sum(sorted_lats)
            result.avg_latency_ms = result.total_latency_ms / n
            result.min_latency_ms = sorted_lats[0]
            result.max_latency_ms = sorted_lats[-1]
            result.p50_latency_ms = sorted_lats[int(n * 0.50)]
            result.p90_latency_ms = sorted_lats[int(n * 0.90)]
            result.p99_latency_ms = sorted_lats[int(min(n - 1, n * 0.99))]

            # Generate latency distribution for charts
            bucket_size = max(1, int(n / 50))
            result.latency_viz_data = [
                {"index": i, "latency_ms": round(sorted_lats[i], 1)}
                for i in range(0, n, bucket_size)
            ]

        # Calculate aggregated LLM metrics
        success_metrics = [m for m in result.request_metrics if m.success]
        if success_metrics:
            result.ttft_ms = sum(m.ttft_ms for m in success_metrics) / len(success_metrics)
            valid_tpot = [m.tpot_ms for m in success_metrics if m.tpot_ms > 0]
            result.tpot_ms = sum(valid_tpot) / len(valid_tpot) if valid_tpot else 0
            valid_decode = [m.decode_tokens_per_second for m in success_metrics if m.decode_tokens_per_second > 0 and m.decode_tokens_per_second < float('inf')]
            result.decode_tokens_per_second = sum(valid_decode) / len(valid_decode) if valid_decode else 0
            result.total_output_tokens = sum(m.total_output_tokens for m in success_metrics)

        result.total_elapsed_ms = (result.end_time - result.start_time) * 1000
        elapsed = result.total_elapsed_ms / 1000
        result.requests_per_second = num_requests / elapsed if elapsed > 0 else 0
        result.tokens_per_second = result.total_output_tokens / elapsed if elapsed > 0 else 0

        result.status = "completed"
        log_manager.emit(channel, "success", 
            f"测试完成: 成功{result.success_count}/{num_requests}, "
            f"TTFT {result.ttft_ms:.0f}ms, TPOT {result.tpot_ms:.0f}ms, "
            f"解码速度 {result.decode_tokens_per_second:.1f} tok/s, "
            f"总输出 {result.total_output_tokens} tokens")

    def get_benchmark(self, bench_id: str) -> Optional[dict]:
        b = self.benchmarks.get(bench_id)
        if not b:
            return None
        d = {k: v for k, v in b.__dict__.items()}
        d["type"] = "api"
        d["latency_viz_data"] = b.latency_viz_data
        d["error_log"] = b.error_log[:50]
        d["request_metrics"] = [
            {
                "ttft_ms": m.ttft_ms,
                "tpot_ms": m.tpot_ms,
                "decode_tokens_per_second": m.decode_tokens_per_second,
                "total_output_tokens": m.total_output_tokens,
                "total_latency_ms": m.total_latency_ms,
                "success": m.success,
                "error": m.error,
            }
            for m in b.request_metrics
        ]
        return d

    def list_benchmarks(self) -> List[dict]:
        return [
            {
                "id": b.id,
                "model_name": b.model_name,
                "api_url": b.api_url,
                "concurrency": b.concurrency,
                "status": b.status,
                "avg_latency_ms": b.avg_latency_ms,
                "requests_per_second": b.requests_per_second,
                "tokens_per_second": b.tokens_per_second,
                "ttft_ms": b.ttft_ms,
                "tpot_ms": b.tpot_ms,
                "decode_tokens_per_second": b.decode_tokens_per_second,
                "total_output_tokens": b.total_output_tokens,
                "total_elapsed_ms": b.total_elapsed_ms,
                "total_requests": b.total_requests,
                "success_count": b.success_count,
                "fail_count": b.fail_count,
                "type": "api",
            }
            for b in self.benchmarks.values()
        ]


api_bench_service = APIBenchService()