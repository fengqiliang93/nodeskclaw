"""NodeHookManager — lifecycle event hooks for node join/leave/update/status changes."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

HookHandler = Callable[..., Coroutine[Any, Any, None]]


class NodeHookManager:
    def __init__(self) -> None:
        self._global_hooks: dict[str, list[HookHandler]] = defaultdict(list)
        self._type_hooks: dict[str, dict[str, list[HookHandler]]] = defaultdict(lambda: defaultdict(list))

    def on_global(self, event: str, handler: HookHandler) -> None:
        self._global_hooks[event].append(handler)
        logger.debug("Registered global hook: %s -> %s", event, handler.__name__)

    def on_type(self, node_type: str, event: str, handler: HookHandler) -> None:
        self._type_hooks[node_type][event].append(handler)
        logger.debug("Registered type hook: %s.%s -> %s", node_type, event, handler.__name__)

    async def emit(self, event: str, *, node_type: str | None = None, **kwargs) -> None:
        for handler in self._global_hooks.get(event, []):
            try:
                await handler(**kwargs)
            except Exception:
                logger.error("Global hook %s.%s failed", event, handler.__name__, exc_info=True)

        if node_type:
            for handler in self._type_hooks.get(node_type, {}).get(event, []):
                try:
                    await handler(**kwargs)
                except Exception:
                    logger.error(
                        "Type hook %s.%s.%s failed", node_type, event, handler.__name__,
                        exc_info=True,
                    )


node_hook_manager = NodeHookManager()
