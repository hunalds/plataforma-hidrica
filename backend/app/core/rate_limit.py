"""Límite de peticiones en memoria por clave (IP) con ventana deslizante.

Suficiente para una sola instancia del backend. Si en producción se ejecutan varias réplicas,
se reemplaza por un almacenamiento compartido (p. ej. Redis) sin cambiar la interfaz.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float = 60.0) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Registra un intento. Devuelve False si se superó el límite."""
        now = time.monotonic()
        with self._lock:
            q = self._events[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_events:
                return False
            q.append(now)
            return True

    def retry_after(self, key: str) -> int:
        with self._lock:
            q = self._events.get(key)
            if not q:
                return 0
            return max(1, int(self.window - (time.monotonic() - q[0])) + 1)
