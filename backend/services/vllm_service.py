"""vLLM model service management."""
import asyncio
import uuid
import time
from typing import Optional, Dict, List, Tuple
import httpx

from services.log_manager import log_manager
from services.docker_service import docker_service, ProgressTracker


class VLLMService:
    def __init__(self):
        self.models: Dict[str, dict] = {}
        self.benchmarks: Dict[str, dict] = {}

    async def start_model_with_progress(
        self,
        model_path: str,
        model_name: str,
        cluster_id: Optional[str] = None,
        tensor_parallel_size: int = 1,
        max_model_len: Optional[int] = None,
        gpu_memory_utilization: float = 0.90,
        dtype: str = "auto",
        trust_remote_code: bool = True,
        enforce_eager: bool = False,
        max_num_seqs: int = 256,
        port: int = 8000,
        extra_args: Optional[List[str]] = None,
    ) -> Tuple[str, ProgressTracker]:
        model_id = f"model-{uuid.uuid4().hex[:8]}"
        channel = f"model:{model_id}"
        
        # Calculate total steps: cmd build + container/process start + health check
        total_steps = 3
        tracker = ProgressTracker(channel, total_steps)
        
        log_manager.emit(channel, "info", f"启动模型: {model_name}")
        log_manager.emit(channel, "info", f"模型路径: {model_path}")
        log_manager.emit(channel, "info", f"Tensor Parallel: {tensor_parallel_size}")
        log_manager.emit(channel, "info", f"GPU 内存利用率: {gpu_memory_utilization}")
        
        try:
            # Step 1: Build command
            tracker.update("构建启动命令", "in_progress", model_name=model_name)
            
            cmd_parts = [
                "python -m vllm.entrypoints.openai.api_server",
                f"--model {model_path}",
                f"--served-model-name {model_name}",
                f"--tensor-parallel-size {tensor_parallel_size}",
                f"--gpu-memory-utilization {gpu_memory_utilization}",
                f"--dtype {dtype}",
                f"--port {port}",
                f"--max-num-seqs {max_num_seqs}",
            ]
            if max_model_len:
                cmd_parts.append(f"--max-model-len {max_model_len}")
            if trust_remote_code:
                cmd_parts.append("--trust-remote-code")
            if enforce_eager:
                cmd_parts.append("--enforce-eager")
            if extra_args:
                cmd_parts.extend(extra_args)
            
            cmd = " \\\n  ".join(cmd_parts)
            
            tracker.update("构建启动命令", "completed", command=cmd[:100] + "...")
            
            # Step 2: Start container/process
            tracker.update("启动模型容器/进程", "in_progress")
            
            if cluster_id:
                cluster = await docker_service.get_cluster(cluster_id)
                if not cluster:
                    raise ValueError(f"集群 {cluster_id} 不存在")
                
                if cluster.get("use_combined"):
                    head_container = cluster["containers"][0]
                    log_manager.emit(channel, "info", "使用合并镜像模式，在集群容器内启动模型")
                    container = docker_service.client.containers.get(head_container["id"])
                    exec_result = container.exec_run(
                        cmd=f"nohup {cmd_parts[0]} {' '.join(cmd_parts[1:])} > /tmp/vllm-{model_id}.log 2>&1 &",
                        detach=True,
                    )
                    log_manager.emit(channel, "info", f"模型进程已后台启动 (exec: {exec_result})")
                else:
                    container_name = f"{model_id}-vllm"
                    log_manager.emit(channel, "info", f"在集群网络中启动新容器: {container_name}")
                    container = docker_service.client.containers.run(
                        image=cluster["image"],
                        name=container_name,
                        detach=True,
                        network=cluster["network"],
                        ports={f"{port}/tcp": port},
                        command=cmd,
                        restart_policy={"Name": "unless-stopped"},
                    )
                    log_manager.emit(channel, "success", f"容器 {container_name} 启动成功: {container.short_id}")
            else:
                log_manager.emit(channel, "info", "独立模式启动模型")
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                log_manager.emit(channel, "info", f"进程已启动 PID: {process.pid}")
            
            tracker.update("启动模型容器/进程", "completed")
            
            # Step 3: Health check
            tracker.update("等待服务就绪", "in_progress", port=port)
            
            # Try to connect to the model endpoint
            max_wait = 120  # Wait up to 2 minutes
            start_time = time.time()
            is_ready = False
            
            while time.time() - start_time < max_wait:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(f"http://localhost:{port}/health", timeout=5)
                        if resp.status_code == 200:
                            is_ready = True
                            break
                except:
                    pass
                await asyncio.sleep(2)
            
            if is_ready:
                elapsed = time.time() - start_time
                tracker.update("等待服务就绪", "completed", 
                              port=port, 
                              startup_time_s=round(elapsed, 1))
                log_manager.emit(channel, "success", f"模型 {model_name} 启动成功 (耗时 {elapsed:.1f}s)")
                
                self.models[model_id] = {
                    "id": model_id,
                    "name": model_name,
                    "path": model_path,
                    "cluster_id": cluster_id,
                    "tensor_parallel_size": tensor_parallel_size,
                    "max_model_len": max_model_len,
                    "gpu_memory_utilization": gpu_memory_utilization,
                    "dtype": dtype,
                    "port": port,
                    "status": "running",
                    "cmd": cmd,
                    "startup_time_s": round(elapsed, 1),
                }
            else:
                tracker.update("等待服务就绪", "failed", 
                              error="模型启动超时，请检查日志")
                self.models[model_id] = {
                    "id": model_id,
                    "name": model_name,
                    "path": model_path,
                    "cluster_id": cluster_id,
                    "tensor_parallel_size": tensor_parallel_size,
                    "max_model_len": max_model_len,
                    "gpu_memory_utilization": gpu_memory_utilization,
                    "dtype": dtype,
                    "port": port,
                    "status": "failed",
                    "cmd": cmd,
                }
                log_manager.emit(channel, "error", f"模型 {model_name} 启动超时")
            
            return model_id, tracker
            
        except Exception as e:
            log_manager.emit(channel, "error", f"模型启动失败: {str(e)}")
            raise

    async def stop_model(self, model_id: str):
        model = self.models.get(model_id)
        if not model:
            raise ValueError(f"模型 {model_id} 不存在")
        channel = f"model:{model_id}"
        log_manager.emit(channel, "info", f"停止模型 {model['name']}")

        if model.get("cluster_id"):
            cluster = await docker_service.get_cluster(model["cluster_id"])
            if cluster and not cluster.get("use_combined"):
                try:
                    container = docker_service.client.containers.get(f"{model_id}-vllm")
                    container.stop(timeout=30)
                    container.remove(force=True)
                    log_manager.emit(channel, "info", "容器已停止并清理")
                except Exception:
                    pass

        model["status"] = "stopped"
        log_manager.emit(channel, "info", f"模型 {model['name']} 已停止")

    async def list_models(self) -> List[dict]:
        return [
            {
                "id": m["id"],
                "name": m["name"],
                "path": m["path"],
                "cluster_id": m.get("cluster_id"),
                "port": m["port"],
                "status": m["status"],
            }
            for m in self.models.values()
        ]

    async def run_benchmark_v2(
        self,
        model_path: str,
        tokenizer_path: str,
        dataset_name: str = "random",
        random_input_len: int = 2048,
        random_output_len: int = 2048,
        num_prompts: int = 5,
        trust_remote_code: bool = True,
        ignore_eos: bool = True,
        served_model_name: str = "llm",
        port: int = 8000,
        max_concurrency: Optional[int] = None,
    ) -> str:
        bench_id = f"bench-{uuid.uuid4().hex[:8]}"
        channel = f"bench:{bench_id}"

        log_manager.emit(channel, "info", f"开始创建性能测试任务")
        log_manager.emit(channel, "info", f"模型路径: {model_path}")
        log_manager.emit(channel, "info", f"Tokenizer路径: {tokenizer_path}")
        log_manager.emit(channel, "info", f"数据集: {dataset_name}")
        log_manager.emit(channel, "info", f"输入长度: {random_input_len}")
        log_manager.emit(channel, "info", f"输出长度: {random_output_len}")
        log_manager.emit(channel, "info", f"请求数量: {num_prompts}")
        log_manager.emit(channel, "info", f"服务端口: {port}")

        bench_cmd_parts = [
            "vllm bench serve",
            f"--model {model_path}",
            f"--dataset-name {dataset_name}",
            f"--tokenizer {tokenizer_path}",
            f"--random-input-len {random_input_len}",
            f"--random-output-len {random_output_len}",
            f"--num-prompts {num_prompts}",
            f"--served-model-name {served_model_name}",
            f"--port {port}",
        ]

        if trust_remote_code:
            bench_cmd_parts.append("--trust-remote-code")
        if ignore_eos:
            bench_cmd_parts.append("--ignore-eos")
        if max_concurrency:
            bench_cmd_parts.append(f"--max-concurrency {max_concurrency}")

        bench_cmd = " \\\n  ".join(bench_cmd_parts)
        log_manager.emit(channel, "info", f"执行 vllm bench serve 命令:\n{bench_cmd}")

        # Run benchmark and capture output
        try:
            process = await asyncio.create_subprocess_shell(
                bench_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_lines = []
            async for line in process.stdout:
                decoded = line.decode().strip()
                if decoded:
                    stdout_lines.append(decoded)
                    log_manager.emit(channel, "info", decoded)

            stderr_output = ""
            async for line in process.stderr:
                decoded = line.decode().strip()
                if decoded:
                    stderr_output += decoded + "\n"
                    log_manager.emit(channel, "warn", decoded)

            await process.wait()

            # Parse benchmark results
            result = self._parse_bench_output("\n".join(stdout_lines))
            self.benchmarks[bench_id] = {
                "id": bench_id,
                "model_path": model_path,
                "model_name": served_model_name,
                "status": "completed",
                "result": result,
            }
            log_manager.emit(channel, "success", "测试完成")
            return bench_id

        except Exception as e:
            log_manager.emit(channel, "error", f"测试失败: {str(e)}")
            self.benchmarks[bench_id] = {
                "id": bench_id,
                "model_path": model_path,
                "model_name": served_model_name,
                "status": "failed",
                "error": str(e),
            }
            raise

    def _parse_bench_output(self, output: str) -> dict:
        """Parse benchmark output into structured data."""
        result = {
            "raw_output": output,
            "metrics": {},
        }
        # Parse throughput
        for line in output.split("\n"):
            line = line.strip()
            if "Request throughput" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["request_throughput"] = parts[-1].strip()
            elif "Output token throughput" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["token_throughput"] = parts[-1].strip()
            elif "Total Token throughput" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["total_token_throughput"] = parts[-1].strip()
            elif "Mean TTFT" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["mean_ttft_ms"] = parts[-1].strip()
            elif "Median TTFT" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["median_ttft_ms"] = parts[-1].strip()
            elif "P99 TTFT" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["p99_ttft_ms"] = parts[-1].strip()
            elif "Mean TPOT" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["mean_tpot_ms"] = parts[-1].strip()
            elif "Median TPOT" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["median_tpot_ms"] = parts[-1].strip()
            elif "P99 TPOT" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["p99_tpot_ms"] = parts[-1].strip()
            elif "Mean ITL" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["mean_itl_ms"] = parts[-1].strip()
            elif "Median ITL" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["median_itl_ms"] = parts[-1].strip()
            elif "P99 ITL" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result["metrics"]["p99_itl_ms"] = parts[-1].strip()

        return result

    async def get_benchmark(self, bench_id: str) -> Optional[dict]:
        return self.benchmarks.get(bench_id)

    async def delete_benchmark(self, bench_id: str) -> bool:
        """Delete a benchmark record."""
        if bench_id in self.benchmarks:
            del self.benchmarks[bench_id]
            return True
        return False

    async def list_benchmarks(self) -> List[dict]:
        return [
            {
                "id": b["id"],
                "model_path": b["model_path"],
                "model_name": b["model_name"],
                "status": b["status"],
            }
            for b in self.benchmarks.values()
        ]


vllm_service = VLLMService()