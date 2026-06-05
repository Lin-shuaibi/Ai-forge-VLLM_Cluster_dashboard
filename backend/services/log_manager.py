"""Centralized log manager with WebSocket broadcast."""
import asyncio
import time
from collections import defaultdict
from typing import Dict, List


class LogManager:
    def __init__(self):
        self.subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self.log_history: Dict[str, List[dict]] = defaultdict(list)
        self.max_history = 2000

    def subscribe(self, channel: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self.subscribers[channel].append(queue)
        # Send history
        for entry in self.log_history.get(channel, [])[-100:]:
            queue.put_nowait(entry)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue):
        if channel in self.subscribers and queue in self.subscribers[channel]:
            self.subscribers[channel].remove(queue)

    def emit(self, channel: str, level: str, message: str, **extra):
        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "channel": channel,
            **extra,
        }
        history = self.log_history[channel]
        history.append(entry)
        if len(history) > self.max_history:
            self.log_history[channel] = history[-self.max_history:]

        # Broadcast to subscribers
        dead = []
        for q in self.subscribers.get(channel, []):
            try:
                q.put_nowait(entry)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.subscribers[channel].remove(q)

        # Also broadcast to global channel
        for q in self.subscribers.get("global", []):
            try:
                q.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    def get_channels(self) -> List[str]:
        return list(self.log_history.keys())


log_manager = LogManager()