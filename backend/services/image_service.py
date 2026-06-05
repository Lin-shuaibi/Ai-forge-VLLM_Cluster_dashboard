"""Image management and transfer service."""
import os
import asyncio
import tempfile
import shutil
import base64
import json
import docker
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import paramiko
from scp import SCPClient
from config import settings
from services.log_manager import log_manager


class ImageService:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.ssh_clients: Dict[str, paramiko.SSHClient] = {}
        
    def _get_auth_config(self) -> Optional[Dict]:
        """Get docker registry auth config from settings."""
        if not settings.registry_auth:
            return None
        
        try:
            auth_data = json.loads(base64.b64decode(settings.registry_auth).decode())
            return {
                "username": auth_data.get("username"),
                "password": auth_data.get("password"),
                "registry": auth_data.get("registry", "")
            }
        except Exception as e:
            log_manager.emit("image_service", "error", f"Failed to parse registry auth: {e}")
            return None
    
    async def check_image(self, image_name: str) -> Dict:
        """Check if image exists locally, pull if not."""
        try:
            # Check if image exists
            try:
                image = self.docker_client.images.get(image_name)
                size_mb = sum(layer.size for layer in image.history()) / (1024 * 1024)
                return {
                    "exists": True,
                    "size_mb": round(size_mb, 2),
                    "layers": len(image.history())
                }
            except docker.errors.ImageNotFound:
                # Image doesn't exist, try to pull
                log_manager.emit("image_service", "info", f"Pulling image: {image_name}")
                return await self.pull_image(image_name)
                
        except Exception as e:
            return {"exists": False, "error": str(e)}
    
    async def pull_image(self, image_name: str) -> Dict:
        """Pull docker image with progress tracking."""
        try:
            auth_config = self._get_auth_config()
            
            # Pull image with streaming
            pull_result = self.docker_client.images.pull(
                image_name,
                auth_config=auth_config,
                stream=True,
                decode=True
            )
            
            # Track progress
            for line in pull_result:
                if "status" in line:
                    status = line.get("status", "")
                    progress = line.get("progress", "")
                    log_manager.emit("image_pull", "info", 
                                   f"{image_name}: {status} {progress}")
            
            # Get image info after pull
            image = self.docker_client.images.get(image_name)
            size_mb = sum(layer.size for layer in image.history()) / (1024 * 1024)
            
            log_manager.emit("image_service", "success", 
                           f"Image pulled successfully: {image_name} ({size_mb:.2f} MB)")
            
            return {
                "exists": True,
                "pulled": True,
                "size_mb": round(size_mb, 2),
                "layers": len(image.history())
            }
            
        except Exception as e:
            error_msg = f"Failed to pull image {image_name}: {e}"
            log_manager.emit("image_service", "error", error_msg)
            return {"exists": False, "error": error_msg}
    
    def save_image_to_tar(self, image_name: str, output_dir: str = None) -> str:
        """Save docker image to tar file."""
        if output_dir is None:
            output_dir = settings.image_cache_dir
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Create safe filename
        safe_name = image_name.replace("/", "_").replace(":", "_")
        tar_path = os.path.join(output_dir, f"{safe_name}.tar")
        
        # Save image
        log_manager.emit("image_service", "info", f"Saving image {image_name} to {tar_path}")
        
        with open(tar_path, 'wb') as f:
            for chunk in self.docker_client.images.get(image_name).save():
                f.write(chunk)
        
        size_mb = os.path.getsize(tar_path) / (1024 * 1024)
        log_manager.emit("image_service", "info", f"Image saved: {tar_path} ({size_mb:.2f} MB)")
        
        return tar_path
    
    def _get_ssh_client(self, host: str, username: str, password: str) -> paramiko.SSHClient:
        """Get or create SSH client for a host."""
        key = f"{host}:{username}"
        if key not in self.ssh_clients:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username=username, password=password, timeout=10)
            self.ssh_clients[key] = client
        return self.ssh_clients[key]
    
    async def transfer_image_to_node(
        self, 
        image_name: str, 
        node_host: str, 
        node_username: str, 
        node_password: str
    ) -> Dict:
        """Transfer image to worker node via SSH/SCP."""
        try:
            log_manager.emit("image_transfer", "info", 
                           f"Starting image transfer: {image_name} to {node_host}")
            
            # Step 1: Save image to tar
            tar_path = self.save_image_to_tar(image_name)
            
            # Step 2: Transfer via SCP
            ssh_client = self._get_ssh_client(node_host, node_username, node_password)
            
            # Get remote path
            remote_dir = "/tmp/vllm-images"
            remote_path = os.path.join(remote_dir, os.path.basename(tar_path))
            
            # Create remote directory
            stdin, stdout, stderr = ssh_client.exec_command(f"mkdir -p {remote_dir}")
            stdout.read()
            
            # Transfer file
            with SCPClient(ssh_client.get_transport()) as scp:
                scp.put(tar_path, remote_path)
            
            # Step 3: Load image on remote node
            log_manager.emit("image_transfer", "info", f"Loading image on {node_host}")
            
            # Load docker image
            stdin, stdout, stderr = ssh_client.exec_command(f"docker load -i {remote_path}")
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if error:
                log_manager.emit("image_transfer", "error", f"Failed to load image on {node_host}: {error}")
                return {"success": False, "error": error}
            
            # Clean up remote tar file
            ssh_client.exec_command(f"rm -f {remote_path}")
            
            # Clean up local tar file
            os.remove(tar_path)
            
            log_manager.emit("image_transfer", "success", 
                           f"Image transferred successfully to {node_host}")
            
            return {"success": True, "output": output}
            
        except Exception as e:
            error_msg = f"Failed to transfer image to {node_host}: {e}"
            log_manager.emit("image_transfer", "error", error_msg)
            return {"success": False, "error": error_msg}
    
    async def ensure_image_on_nodes(
        self,
        image_name: str,
        nodes: List[Dict]  # List of {"host": "...", "username": "...", "password": "..."}
    ) -> Dict:
        """Ensure image exists on all nodes, transfer if needed."""
        results = {}
        
        # First check and pull on master node
        master_result = await self.check_image(image_name)
        if not master_result.get("exists"):
            return {"overall_success": False, "error": f"Image not available on master: {master_result.get('error')}"}
        
        # Transfer to each node
        tasks = []
        for node in nodes:
            task = self.transfer_image_to_node(
                image_name,
                node["host"],
                node["username"],
                node["password"]
            )
            tasks.append(task)
        
        # Execute transfers in parallel
        transfer_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        success_count = 0
        for i, result in enumerate(transfer_results):
            node = nodes[i]
            if isinstance(result, Exception):
                results[node["host"]] = {"success": False, "error": str(result)}
            else:
                results[node["host"]] = result
                if result.get("success"):
                    success_count += 1
        
        overall_success = success_count == len(nodes)
        
        return {
            "overall_success": overall_success,
            "results": results,
            "success_count": success_count,
            "total_nodes": len(nodes)
        }
    
    def cleanup_cache(self):
        """Clean up cached tar files."""
        cache_dir = settings.image_cache_dir
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                if file.endswith(".tar"):
                    os.remove(os.path.join(cache_dir, file))
            log_manager.emit("image_service", "info", f"Cleaned up cache directory: {cache_dir}")


# Global instance
image_service = ImageService()