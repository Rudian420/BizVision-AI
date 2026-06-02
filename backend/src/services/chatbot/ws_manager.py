"""
BizVision AI — WebSocket Connection Manager

Tracks active chatbot WebSocket connections grouped by conversation so
streamed tokens can be routed (and broadcast, if a conversation is open
in multiple tabs). Auth token validation is performed on connect.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket, status
from jose import JWTError

from src.core.security import decode_token


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(
        self, websocket: WebSocket, conversation_id: UUID, token: str
    ) -> UUID | None:
        """Validate the JWT, accept the socket, register it, return user_id.

        Returns the authenticated user's UUID on success so the caller
        can scope persistence to that user. Returns `None` if the token
        is missing/invalid/expired or carries the wrong type — in which
        case the socket is already closed.
        """
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise JWTError("not an access token")
            sub = payload.get("sub")
            if not sub:
                raise JWTError("missing sub")
            user_id = UUID(str(sub))
        except (JWTError, ValueError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

        await websocket.accept()
        self._connections[conversation_id].add(websocket)
        return user_id

    def disconnect(self, websocket: WebSocket, conversation_id: UUID) -> None:
        conns = self._connections.get(conversation_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                self._connections.pop(conversation_id, None)

    async def broadcast(self, conversation_id: UUID, message: dict) -> None:
        for ws in list(self._connections.get(conversation_id, set())):
            await ws.send_json(message)
