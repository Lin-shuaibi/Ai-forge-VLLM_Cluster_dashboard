"""Docker service for managing cluster containers with progress tracking."""
import asyncio
import uuid
import time
from typing import Optional, Dict, List, Tuple
import docker
from docker.errors import DockerException, NotFound, APIError

from config import settings
from services.log_manager import log_manager
from services.image_service import image_service


class ProgressTracker:
    """Track progress of long-running operations."""
    
    def __init__(self, channel: str, total_steps: int):
        self.channel = channel
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = time.time()
        self.step_details = {}
    
    def update(self, step_name: str, status: str = "in_progress", **details):
        """Update progress for a step."""
        self.current_step += 1
        self.step_details[step_name] = {
            "status": status,
            "timestamp": time.time(),
            **details
        }
        
        progress_pct = (self.current_step / self.total_steps) * 100
        
        log_manager.emit(self.channel, "progress", {
            "step": step_name,
            "current": self.current_step,
            "total": self.total_steps,
            "percentage": round(progress_pct, 1),
            "status": status,
            "details": details
        })
        
        if status == "completed":
            elapsed = time.time() - self.start_time
            log_manager.emit(self.channel, "info", 
                           f"步骤 '{step_name}' 完成 (耗时: {elapsed:.1f}s)")
        elif status == "failed":
            log_manager.emit(self.channel, "error", 
                           f"步骤 '{step_name}' 失败: {details.get('error', '未知错误')}")
    
    def get_progress(self) -> Dict:
        """Get current progress state."""
        elapsed = time.time() - self.start_time
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "percentage": (self.current_step / self.total_steps) * 100 if self.total_steps > 0 else 0,
            "elapsed_seconds": round(elapsed, 1),
            "steps": self.step_details
        }


