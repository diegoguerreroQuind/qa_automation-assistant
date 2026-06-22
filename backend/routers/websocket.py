"""
WebSocket endpoint for real-time generation progress.

Architecture:
  Celery worker → Redis pub/sub → FastAPI WS handler → browser

The Celery worker publishes events to channel ws:{execution_id}.
This handler subscribes to that channel and relays messages to connected clients.

Authentication:
  JWT is passed as query param ?token=<jwt> because the WebSocket protocol
  does not support custom headers during the handshake from browsers.
  The token is validated and execution ownership verified before accepting.
"""
import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.models.database import get_db
from backend.models.db import Execution, Project
from backend.security.jwt import decode_token
from backend.services.ws_manager import ws_manager

router = APIRouter(tags=["websocket"])
logger = logging.getLogger("qa_assistant.ws")

# WebSocket close codes (RFC 6455 custom range: 4000–4999)
_WS_UNAUTHORIZED = 4001
_WS_FORBIDDEN    = 4003


@router.websocket("/ws/executions/{execution_id}")
async def websocket_endpoint(
    execution_id: str,
    ws: WebSocket,
    token: str = Query(..., description="JWT de autenticación del usuario"),
    db: AsyncSession = Depends(get_db),
):
    # --- Auth: validate JWT ---
    try:
        payload = decode_token(token)
    except Exception:
        await ws.close(code=_WS_UNAUTHORIZED)
        return

    user_id = payload.get("sub")
    if not user_id:
        await ws.close(code=_WS_UNAUTHORIZED)
        return

    # --- Auth: verify execution belongs to this user ---
    result = await db.execute(
        select(Execution)
        .join(Project, Execution.project_id == Project.id)
        .where(Execution.id == execution_id, Project.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        await ws.close(code=_WS_FORBIDDEN)
        return

    # --- Accept and subscribe ---
    await ws_manager.connect(execution_id, ws)

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"ws:{execution_id}")

    redis_task: asyncio.Task | None = None

    async def _relay_redis():
        """Forward every Redis pub/sub message to connected WebSocket clients."""
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except json.JSONDecodeError:
                logger.warning("WS %s: mensaje pub/sub no es JSON válido, se ignora", execution_id)
                continue
            try:
                await ws_manager.broadcast(execution_id, data)
            except Exception:
                logger.error("WS %s: fallo al retransmitir mensaje", execution_id, exc_info=True)
                continue
            # Stop relay once generation is fully complete or fatally failed
            if data.get("type") in ("complete", "fatal_error"):
                break

    try:
        redis_task = asyncio.create_task(_relay_redis())

        while True:
            # Keep connection alive; send ping every 25s so proxies don't close it
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=25)
                if msg == "ping":
                    await ws.send_text('{"type":"pong"}')
            except asyncio.TimeoutError:
                await ws.send_text('{"type":"ping"}')

    except WebSocketDisconnect:
        pass
    finally:
        if redis_task and not redis_task.done():
            redis_task.cancel()
        try:
            await pubsub.unsubscribe(f"ws:{execution_id}")
            await pubsub.aclose()
            await r.aclose()
        except Exception:
            pass
        ws_manager.disconnect(execution_id, ws)
