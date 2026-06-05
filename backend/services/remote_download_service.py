"""Remote model download service via SSH (HuggingFace / ModelScope)."""
import asyncio
import re
import uuid
import paramiko
import threading
from typing import Optional, Dict

from services.log_manager import log_manager


class RemoteDownloadService:
    """Download models on remote machines via SSH using huggingface-cli or modelscope CLI."""

    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self.ssh_clients: Dict[str, paramiko.SSHClient] = {}
        self.lock = threading.Lock()

    def _run_ssh(self, ssh: paramiko.SSHClient, cmd: str, timeout: int = 60):
        """Execute command on remote, return stdout/stderr tuple."""
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors='replace').strip()
        err = stderr.read().decode(errors='replace').strip()
        return out, err

    async def download_model(
        self,
        host: str,
        username: str,
        password: str,
        model_id: str,
        target_dir: str,
        source: str = "huggingface",
        hf_token: Optional[str] = None,
    ) -> str:
        """Start remote model download. Returns task_id immediately."""
        task_id = "dl-" + uuid.uuid4().hex[:8]
        channel = "download:" + task_id

        with self.lock:
            self.tasks[task_id] = {
                "task_id": task_id,
                "host": host,
                "model_id": model_id,
                "target_dir": target_dir,
                "source": source,
                "status": "connecting",
                "progress": 0.0,
                "message": "",
                "speed": "",
            }

        log_manager.emit(channel, "info", f"开始远程下载: {model_id}")
        log_manager.emit(channel, "info", f"目标主机: {host}")
        log_manager.emit(channel, "info", f"下载源: {source}")
        log_manager.emit(channel, "info", f"目标目录: {target_dir}")

        # Run in background thread to avoid blocking
        threading.Thread(
            target=self._execute_download,
            args=(task_id, channel, host, username, password, model_id, target_dir, source, hf_token),
            daemon=True,
        ).start()

        return task_id

    def _execute_download(
        self, task_id, channel, host, username, password, model_id, target_dir, source, hf_token
    ):
        ssh = None
        try:
            # Step 1: SSH connect
            log_manager.emit(channel, "info", "建立SSH连接...")
            with self.lock:
                self.tasks[task_id]["status"] = "connecting"
                self.tasks[task_id]["progress"] = 0.05

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password, timeout=30)
            with self.lock:
                self.ssh_clients[task_id] = ssh
            log_manager.emit(channel, "info", "SSH连接成功")

            # Step 2: Ensure CLI tool installed
            with self.lock:
                self.tasks[task_id]["status"] = "preparing"
                self.tasks[task_id]["progress"] = 0.10

            if source == "huggingface":
                log_manager.emit(channel, "info", "检查 huggingface-cli ...")
                out, err = self._run_ssh(ssh, "huggingface-cli --version 2>&1 || echo 'NOT_FOUND'")
                if "NOT_FOUND" in out:
                    log_manager.emit(channel, "info", "安装 huggingface_hub ...")
                    out, err = self._run_ssh(ssh, "pip install huggingface_hub -q 2>&1", timeout=180)
                    log_manager.emit(channel, "info", f"安装输出: {out[:200]}")

                    # Verify
                    out, err = self._run_ssh(ssh, "huggingface-cli --version 2>&1 || echo 'FAIL'")
                    if "FAIL" in out:
                        raise Exception("huggingface-cli 安装失败")
                    log_manager.emit(channel, "success", f"huggingface-cli 安装成功: {out.strip()}")
                else:
                    log_manager.emit(channel, "info", f"huggingface-cli 已安装: {out.strip()}")

                # Set HF token if provided
                if hf_token:
                    log_manager.emit(channel, "info", "配置 HF Token ...")
                    self._run_ssh(ssh, f"huggingface-cli login --token {hf_token} 2>&1", timeout=30)

                # Build download command
                cmd = f"huggingface-cli download {model_id} --local-dir {target_dir} --local-dir-use-symlinks False 2>&1"
            else:
                log_manager.emit(channel, "info", "检查 modelscope CLI ...")
                out, err = self._run_ssh(ssh, "modelscope --version 2>&1 || echo 'NOT_FOUND'")
                if "NOT_FOUND" in out:
                    log_manager.emit(channel, "info", "安装 modelscope ...")
                    out, err = self._run_ssh(ssh, "pip install modelscope -q 2>&1", timeout=180)
                    log_manager.emit(channel, "info", f"安装输出: {out[:200]}")

                    out, err = self._run_ssh(ssh, "modelscope --version 2>&1 || echo 'FAIL'")
                    if "FAIL" in out:
                        raise Exception("modelscope CLI 安装失败")
                    log_manager.emit(channel, "success", f"modelscope CLI 安装成功: {out.strip()}")
                else:
                    log_manager.emit(channel, "info", f"modelscope CLI 已安装: {out.strip()}")

                # Build download command
                cmd = f"modelscope download --model {model_id} --local_dir {target_dir} 2>&1"

            # Step 3: Create target subdirectory with model name
            with self.lock:
                self.tasks[task_id]["status"] = "downloading"
                self.tasks[task_id]["progress"] = 0.15

            model_name = model_id.split('/')[-1]
            download_dir = f"{target_dir}/{model_name}"

            log_manager.emit(channel, "info", f"创建模型目录: {download_dir}")
            self._run_ssh(ssh, f"mkdir -p {download_dir}")

            # Update cmd to target the subdirectory
            if source == "huggingface":
                cmd = f"huggingface-cli download {model_id} --local-dir {download_dir} --local-dir-use-symlinks False 2>&1"
            else:
                cmd = f"modelscope download --model {model_id} --local_dir {download_dir} 2>&1"

            log_manager.emit(channel, "info", f"执行下载命令: {cmd[:200]}")
            log_manager.emit(channel, "info", f"开始下载 (通过SSH通道，实际速度取决于网络)...")

            # Execute with channel for live output
            transport = ssh.get_transport()
            exec_channel = transport.open_session()
            exec_channel.exec_command(cmd)

            prog_re = re.compile(r'(\d+)%')
            speed_re = re.compile(r'(\d+(?:\.\d+)?\s*(?:B|KB|MB|GB)/s)')
            buffer = b""

            while True:
                if exec_channel.recv_ready():
                    chunk = exec_channel.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    # Process lines
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        line = line_bytes.decode(errors='replace').strip()
                        if line:
                            log_manager.emit(channel, "progress", line, speed=None, progress=None)

                            m = prog_re.search(line)
                            if m:
                                try:
                                    pct = int(m.group(1)) / 100.0
                                    with self.lock:
                                        self.tasks[task_id]["progress"] = 0.15 + 0.80 * pct
                                except ValueError:
                                    pass

                            m = speed_re.search(line)
                            if m:
                                with self.lock:
                                    self.tasks[task_id]["speed"] = m.group(1)

                if exec_channel.recv_stderr_ready():
                    err_chunk = exec_channel.recv_stderr(4096)
                    if err_chunk:
                        err_line = err_chunk.decode(errors='replace').strip()
                        if err_line:
                            log_manager.emit(channel, "warn", err_line)

                if exec_channel.exit_status_ready():
                    break

            exit_code = exec_channel.recv_exit_status()

            # Process remaining buffer
            if buffer:
                line = buffer.decode(errors='replace').strip()
                if line:
                    log_manager.emit(channel, "progress", line)

            exec_channel.close()

            if exit_code == 0:
                with self.lock:
                    self.tasks[task_id]["status"] = "completed"
                    self.tasks[task_id]["progress"] = 1.0
                log_manager.emit(channel, "success", f"下载完成: {download_dir}")
                log_manager.emit(channel, "success", f"模型路径: {download_dir}")
            else:
                with self.lock:
                    self.tasks[task_id]["status"] = "failed"
                log_manager.emit(channel, "error", f"下载失败，退出码: {exit_code}")
                log_manager.emit(channel, "error", f"请检查模型ID是否正确，以及网络连接状态")

        except Exception as e:
            with self.lock:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["message"] = str(e)
            log_manager.emit(channel, "error", f"下载失败: {str(e)}")
        finally:
            if ssh:
                try:
                    ssh.close()
                except:
                    pass
                with self.lock:
                    if task_id in self.ssh_clients:
                        del self.ssh_clients[task_id]

    def get_task_status(self, task_id: str) -> dict:
        """Get download task status."""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return {"error": f"任务 {task_id} 不存在"}
            return {
                "task_id": task["task_id"],
                "status": task["status"],
                "progress": task["progress"],
                "message": task["message"],
                "speed": task.get("speed", ""),
                "host": task.get("host", ""),
                "model_id": task.get("model_id", ""),
                "target_dir": task.get("target_dir", ""),
                "source": task.get("source", ""),
            }

    def list_tasks(self) -> list:
        """List all download tasks."""
        with self.lock:
            return [
                {
                    "task_id": t["task_id"],
                    "status": t["status"],
                    "progress": t["progress"],
                    "host": t.get("host", ""),
                    "model_id": t.get("model_id", ""),
                    "target_dir": t.get("target_dir", ""),
                    "source": t.get("source", ""),
                }
                for t in self.tasks.values()
            ]

    def close_ssh(self, task_id: str):
        """Close SSH connection for a task."""
        with self.lock:
            ssh = self.ssh_clients.pop(task_id, None)
            if ssh:
                try:
                    ssh.close()
                except:
                    pass
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = "cancelled"


remote_download_service = RemoteDownloadService()
