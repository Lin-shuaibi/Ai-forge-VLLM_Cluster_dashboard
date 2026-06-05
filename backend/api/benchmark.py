"""Benchmark API routes."""
import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from services.vllm_service import vllm_service
from services.api_bench_service import api_bench_service
from services.log_manager import log_manager

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


# ── vLLM Bench ──────────────────────────────────────────────
class RunVllmBenchRequest(BaseModel):
    model_path: str
    tokenizer_path: Optional[str] = None
    dataset_name: str = "random"
    random_input_len: int = 2048
    random_output_len: int = 2048
    num_prompts: int = 5
    trust_remote_code: bool = True
    ignore_eos: bool = True
    served_model_name: str = "llm"
    port: int = 8000
    max_concurrency: Optional[int] = None


@router.post("/vllm/run", response_model=dict)
async def run_vllm_benchmark(body: RunVllmBenchRequest):
    try:
        bench_id = await vllm_service.run_benchmark_v2(
            model_path=body.model_path,
            tokenizer_path=body.tokenizer_path or body.model_path,
            dataset_name=body.dataset_name,
            random_input_len=body.random_input_len,
            random_output_len=body.random_output_len,
            num_prompts=body.num_prompts,
            trust_remote_code=body.trust_remote_code,
            ignore_eos=body.ignore_eos,
            served_model_name=body.served_model_name,
            port=body.port,
            max_concurrency=body.max_concurrency,
        )
        return {"bench_id": bench_id, "status": "running", "type": "vllm"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Public API Bench ────────────────────────────────────────
class RunApiBenchRequest(BaseModel):
    api_url: str
    api_key: str
    model_name: str
    concurrency: int = 1
    input_tokens: int = 256
    output_tokens: int = 256
    num_requests: int = 10


@router.post("/api/run", response_model=dict)
async def run_api_benchmark(body: RunApiBenchRequest):
    try:
        # Pre-create bench entry to return ID immediately, then launch in background
        bench_id = api_bench_service.create_bench_entry(
            api_url=body.api_url,
            model_name=body.model_name,
            concurrency=body.concurrency,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
        )
        asyncio.create_task(api_bench_service.run_api_bench(
            bench_id=bench_id,
            api_url=body.api_url,
            api_key=body.api_key,
            model_name=body.model_name,
            concurrency=body.concurrency,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
            num_requests=body.num_requests,
        ))
        return {"bench_id": bench_id, "status": "running", "type": "api"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Common ──────────────────────────────────────────────────
@router.get("", response_model=List[dict])
async def list_benchmarks():
    vllm_benches = await vllm_service.list_benchmarks()
    api_benches = api_bench_service.list_benchmarks()
    combined = []
    for b in vllm_benches:
        b["type"] = "vllm"
        combined.append(b)
    for b in api_benches:
        b["type"] = "api"
        combined.append(b)
    combined.sort(key=lambda x: x.get("id", ""), reverse=True)
    return combined


@router.get("/{bench_id}")
async def get_benchmark(bench_id: str):
    if bench_id.startswith("api-bench-"):
        bench = api_bench_service.get_benchmark(bench_id)
        if bench:
            return bench
    bench = await vllm_service.get_benchmark(bench_id)
    if bench:
        return bench
    raise HTTPException(status_code=404, detail="测试不存在")


@router.get("/{bench_id}/export-report")
async def export_report(bench_id: str):
    """Generate and return an HTML report."""
    bench_data = None
    if bench_id.startswith("api-bench-"):
        bench_data = api_bench_service.get_benchmark(bench_id)
    else:
        bench_data = await vllm_service.get_benchmark(bench_id)

    if not bench_data:
        raise HTTPException(status_code=404, detail="测试不存在")

    html = _build_report_html(bench_data)
    return Response(content=html, media_type="text/html",
                    headers={"Content-Disposition": f"attachment; filename={bench_id}-report.html"})


@router.delete("/{bench_id}")
async def delete_benchmark(bench_id: str):
    """Delete a benchmark record."""
    if bench_id.startswith("api-bench-"):
        # Delete from API bench service
        if bench_id in api_bench_service.benchmarks:
            # Cancel running benchmark task if exists
            bench = api_bench_service.benchmarks.get(bench_id)
            if bench and hasattr(api_bench_service, 'running_tasks'):
                task = api_bench_service.running_tasks.get(bench_id)
                if task and not task.done():
                    task.cancel()
                    del api_bench_service.running_tasks[bench_id]
            del api_bench_service.benchmarks[bench_id]
            return {"success": True, "message": f"API测试记录 {bench_id} 已删除"}
    else:
        # Delete from vLLM service
        success = await vllm_service.delete_benchmark(bench_id)
        if success:
            return {"success": True, "message": f"vLLM测试记录 {bench_id} 已删除"}
    
    raise HTTPException(status_code=404, detail="测试不存在")


def _build_report_html(data: dict) -> str:
    """Build a printable HTML report."""
    bench_type = data.get("type", "vllm")
    if bench_type == "api":
        table_rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in [
                ("模型名", data.get("model_name", "-")),
                ("API地址", data.get("api_url", "-")),
                ("并发数", str(data.get("concurrency", "-"))),
                ("总请求数", str(data.get("total_requests", "-"))),
                ("成功数", str(data.get("success_count", "-"))),
                ("失败数", str(data.get("fail_count", "-"))),
                ("平均延迟(ms)", f"{data.get('avg_latency_ms', 0):.1f}"),
                ("P50延迟(ms)", f"{data.get('p50_latency_ms', 0):.1f}"),
                ("P90延迟(ms)", f"{data.get('p90_latency_ms', 0):.1f}"),
                ("P99延迟(ms)", f"{data.get('p99_latency_ms', 0):.1f}"),
                ("最小延迟(ms)", f"{data.get('min_latency_ms', 0):.1f}"),
                ("最大延迟(ms)", f"{data.get('max_latency_ms', 0):.1f}"),
                ("QPS", f"{data.get('requests_per_second', 0):.1f}"),
                ("Tokens/s", f"{data.get('tokens_per_second', 0):.1f}"),
            ]
        )
    else:
        metrics = data.get("result", {}).get("metrics", {})
        table_rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in metrics.items()
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>性能测试报告</title>
<style>
body{{font-family:'Segoe UI',sans-serif;max-width:900px;margin:40px auto;padding:20px;color:#1e293b}}
h1{{color:#6366f1;border-bottom:3px solid #6366f1;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin:20px 0}}
th{{background:#6366f1;color:#fff;padding:10px;text-align:left}}
td{{padding:10px;border-bottom:1px solid #e2e8f0}}
tr:nth-child(even){{background:#f8fafc}}
.footer{{margin-top:40px;color:#94a3b8;font-size:12px}}
</style></head><body>
<h1>性能测试报告</h1>
<p>测试ID: {data.get("id", "-")} | 类型: {bench_type} | 状态: {data.get("status", "-")}</p>
<h2>测试指标</h2>
<table><thead><tr><th>指标</th><th>值</th></tr></thead><tbody>{table_rows}</tbody></table>
<div class="footer">生成于 vLLM Dashboard · 性能测试模块</div>
</body></html>"""


@router.websocket("/{bench_id}/logs")
async def benchmark_logs(websocket: WebSocket, bench_id: str):
    await websocket.accept()
    channel = f"bench:{bench_id}"
    queue = log_manager.subscribe(channel)
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except WebSocketDisconnect:
        log_manager.unsubscribe(channel, queue)
    except Exception:
        log_manager.unsubscribe(channel, queue)