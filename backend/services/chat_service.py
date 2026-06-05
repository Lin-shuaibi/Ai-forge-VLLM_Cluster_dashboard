"""Chat service placeholder."""
from typing import Dict, List, Optional

class ChatService:
    def __init__(self):
        self.sessions: Dict[str, List] = {}
    
    async def add_message(self, session_id: str, message: dict):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(message)
    
    async def get_messages(self, session_id: str) -> List[dict]:
        return self.sessions.get(session_id, [])
    
    async def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

chat_service = ChatService()