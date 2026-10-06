"""Limits how often one visitor can call an expensive or sensitive endpoint.

  /chat           every message uses the Groq allowance, which is small on the free tier
  /auth/login     limiting attempts makes guessing passwords impractical
  /auth/register  stops scripts creating accounts in bulk

Each limit counts requests per visitor (by IP address) within a sliding window: "10 in
the last 60 seconds", not "10 per calendar minute", so there's no burst allowed at the
turn of each minute.

Counts are kept in memory. That is right for a single server process, which this demo
runs; several processes would each keep their own counts and would need a shared store
such as Redis instead.

Behind a proxy (as on most hosting), every request appears to come from the proxy's
address. Run uvicorn with --proxy-headers there, so it reads the visitor's real address
from the proxy. The address is never read from request headers here directly, because
anyone can write any value into a header.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_MAX_TRACKED_VISITORS = 10_000


class RateLimit:
    """Use as a FastAPI dependency: dependencies=[Depends(some_limit)]."""

    def __init__(self, limit: int, per_seconds: int):
        self.limit = limit
        self.per_seconds = per_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        visitor = request.client.host if request.client else "unknown"
        now = time.monotonic()

        hits = self._hits[visitor]
        while hits and now - hits[0] >= self.per_seconds:
            hits.popleft()  # forget requests that have left the window

        if len(hits) >= self.limit:
            wait = int(self.per_seconds - (now - hits[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Please try again in {wait} seconds.",
                headers={"Retry-After": str(wait)},
            )
        hits.append(now)

        if len(self._hits) > _MAX_TRACKED_VISITORS:
            self._forget_idle(now)

    def _forget_idle(self, now: float) -> None:
        """Keep memory bounded: drop visitors with nothing left in their window."""
        for visitor in [v for v, h in self._hits.items() if not h or now - h[-1] >= self.per_seconds]:
            del self._hits[visitor]

    def reset(self) -> None:
        self._hits.clear()


chat_per_minute = RateLimit(limit=10, per_seconds=60)
chat_per_day = RateLimit(limit=200, per_seconds=24 * 60 * 60)
auth_per_minute = RateLimit(limit=5, per_seconds=60)

ALL_LIMITS = [chat_per_minute, chat_per_day, auth_per_minute]
