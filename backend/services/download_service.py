"""Model download service using modelscope CLI."""
import asyncio
import re
import os
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

from services.log_manager import log_manager


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class DownloadTask:
    task_id: str
    model_name: str
    local_path: str
    remote_host: Optional[str] = None
    remote_user: Optional[str] = None
    remote_password: Optional[str] = None
    remote_model_name: Optional[str] = None
    remote_path: Optional[str] = None
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None


class ModelDownloadService:
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.logs: Dict[str, list] = {}
        self.speeds: Dict[str, str] = {}
        self.processes: Dict[str, asyncio.subprocess.Process] = {}  # 跟踪进程
        self.paused_tasks: Dict[str, bool] = {}  # 暂停状态

    async def check_modelscope_cli(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_shell(
                "modelscope --help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception:
            pass
        self.add_log("_system", "Installing modelscope...")
        proc = await asyncio.create_subprocess_shell(
            "pip install modelscope -q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            self.add_log("_system", "modelscope installed successfully")
            return True
        else:
            self.add_log("_system", f"modelscope install failed: {stderr.decode()}")
            return False

    async def create_download_task(
        self,
        model_name: str,
        local_path: str = "",
        remote_host: Optional[str] = None,
        remote_user: Optional[str] = None,
        remote_password: Optional[str] = None,
        remote_model_name: Optional[str] = None,
        remote_path: Optional[str] = None,
    ) -> str:
        import uuid
        task_id = f"download-{uuid.uuid4().hex[:8]}"
        task = DownloadTask(
            task_id=task_id,
            model_name=model_name,
            local_path=local_path,
            remote_host=remote_host,
            remote_user=remote_user,
            remote_password=remote_password,
            remote_model_name=remote_model_name,
            remote_path=remote_path,
            status=DownloadStatus.PENDING
        )
        self.tasks[task_id] = task
        asyncio.create_task(self._execute_download(task))
        return task_id

    async def _execute_download(self, task: DownloadTask):
        try:
            base_dir = '/data/models'
            model_dir = os.path.join(base_dir, task.model_name)
            task.local_path = model_dir
            self.add_log(task.task_id, f"Download target path: {model_dir}")

            if not await self.check_modelscope_cli():
                task.status = DownloadStatus.FAILED
                task.error = "Cannot install modelscope CLI"
                return

            task.status = DownloadStatus.DOWNLOADING
            task.progress = 0.0

            if task.remote_host:
                await self._download_from_remote(task)
            else:
                await self._download_local_cli(task)

        except Exception as e:
            task.status = DownloadStatus.FAILED
            task.error = str(e)
            self.add_log(task.task_id, f"Download failed: {e}")

    async def _download_local_cli(self, task: DownloadTask):
        cmd = f'modelscope download --model {task.model_name} --local_dir {task.local_path}'
        self.add_log(task.task_id, f"Command: {cmd}")
        os.makedirs(task.local_path, exist_ok=True)

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        prog_re = re.compile(r'(\d+(?:\.\d+)?)%')
        speed_re = re.compile(r'(\d+(?:\.\d+)?\s*(?:B|KB|MB|GB)/s)')

        async for line_bytes in proc.stdout:
            line = line_bytes.decode('utf-8', errors='replace').strip()
            if not line:
                continue
            self.add_log(task.task_id, line)

            m = prog_re.search(line)
            if m:
                try:
                    task.progress = float(m.group(1)) / 100.0
                except ValueError:
                    pass

            m = speed_re.search(line)
            if m:
                self.set_speed(task.task_id, m.group(1))

        await proc.wait()

        if proc.returncode == 0:
            task.progress = 1.0
            task.status = DownloadStatus.COMPLETED
            if task.task_id in self.processes:
                del self.processes[task.task_id]
            if task.task_id in self.paused_tasks:
                del self.paused_tasks[task.task_id]
            self.add_log(task.task_id, f"Download completed: {task.local_path}")
            self.set_speed(task.task_id, "")
        else:
            task.status = DownloadStatus.FAILED
            task.error = f"CLI return code: {proc.returncode}"
            if task.task_id in self.processes:
                del self.processes[task.task_id]
            if task.task_id in self.paused_tasks:
                del self.paused_tasks[task.task_id]
            self.add_log(task.task_id, f"Download failed, return code: {proc.returncode}")

    async def _download_from_remote(self, task: DownloadTask):
        import paramiko
        from scp import SCPClient

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname=task.remote_host,
                username=task.remote_user,
                password=task.remote_password,
                timeout=30
            )

            remote_path = task.remote_path or f"~/{task.remote_model_name or task.model_name}"
            stdin, stdout, stderr = ssh.exec_command(f"test -e {remote_path} && echo FOUND || echo NOT_FOUND")
            remote_exists = stdout.read().decode().strip()

            if remote_exists == "NOT_FOUND":
                raise Exception(f"Model not found on remote: {remote_path}")

            os.makedirs(task.local_path, exist_ok=True)
            task.progress = 0.1
            self.add_log(task.task_id, f"Starting SCP transfer: {task.remote_host}:{remote_path}")

            def scp_progress(filename, size, sent):
                if size > 0:
                    task.progress = 0.1 + 0.8 * (sent / size)
                    if sent > 0:
                        self.set_speed(task.task_id, "SCP transferring")

            with SCPClient(ssh.get_transport(), progress=scp_progress) as scp:
                scp.get(remote_path, task.local_path, recursive=True)

            task.progress = 1.0
            task.status = DownloadStatus.COMPLETED
            self.add_log(task.task_id, f"Remote download completed: {task.local_path}")

        finally:
            ssh.close()

    async def pause_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task is None or task.status != DownloadStatus.DOWNLOADING:
            return False
        proc = self.processes.get(task_id)
        if proc:
            try:
                proc.send_signal(19)  # SIGSTOP (Unix)
                self.paused_tasks[task_id] = True
            except:
                pass
        task.status = DownloadStatus.PAUSED
        self.add_log(task_id, "Task paused (process suspended)")
        return True

    async def stop_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task is None:
            return False
        proc = self.processes.get(task_id)
        if proc:
            try:
                proc.terminate()
                await asyncio.sleep(0.5)
                if proc.returncode is None:
                    proc.kill()
                del self.processes[task_id]
            except:
                pass
        if task_id in self.paused_tasks:
            del self.paused_tasks[task_id]
        task.status = DownloadStatus.STOPPED
        task.error = "Task stopped by user"
        self.add_log(task_id, "Task stopped (process terminated)")
        return True

    async def resume_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task is None or task.status != DownloadStatus.PAUSED:
            return False
        proc = self.processes.get(task_id)
        if proc and self.paused_tasks.get(task_id):
            try:
                proc.send_signal(18)  # SIGCONT (Unix)
                del self.paused_tasks[task_id]
            except:
                pass
        task.status = DownloadStatus.DOWNLOADING
        self.add_log(task_id, "Task resumed (process continued)")
        return True

    async def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self.tasks.get(task_id)

    def get_logs(self) -> Dict[str, list]:
        return self.logs

    def get_speeds(self) -> Dict[str, str]:
        return self.speeds

    def add_log(self, task_id: str, message: str):
        if task_id not in self.logs:
            self.logs[task_id] = []
        self.logs[task_id].append(message)
        if len(self.logs[task_id]) > 200:
            self.logs[task_id] = self.logs[task_id][-200:]

    def set_speed(self, task_id: str, speed: str):
        self.speeds[task_id] = speed

    async def list_tasks(self) -> list:
        return list(self.tasks.values())


model_download_service = ModelDownloadService()