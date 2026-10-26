import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]

# Float rounding can leave a refilled bucket at 0.9999999...; without this tolerance the
# limiter would keep sleeping ever-shorter intervals and never hand out the token.
_EPSILON = 1e-9


@dataclass
class TokenBucket:
    """`capacity` tokens, refilled continuously at `rate` tokens per second."""

    rate: float
    capacity: float
    tokens: float = field(init=False)
    updated_at: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def refill(self, now: float) -> None:
        if self.updated_at is not None:
            self.tokens = min(self.capacity, self.tokens + (now - self.updated_at) * self.rate)
        self.updated_at = now

    def seconds_until_available(self) -> float:
        return 0.0 if self.tokens >= 1 - _EPSILON else (1 - self.tokens) / self.rate


class RateLimiter:
    """Waits until every bucket has a token, then takes one from each.

    In-process only: each process (API, worker) has its own limiter, which is fine for
    our call volume (a few calls per sign-in, spec §7.2).
    """

    def __init__(
        self,
        buckets: Sequence[TokenBucket],
        *,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._buckets = buckets
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        # Waiters queue on the lock, so callers are served in arrival order.
        async with self._lock:
            while True:
                now = self._clock()
                for bucket in self._buckets:
                    bucket.refill(now)
                wait = max(bucket.seconds_until_available() for bucket in self._buckets)
                if wait <= 0:
                    for bucket in self._buckets:
                        bucket.tokens -= 1
                    return
                await self._sleep(wait)


PER_SECOND_LIMIT = 100
PER_HOUR_LIMIT = 36_000


def strict_bucket(limit: int, window_seconds: float, burst: float) -> TokenBucket:
    """A bucket that never lets more than `limit` requests into any `window_seconds` window.

    A bucket allows at most `capacity + rate * window` requests per window, so the refill
    rate is whatever the burst leaves over.
    """
    return TokenBucket(rate=(limit - burst) / window_seconds, capacity=burst)


def blizzard_rate_limiter(
    *, clock: Clock = time.monotonic, sleep: Sleep = asyncio.sleep
) -> RateLimiter:
    """Blizzard's per-client limits: 100 requests/second and 36,000 requests/hour (spec §7.2).

    Both are kept strictly (the hourly cap is reported to be strictly enforced), so we never
    rely on 429 retries. Sustained, the hourly limit dominates: about 10 requests/second.
    """
    return RateLimiter(
        [
            strict_bucket(PER_SECOND_LIMIT, 1, burst=PER_SECOND_LIMIT / 2),
            strict_bucket(PER_HOUR_LIMIT, 3600, burst=100),
        ],
        clock=clock,
        sleep=sleep,
    )
