import asyncio
from fastapi import WebSocket
from typing import List


class ConnectionManager:
    """
    Manages active WebSocket connections and provides methods for broadcasting messages.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepts a new WebSocket connection and adds it to the list."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Removes a WebSocket connection from the list."""
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Sends a JSON message to all active connections."""
        # Create a list of tasks to send messages concurrently
        tasks = [
            connection.send_json(message)
            for connection in self.active_connections
        ]
        # Run all sending tasks in parallel
        await asyncio.gather(*tasks, return_exceptions=True)

# Create a single, importable instance of the manager
manager = ConnectionManager()
