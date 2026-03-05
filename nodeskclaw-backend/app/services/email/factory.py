"""EmailTransport 工厂 — 统一返回全局 SMTP 传输实现。"""

from __future__ import annotations

from functools import lru_cache

from app.services.email.transport import EmailTransport


@lru_cache(maxsize=1)
def get_email_transport() -> EmailTransport:
    from app.services.email.global_smtp import GlobalSmtpTransport
    return GlobalSmtpTransport()
