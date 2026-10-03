"""
In-Memory Sliding Window Rate Limiter for Grannus RuralCare AI.

Prevents:
  - DoS attacks on speech-to-text and LLM extraction APIs
  - Brute-force credential stuffing
  - Automated intake spamming
"""
import time
from collections import defaultdict, deque
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int = 60, burst_limit: int = 15):
        self.rpm = requests_per_minute
        self.burst = burst_limit
        # IP -> deque of timestamps
        self.clients: Dict[str, deque] = defaultdict(deque)

    def is_allowed(self, client_id: str) -> Tuple[bool, int, int]:
        """
        Check if request is within limits.
        Returns: (allowed, remaining, retry_after)
        """
        now = time.time()
        window_start = now - 60.0
        queue = self.clients[client_id]

        # Evict timestamps older than 60 seconds
        while queue and queue[0] < window_start:
            queue.popleft()

        # Check burst (requests in last 5 seconds)
        burst_start = now - 5.0
        recent_count = sum(1 for ts in queue if ts >= burst_start)
        if recent_count >= self.burst:
            retry_after = int(5.0 - (now - queue[-self.burst])) + 1
            return False, 0, max(retry_after, 1)

        # Check RPM
        if len(queue) >= self.rpm:
            retry_after = int(60.0 - (now - queue[0])) + 1
            return False, 0, max(retry_after, 1)

        queue.append(now)
        remaining = self.rpm - len(queue)
        return True, remaining, 0

    def cleanup(self):
        """Clean up inactive clients to prevent memory growth."""
        now = time.time()
        stale_clients = [ip for ip, q in self.clients.items() if not q or q[-1] < (now - 300)]
        for ip in stale_clients:
            del self.clients[ip]


# Singleton rate limiters
intake_limiter = SlidingWindowRateLimiter(requests_per_minute=30, burst_limit=10)
api_limiter = SlidingWindowRateLimiter(requests_per_minute=120, burst_limit=30)


async def rate_limit_patient_intake(request: Request):
    """FastAPI dependency for patient intake rate limiting."""
    client_ip = request.client.host if request.client else "unknown_ip"
    allowed, remaining, retry_after = intake_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Too many consultations requested. Please retry in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
