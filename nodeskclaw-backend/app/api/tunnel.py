"""Tunnel WebSocket endpoint — instance-initiated connection to backend."""

from fastapi import APIRouter, Depends, WebSocket

from app.core.deps import get_current_org

router = APIRouter()


@router.websocket("/tunnel/connect")
async def tunnel_connect(ws: WebSocket):
    from app.services.tunnel import tunnel_adapter
    await tunnel_adapter.handle_websocket(ws)


@router.get("/admin/tunnel/status")
async def tunnel_status(org_ctx=Depends(get_current_org)):
    from app.services.tunnel import tunnel_adapter
    return {"code": 0, "message": "success", "data": tunnel_adapter.get_status()}