class DockerClusterService:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except DockerException:
            self.client = None
        self.clusters: Dict[str, dict] = {}

    async def health_check(self) -> bool:
        try:
            if self.client is None:
                self.client = docker.from_env()
            self.client.ping()
            return True
        except Exception:
            return False

    async def create_cluster_with_progress(
        self,
        name: str,
        nodes: List[Dict[str, str]],
        image: str,
        use_combined: bool = False,
    ) -> Tuple[str, ProgressTracker]:
        """Create cluster with detailed progress tracking."""
        cluster_id = f"cluster-{uuid.uuid4().hex[:8]}"
        channel = f"cluster:{cluster_id}"
        
        # Calculate total steps: image check + image transfer to each node + network creation + container creation
        total_steps = 1 + len(nodes) + 1 + len(nodes)  # image check + transfers + network + containers
        tracker = ProgressTracker(channel, total_steps)
        
        log_manager.emit(channel, "info", f"开始创建集群 {name} (ID: {cluster_id})")
        log_manager.emit(channel, "info", f"使用镜像: {image}")
        log_manager.emit(channel, "info", f"节点数量: {len(nodes)}")
        log_manager.emit(channel, "info", f"使用合并镜像: {use_combined}")
        
        try:
            # Step 1: Check and ensure image exists on master
            tracker.update("检查主节点镜像", "in_progress", image=image)
            image_result = await image_service.check_image(image)
            if not image_result.get("exists"):
                tracker.update("检查主节点镜像", "failed", error=image_result.get("error", "镜像不存在"))
                raise ValueError(f"镜像 {image} 不存在: {image_result.get('error')}")
            tracker.update("检查主节点镜像", "completed", 
                          size_mb=image_result.get("size_mb"), 
                          layers=image_result.get("layers"))
            
            # Step 2: Transfer image to worker nodes
            tracker.update("传输镜像到工作节点", "in_progress", total_nodes=len(nodes))
            transfer_result = await image_service.ensure_image_on_nodes(image, nodes)
            
            if not transfer_result.get("overall_success"):
                failed_nodes = []
                for host, res in transfer_result.get("results", {}).items():
                    if not res.get("success"):
                        failed_nodes.append(host)
                tracker.update("传输镜像到工作节点", "failed", 
                              error=f"镜像传输失败到节点: {failed_nodes}")
                raise ValueError(f"镜像传输失败到节点: {failed_nodes}")
            
            tracker.update("传输镜像到工作节点", "completed", 
                          success_count=transfer_result.get("success_count"),
                          total_nodes=transfer_result.get("total_nodes"))
            
            # Step 3: Create overlay network
            tracker.update("创建overlay网络", "in_progress")
            network_name = f"{cluster_id}-net"
            try:
                self.client.networks.get(network_name)
                network_exists = True
            except NotFound:
                self.client.networks.create(
                    network_name,
                    driver="overlay",
                    attachable=True,
                )
                network_exists = False
            
            tracker.update("创建overlay网络", "completed", 
                          network_name=network_name, existed=network_exists)
            
            # Step 4: Create containers on each node
            containers = []
            head_ip = None
            
            for i, node in enumerate(nodes):
                node_ip = node.get("ip", "")
                node_user = node.get("username", "root")
                node_pass = node.get("password", "")
                node_name = f"{cluster_id}-node{i}"
                is_head = i == 0
                
                tracker.update(f"在节点 {node_ip} 上启动容器", "in_progress", 
                              node_name=node_name, is_head=is_head)
                
                env_vars = {}
                if is_head:
                    env_vars["RAY_HEAD"] = "true"
                    head_ip = node_ip
                else:
                    env_vars["RAY_HEAD"] = "false"
                    env_vars["RAY_ADDRESS"] = f"{head_ip}:{settings.ray_head_port}"
                
                ports = {}
                if is_head:
                    ports = {
                        f"{settings.ray_dashboard_port}/tcp": settings.ray_dashboard_port,
                        "8000/tcp": 8001 + i,
                    }
                
                try:
                    container = self.client.containers.run(
                        image=image,
                        name=node_name,
                        detach=True,
                        network=network_name,
                        environment=env_vars,
                        ports=ports,
                        command="ray start --head" if is_head else f"ray start --address={head_ip}:{settings.ray_head_port}",
                        restart_policy={"Name": "unless-stopped"},
                    )
                    containers.append({
                        "id": container.id,
                        "name": node_name,
                        "ip": node_ip,
                        "is_head": is_head,
                    })
                    
                    tracker.update(f"在节点 {node_ip} 上启动容器", "completed", 
                                  container_id=container.short_id)
                    
                except APIError as e:
                    tracker.update(f"在节点 {node_ip} 上启动容器", "failed", error=str(e))
                    raise
            
            # Step 5: Finalize cluster creation
            tracker.update("集群配置完成", "in_progress")
            
            self.clusters[cluster_id] = {
                "id": cluster_id,
                "name": name,
                "image": image,
                "use_combined": use_combined,
                "nodes": nodes,
                "containers": containers,
                "head_ip": head_ip,
                "network": network_name,
                "status": "running",
                "progress_tracker": tracker,
            }
            
            tracker.update("集群配置完成", "completed")
            
            log_manager.emit(channel, "success", f"集群 {name} 创建完成")
            return cluster_id, tracker
            
        except Exception as e:
            log_manager.emit(channel, "error", f"集群创建失败: {str(e)}")
            await self.cleanup_cluster(cluster_id)
            raise
    
    async def create_cluster(
        self,
        name: str,
        nodes: List[Dict[str, str]],
        image: str,
        use_combined: bool = False,
    ) -> str:
        """Backward compatible method without detailed progress."""
        cluster_id, _ = await self.create_cluster_with_progress(name, nodes, image, use_combined)
        return cluster_id

    async def cleanup_cluster(self, cluster_id: str):
        cluster = self.clusters.get(cluster_id)
        if not cluster:
            return
        channel = f"cluster:{cluster_id}"
        for c in cluster.get("containers", []):
            try:
                container = self.client.containers.get(c["id"])
                container.stop(timeout=10)
                container.remove(force=True)
                log_manager.emit(channel, "info", f"清理容器: {c['name']}")
            except Exception:
                pass
        try:
            net = self.client.networks.get(cluster["network"])
            net.remove()
        except Exception:
            pass
        self.clusters.pop(cluster_id, None)

    async def delete_cluster(self, cluster_id: str):
        cluster = self.clusters.get(cluster_id)
        if not cluster:
            raise ValueError(f"集群 {cluster_id} 不存在")
        channel = f"cluster:{cluster_id}"
        log_manager.emit(channel, "info", f"删除集群 {cluster['name']}")
        await self.cleanup_cluster(cluster_id)

    async def list_clusters(self) -> List[dict]:
        result = []
        for cid, c in self.clusters.items():
            result.append({
                "id": c["id"],
                "name": c["name"],
                "image": c["image"],
                "use_combined": c["use_combined"],
                "node_count": len(c["nodes"]),
                "head_ip": c["head_ip"],
                "status": c["status"],
            })
        return result

    async def get_cluster(self, cluster_id: str) -> Optional[dict]:
        c = self.clusters.get(cluster_id)
        if not c:
            return None
        return {
            "id": c["id"],
            "name": c["name"],
            "image": c["image"],
            "use_combined": c["use_combined"],
            "nodes": c["nodes"],
            "containers": c["containers"],
            "head_ip": c["head_ip"],
            "network": c["network"],
            "status": c["status"],
        }


docker_service = DockerClusterService()