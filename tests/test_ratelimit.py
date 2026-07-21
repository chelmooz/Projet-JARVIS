"""Tests Rate limiter — check_rate_limit retourne (allowed, remaining)."""
import services.ratelimit as ratelimit_mod
from services.ratelimit import MAX_REQUESTS, check_rate_limit


class TestRateLimit:

    def setup_method(self):
        self._orig_hits = ratelimit_mod._hits
        ratelimit_mod._hits = {}

    def teardown_method(self):
        ratelimit_mod._hits = self._orig_hits

    def test_allows_within_limit(self):
        key = "test_allow"
        ratelimit_mod._hits[key] = []
        for i in range(59):
            allowed, remaining = check_rate_limit(key)
            assert allowed
            assert remaining == MAX_REQUESTS - (i + 1)

    def test_blocks_over_limit(self):
        key = "test_block"
        ratelimit_mod._hits[key] = []
        for _ in range(MAX_REQUESTS):
            check_rate_limit(key)
        allowed, remaining = check_rate_limit(key)
        assert not allowed
        assert remaining == 0

    def test_different_ips_independent(self):
        ratelimit_mod._hits["ip_a"] = []
        ratelimit_mod._hits["ip_b"] = []
        for _ in range(MAX_REQUESTS):
            check_rate_limit("ip_a")
        allowed_a, rem_a = check_rate_limit("ip_a")
        allowed_b, rem_b = check_rate_limit("ip_b")
        assert not allowed_a
        assert allowed_b
        assert rem_a == 0
        assert rem_b == MAX_REQUESTS - 1

    def test_window_expires(self, monkeypatch):
        fake_time = iter([100.0] * (MAX_REQUESTS + 1) + [161.0])
        monkeypatch.setattr("services.ratelimit.time.time", lambda: next(fake_time))
        key = "test_expire"
        ratelimit_mod._hits[key] = []
        for _ in range(MAX_REQUESTS):
            check_rate_limit(key)
        allowed, remaining = check_rate_limit(key)
        assert not allowed
        assert remaining == 0
        assert len(ratelimit_mod._hits[key]) >= MAX_REQUESTS + 1

    def test_remaining_decreases(self):
        key = "test_remaining"
        ratelimit_mod._hits[key] = []
        for i in range(5):
            _, rem = check_rate_limit(key)
            assert rem == MAX_REQUESTS - (i + 1)
