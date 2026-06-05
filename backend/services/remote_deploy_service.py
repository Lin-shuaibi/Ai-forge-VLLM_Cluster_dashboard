"""Remote deployment service via SSH."""
import asyncio
import uuid
import time
import paramiko
from typing import Optional, Dict, List, Tuple
import httpx

from services.log_manager import log_manager
from services.docker_service import ProgressTracker


class RemoteDeployService:
    def __init__(self):
        self.deployments: Dict[str, dict] = {}
        self.ssh_clients: Dict[str, paramiko.SSHClient] = {}

    def _run_ssh(self, ssh: paramiko.SSHClient, cmd: str, timeout: int = 60) -> Tuple[str, str]:
        """Execute command on remote and return stdout, stderr."""
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors='replace').strip()
        err = stderr.read().decode(errors='replace').strip()
        return out, err

    async def deploy_model(
        self,
        host: str,
        username: str,
        password: str,
        model_path: str,
        model_name: str,
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
        """Deploy model on remote machine via SSH."""
        deployment_id = f"remote-{uuid.uuid4().hex[:8]}"
        channel = f"remote:{deployment_id}"
        
        total_steps = 5
        tracker = ProgressTracker(channel, total_steps)
        
        log_manager.emit(channel, "info", f"开始远程部署: {model_name}")
        log_manager.emit(channel, "info", f"目标主机: {host}")
        log_manager.emit(channel, "info", f"模型路径: {model_path}")
        
        ssh = None
        try:
            # Step 1: SSH connection
            tracker.update("建立SSH连接", "in_progress", host=host)
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password, timeout=30)
            self.ssh_clients[deployment_id] = ssh
            
            # Check remote environment
            out, err = self._run_ssh(ssh, "python3 --version 2>&1")
            python_version = out
            log_manager.emit(channel, "info", f"远程Python版本: {python_version}")
            
            # Check if remote has GPU
            out, err = self._run_ssh(ssh, "nvidia-smi --query-gpu=name --format=csv,noheader 2>&1 || echo 'NO_GPU'")
            has_gpu = "NO_GPU" not in out and out.strip()
            if has_gpu:
                log_manager.emit(channel, "info", f"远程GPU: {out}")
            else:
                log_manager.emit(channel, "warn", "远程机器无GPU，将尝试CPU模式部署")
            
            tracker.update("建立SSH连接", "completed", python_version=python_version, has_gpu=has_gpu)
            
            # Step 2: Check vllm installation
            tracker.update("检查依赖环境", "in_progress")
            out, err = self._run_ssh(ssh, "pip3 list 2>/dev/null | grep -i vllm")
            vllm_installed = bool(out.strip())
            
            if not vllm_installed:
                log_manager.emit(channel, "info", "远程机器未安装vllm，尝试安装...")
                out, err = self._run_ssh(ssh, "pip3 install vllm -q 2>&1", timeout=300)
                log_manager.emit(channel, "info", f"pip3 install vllm 输出: {out[:200]}")
                if err and "ERROR" in err.upper():
                    log_manager.emit(channel, "warn", f"vllm安装有警告: {err[:200]}")
                
                # Verify installation
                out, err = self._run_ssh(ssh, "python3 -c 'import vllm; print(vllm.__version__)' 2>&1")
                if "ModuleNotFoundError" in out or "ModuleNotFoundError" in err:
                    log_manager.emit(channel, "error", f"vllm安装失败: {out} {err}")
                    raise Exception(f"vllm安装失败，远程机器可能缺少GPU或依赖: {out}")
                log_manager.emit(channel, "success", f"vllm安装成功: {out}")
            else:
                log_manager.emit(channel, "info", f"vllm已安装: {out}")
            
            tracker.update("检查依赖环境", "completed")
            
            # Step 3: Check model path exists on remote
            tracker.update("检查模型文件", "in_progress")
            out, err = self._run_ssh(ssh, f"ls -la {model_path} 2>&1 | head -5")
            if "No such file" in out or "No such file" in err:
                log_manager.emit(channel, "error", f"远程模型路径不存在: {model_path}")
                raise Exception(f"远程模型路径不存在: {model_path}")
            log_manager.emit(channel, "info", f"模型路径验证通过: {out[:200]}")
            tracker.update("检查模型文件", "completed")
            
            # Step 4: Build and start vLLM command
            tracker.update("启动远程模型服务", "in_progress")
            
            cmd_parts = [
                "nohup python3 -m vllm.entrypoints.openai.api_server",
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
            
            cmd_parts.append(f"> /tmp/vllm-{deployment_id}.log 2>&1 &")
            full_cmd = " ".join(cmd_parts)
            
            log_manager.emit(channel, "info", f"执行远程命令: {full_cmd[:200]}...")
            out, err = self._run_ssh(ssh, full_cmd)
            log_manager.emit(channel, "info", f"命令输出: {out}")
            if err:
                log_manager.emit(channel, "warn", f"命令错误: {err[:200]}")
            
            # Get process ID
            time.sleep(2)
            out, err = self._run_ssh(ssh, f"ps aux | grep 'vllm.entrypoints.openai.api_server.*{port}' | grep -v grep")
            pid = out.split()[1] if out and len(out.split()) > 1 else None
            if pid:
                log_manager.emit(channel, "info", f"远程进程PID: {pid}")
            else:
                # Check log for errors
                out, err = self._run_ssh(ssh, f"tail -30 /tmp/vllm-{deployment_id}.log 2>&1")
                log_manager.emit(channel, "warn", f"进程未启动，日志: {out[:300]}")
                if out:
                    raise Exception(f"远程进程启动失败: {out[:300]}")
            
            tracker.update("启动远程模型服务", "completed", pid=pid)
            
            # Step 5: Health check
            tracker.update("检查远程服务健康", "in_progress", port=port)
            
            max_wait = 180
            start_time = time.time()
            is_ready = False
            last_error = ""
            
            while time.time() - start_time < max_wait:
                try:
                    # Check if process is still alive
                    if pid:
                        out, err = self._run_ssh(ssh, f"ps -p {pid} > /dev/null 2>&1 && echo 'running' || echo 'dead'")
                        if out == "dead":
                            out, err = self._run_ssh(ssh, f"tail -20 /tmp/vllm-{deployment_id}.log")
                            raise Exception(f"远程进程已终止，日志: {out[:300]}")
                    
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(f"http://{host}:{port}/health", timeout=5)
                        if resp.status_code == 200:
                            is_ready = True
                            break
                except Exception as e:
                    last_error = str(e)[:100]
                    log_manager.emit(channel, "debug", f"健康检查: {last_error}")
                await asyncio.sleep(3)
            
            if is_ready:
                elapsed = time.time() - start_time
                tracker.update("检查远程服务健康", "completed",
                              startup_time_s=round(elapsed, 1))
                log_manager.emit(channel, "success", f"远程模型 {model_name} 部署成功 (耗时 {elapsed:.1f}s)")
                
                self.deployments[deployment_id] = {
                    "id": deployment_id,
                    "host": host,
                    "username": username,
                    "model_name": model_name,
                    "model_path": model_path,
                    "port": port,
                    "pid": pid,
                    "status": "running",
                    "start_time": time.time(),
                }
                return deployment_id, tracker
            
            # Timeout
            out, err = self._run_ssh(ssh, f"tail -20 /tmp/vllm-{deployment_id}.log 2>&1")
            error_msg = f"远程服务启动超时 ({max_wait}s)。最后错误: {last_error}。日志: {out[:200]}"
            tracker.update("检查远程服务健康", "failed", error=error_msg)
            log_manager.emit(channel, "error", error_msg)
            raise Exception(error_msg)
            
        except Exception as e:
            log_manager.emit(channel, "error", f"远程部署失败: {str(e)}")
            if ssh:
                try:
                    ssh.close()
                except:
                    pass
                if deployment_id in self.ssh_clients:
                    del self.ssh_clients[deployment_id]
            raise

    async def get_deployment_status(self, deployment_id: str) -> dict:
        """Get status of a remote deployment."""
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            raise ValueError(f"部署 {deployment_id} 不存在")
        
        ssh = self.ssh_clients.get(deployment_id)
        if not ssh:
            return {"status": "unknown", "error": "SSH连接已断开"}
        
        try:
            pid = deployment.get("pid")
            if pid:
                out, err = self._run_ssh(ssh, f"ps -p {pid} > /dev/null 2>&1 && echo 'running' || echo 'dead'")
                deployment["process_status"] = out
            
            host = deployment["host"]
            port = deployment["port"]
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"http://{host}:{port}/health", timeout=5)
                    deployment["health_check"] = resp.status_code == 200
            except:
                deployment["health_check"] = False
            
            return deployment
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def stop_deployment(self, deployment_id: str):
        """Stop a remote deployment."""
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            raise ValueError(f"部署 {deployment_id} 不存在")
        
        channel = f"remote:{deployment_id}"
        log_manager.emit(channel, "info", f"停止远程部署 {deployment['model_name']}")
        
        ssh = self.ssh_clients.get(deployment_id)
        if ssh:
            try:
                pid = deployment.get("pid")
                if pid:
                    self._run_ssh(ssh, f"kill -9 {pid} 2>/dev/null")
                    log_manager.emit(channel, "info", f"已终止远程进程 {pid}")
                ssh.close()
            except:
                pass
        
        if deployment_id in self.ssh_clients:
            del self.ssh_clients[deployment_id]
        
        deployment["status"] = "stopped"
        log_manager.emit(channel, "info", f"远程部署 {deployment['model_name']} 已停止")

    async def list_deployments(self) -> List[dict]:
        """List all remote deployments."""
        return [
            {
                "id": d["id"],
                "host": d["host"],
                "model_name": d["model_name"],
                "model_path": d["model_path"],
                "port": d["port"],
                "status": d["status"],
                "start_time": d.get("start_time"),
            }
            for d in self.deployments.values()
        ]

    async def cleanup(self):
        """Clean up all SSH connections."""
        for deployment_id, ssh in self.ssh_clients.items():
            try:
                ssh.close()
            except:
                pass
        self.ssh_clients.clear()


remote_deploy_service = RemoteDeployService()