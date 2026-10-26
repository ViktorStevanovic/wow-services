from app.integrations.blizzard.rate_limiter import (
    PER_HOUR_LIMIT,
    PER_SECOND_LIMIT,
    RateLimiter,
    TokenBucket,
    blizzard_rate_limiter,
)


class FakeClock:
    """A clock that only moves when the limiter sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        # Fail instead of hanging if the limiter ever loops on tiny sleeps again.
        assert len(self.sleeps) < 100_000, "limiter is stalling"
        self.sleeps.append(seconds)
        self.now += seconds


async def test_burst_up_to_capacity_without_waiting() -> None:
    clock = FakeClock()
    limiter = RateLimiter([TokenBucket(rate=10, capacity=5)], clock=clock, sleep=clock.sleep)

    for _ in range(5):
        await limiter.acquire()

    assert clock.sleeps == []


async def test_waits_for_refill_when_empty() -> None:
    clock = FakeClock()
    limiter = RateLimiter([TokenBucket(rate=10, capacity=1)], clock=clock, sleep=clock.sleep)

    await limiter.acquire()
    await limiter.acquire()

    assert clock.sleeps == [0.1]


async def test_slowest_bucket_decides() -> None:
    clock = FakeClock()
    fast = TokenBucket(rate=100, capacity=100)
    slow = TokenBucket(rate=1, capacity=2)
    limiter = RateLimiter([fast, slow], clock=clock, sleep=clock.sleep)

    for _ in range(3):
        await limiter.acquire()

    assert clock.sleeps == [1.0]


async def test_blizzard_limits_hold_per_second_and_per_hour() -> None:
    clock = FakeClock()
    limiter = blizzard_rate_limiter(clock=clock, sleep=clock.sleep)
    timestamps: list[float] = []

    # More than an hour's worth of requests, as fast as the limiter allows.
    for _ in range(PER_HOUR_LIMIT + 1_000):
        await limiter.acquire()
        timestamps.append(clock.now)

    def max_in_window(window: float) -> int:
        best, start = 0, 0
        for end, t in enumerate(timestamps):
            while t - timestamps[start] >= window:
                start += 1
            best = max(best, end - start + 1)
        return best

    assert max_in_window(1.0) <= PER_SECOND_LIMIT
    assert max_in_window(3600.0) <= PER_HOUR_LIMIT


async def test_does_not_stall_on_float_rounding() -> None:
    clock = FakeClock()
    limiter = blizzard_rate_limiter(clock=clock, sleep=clock.sleep)

    for _ in range(300):
        await limiter.acquire()

    # One sleep per token after the initial burst: no endless tiny sleeps.
    assert len(clock.sleeps) < 300
