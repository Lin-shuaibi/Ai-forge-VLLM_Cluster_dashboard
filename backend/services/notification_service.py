"""Notification and alerting service."""
import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime
from persistence import PersistentStore

class NotificationService:
    def __init__(self):
        self.ws_clients = set()
        self.alert_rules = []
        self._load_alert_rules()
    
    def _load_alert_rules(self):
        """Load alert rules from database."""
        # Default rules
        self.alert_rules = [
            {
                "name": "GPU Overheat",
                "type": "gpu_temperature",
                "condition": {"field": "temperature", "operator": ">", "value": 85},
                "actions": ["in_app", "webhook"],
                "enabled": True
            },
            {
                "name": "High Memory Usage",
                "type": "memory_usage",
                "condition": {"field": "usage_percent", "operator": ">", "value": 90},
                "actions": ["in_app"],
                "enabled": True
            },
            {
                "name": "Node Offline",
                "type": "node_status",
                "condition": {"field": "status", "operator": "==", "value": "offline"},
                "actions": ["in_app", "email"],
                "enabled": True
            }
        ]
    
    async def create_notification(
        self,
        type: str,
        level: str,
        title: str,
        message: str,
        data: Dict = None
    ):
        """Create a new notification and broadcast to WebSocket clients."""
        from services.log_manager import log_manager
        
        notification = {
            "id": str(uuid.uuid4())[:8],
            "type": type,
            "level": level,
            "title": title,
            "message": message,
            "data": data or {},
            "read": False,
            "created_at": datetime.now().isoformat()
        }
        
        # Log to system
        log_level = "WARN" if level in ["warning", "error", "critical"] else "INFO"
        log_manager.broadcast(f"[{log_level}] {title}: {message}")
        
        # Broadcast via WebSocket
        await self._broadcast_ws({
            "type": "notification",
            "data": notification
        })
        
        # Check alert rules
        await self._check_alert_rules(type, data)
        
        return notification
    
    async def _broadcast_ws(self, message: Dict):
        """Broadcast message to all WebSocket clients."""
        import json
        message_json = json.dumps(message)
        for ws in self.ws_clients:
            try:
                await ws.send_text(message_json)
            except:
                # Remove disconnected client
                self.ws_clients.discard(ws)
    
    async def _check_alert_rules(self, event_type: str, event_data: Dict):
        """Check if event triggers any alert rules."""
        for rule in self.alert_rules:
            if not rule["enabled"] or rule["type"] != event_type:
                continue
            
            condition = rule["condition"]
            field_value = event_data.get(condition["field"])
            
            if self._evaluate_condition(field_value, condition):
                # Trigger alert
                await self._trigger_alert(rule, event_data)
    
    def _evaluate_condition(self, value, condition: Dict) -> bool:
        """Evaluate condition against value."""
        op = condition["operator"]
        target = condition["value"]
        
        if op == ">":
            return value > target
        elif op == ">=":
            return value >= target
        elif op == "<":
            return value < target
        elif op == "<=":
            return value <= target
        elif op == "==":
            return value == target
        elif op == "!=":
            return value != target
        elif op == "in":
            return value in target
        elif op == "not in":
            return value not in target
        return False
    
    async def _trigger_alert(self, rule: Dict, event_data: Dict):
        """Execute alert actions."""
        title = f"Alert: {rule['name']}"
        message = f"Condition triggered: {rule['condition']}"
        
        for action in rule.get("actions", []):
            if action == "in_app":
                await self.create_notification(
                    type="alert",
                    level="warning",
                    title=title,
                    message=message,
                    data={"rule": rule, "event": event_data}
                )
            elif action == "webhook":
                await self._send_webhook(rule, event_data)
            elif action == "email":
                await self._send_email_alert(rule, event_data)
    
    async def _send_webhook(self, rule: Dict, event_data: Dict):
        """Send alert to configured webhook."""
        # TODO: Implement webhook integration
        pass
    
    async def _send_email_alert(self, rule: Dict, event_data: Dict):
        """Send email alert."""
        # TODO: Implement email integration
        pass
    
    def register_ws_client(self, ws):
        """Register a WebSocket client for real-time notifications."""
        self.ws_clients.add(ws)
    
    def unregister_ws_client(self, ws):
        """Unregister a WebSocket client."""
        self.ws_clients.discard(ws)
    
    async def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        # TODO: Query from database
        return 0
    
    async def mark_as_read(self, notification_id: str):
        """Mark notification as read."""
        # TODO: Update in database
        pass

# Global instance
notification_service = NotificationService()
