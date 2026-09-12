# Rate Limiting

The boilerplate ships crudauth's rate limiter with per-tier, per-path limits backed by Redis. API
routes are protected by default; authenticated requests key by user ID and anonymous requests by
trusted-proxy-aware client IP.

!!! tip "Building a full SaaS?"
    Rate limiting is part of the free foundation. **[FastroAI](https://fastro.ai)** bundles it with Stripe payments, entitlements, transactional email, a frontend, and AI agents - all wired together and production-ready. [Ship your SaaS faster →](https://fastro.ai)

## What's Built In

```text
backend/src/infrastructure/auth/setup.py
└── resolve_api_rate_limit()  crudauth per-request resolver

backend/src/modules/rate_limit/
├── models.py          RateLimit (tier_id, path, limit, period)
├── routes.py          GET / GET-by-name / PATCH / DELETE on /api/v1/rate-limits/
├── crud.py / service.py
└── schemas.py
```

The configured crudauth backend is initialized with the auth singleton in the app's lifespan.

## How a Request Flows Through It

1. **The router-level crudauth dependency runs** for each API request.
2. **`resolve_api_rate_limit`** looks up the user's tier and matching path row from the database.
3. **crudauth resolves the principal** and keys authenticated requests by user ID or anonymous requests by client IP.
4. **`increment_and_check`** atomically increments the crudauth counter and returns `(count, is_limited)`. The TTL on the key is set on first increment to `period` seconds.
5. **If `is_limited`**, raises `RateLimitException` (HTTP 429). Otherwise, sets `request.state.rate_limit_headers` so the middleware can attach them to the response.

The key shape (no window suffix — the TTL handles the window):

```text
ratelimit:{user_id_or_ip}:{action}
```

## Custom Enforcement

Shipped API routes already use a router-level dependency. For another router, reuse the same
crudauth API:

```python
from fastapi import APIRouter, Depends
from src.infrastructure.auth.setup import auth
from crudauth.ratelimit import KeyBy, RateLimit

router = APIRouter()


@router.post("/widgets", dependencies=[Depends(auth.rate_limit("widgets", RateLimit(10, 60), key=KeyBy.USER_OR_IP))])
async def create_widget(...): ...
```

Or apply it to every route in a router:

```python
router = APIRouter(dependencies=[Depends(auth.rate_limit("widgets", RateLimit(10, 60), key=KeyBy.USER_OR_IP))])
```

That's all that's required. The limiter is enabled with `RATE_LIMITER_ENABLED=true`.

## Configuration

```env
# Master toggle
RATE_LIMITER_ENABLED=true

# Behavior on backend errors:
#   true  → log and let the request through (recommended)
#   false → raise RateLimitException ("Access denied as a precaution")
RATE_LIMITER_FAIL_OPEN=true

# Defaults applied when the user has no tier or no matching rate-limit row
DEFAULT_RATE_LIMIT_LIMIT=100
DEFAULT_RATE_LIMIT_PERIOD=60          # seconds — 100/60s by default

# Redis backend
RATE_LIMITER_REDIS_HOST=redis         # use "localhost" without Docker
RATE_LIMITER_REDIS_PORT=6379
RATE_LIMITER_REDIS_DB=1               # rate-limiter DB (cache + session share DB 0, taskiq DB 3)
RATE_LIMITER_REDIS_PASSWORD=
RATE_LIMITER_REDIS_CONNECT_TIMEOUT=5
RATE_LIMITER_REDIS_POOL_SIZE=10

```

When `RATE_LIMITER_ENABLED=false`, the router-level dependency is a no-op. This is useful in tests
and for isolating performance issues.

## User-Tier vs IP-Based Limits

`KeyBy.USER_OR_IP` uses the request principal when authentication is present and falls back to
the client IP using `TRUSTED_PROXY_HOPS`. The resolver checks the current path against the user's
tier and falls back to the configured default.

## Path Matching

Rate-limit rows use the request path directly:

```python
def sanitize_path(path: str) -> str:
    return path.strip("/").replace("/", "_")

# /api/v1/users         → "api_v1_users"
# /api/v1/users/42      → "api_v1_users_42"
# /api/v1/users/{id}    → "api_v1_users_{id}"
```

Store the exact API path in the database, including its `/api/v1` prefix.

Note: paths with path parameters (`/users/42`) sanitize to `api_v1_users_42`, which means **each individual resource ID gets its own counter**. That's almost always what you want (otherwise a single hot resource could rate-limit unrelated reads), but if you specifically want a single counter for a parameterized route, store the rule under the literal pattern `api_v1_users_{id}` and write a small middleware that matches the route against the path template before sanitizing.

## Managing Rate-Limit Rules

The `RateLimit` model:

```python
class RateLimit(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "rate_limits"

    id: int
    tier_id: int        # FK to tiers.id
    name: str           # unique — used as the URL path on /rate-limits/{name}
    path: str           # exact request path the rule applies to
    limit: int          # max requests per period
    period: int         # seconds
```

### What the API exposes

| Method | Path                         | Auth        | Notes                                    |
|--------|------------------------------|-------------|------------------------------------------|
| GET    | `/api/v1/rate-limits/`       | Public      | Paginated list of all rate-limit rules   |
| GET    | `/api/v1/rate-limits/{name}` | Public      | Get a rule by name                       |
| PATCH  | `/api/v1/rate-limits/{name}` | Superuser   | Update an existing rule                  |
| DELETE | `/api/v1/rate-limits/{name}` | Superuser   | Delete a rule                            |

There's **no POST endpoint** for creating rate-limit rules. To seed initial rules, you have three options:

### Option 1: SQL / Migration

Add an Alembic migration that inserts the rows:

```python
# alembic/versions/xxxx_seed_rate_limits.py
def upgrade():
    op.execute("""
        INSERT INTO rate_limits (tier_id, name, path, "limit", period, created_at)
        VALUES
            (1, 'free_widgets_create', 'api_v1_widgets', 10, 60, NOW()),
            (2, 'pro_widgets_create',  'api_v1_widgets', 100, 60, NOW())
    """)
```

### Option 2: Custom Seed Script

Add a one-off in `backend/scripts/`:

```python
# backend/scripts/setup_rate_limits.py
import asyncio

from src.infrastructure.database.session import local_session
from src.modules.rate_limit.crud import crud_rate_limits


async def main():
    async with local_session() as db:
        await crud_rate_limits.create(db=db, object={
            "tier_id": 1, "name": "free_widgets_create",
            "path": "api_v1_widgets", "limit": 10, "period": 60,
        })
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
```

Run with `uv run python -m scripts.setup_rate_limits` (from `backend/`).

### Option 3: Add a SQLAdmin View

Mirror `UserAdmin` and `TierAdmin` to add a `RateLimitAdmin` view — see [Admin Panel → Adding Models](../admin-panel/adding-models.md). This gives you a UI for creating, editing, and deleting rules.

## Response Headers

When the crudauth limiter runs successfully, it attaches:

| Header                | Meaning                                          |
|-----------------------|--------------------------------------------------|
| `X-RateLimit-Limit`   | The configured limit for this user × path        |
| `X-RateLimit-Remaining` | How many requests are left in the current window |
| `X-RateLimit-Reset`   | Period (seconds) for the window                  |

These are standard-ish (formatted like the GitHub / Stripe convention, not RFC 6585). Frontends can read them to surface graceful "you're approaching your limit" UI.

## Programmatic Cache-like Operations

The provider exposes the same primitives the middleware uses, in case you need to apply rate limits outside the HTTP request path (background jobs that throttle calls to a third party, for example):

```python
from src.infrastructure.rate_limit import increment_and_check, get_count, reset

count, is_limited = await increment_and_check(
    key="external_api_calls:user_42",
    limit=100,
    period=3600,
    fail_open=True,
)

current = await get_count("external_api_calls:user_42")
await reset("external_api_calls:user_42")
```

Use a key prefix that doesn't collide with the HTTP rate limiter's `ratelimit:` namespace.

## Backend Differences

| Feature                     | Redis | Memcached |
|-----------------------------|-------|-----------|
| Atomic increment + TTL set  | Yes   | Yes       |
| `get_count` / `reset`       | Yes   | Yes       |
| Pattern-based reset         | Yes   | No        |
| Connection pooling          | Yes   | Yes       |

Both backends do everything the middleware needs. Pick Redis if you're already running it for cache or Taskiq.

## Production Considerations

### Pool sizing

`RATE_LIMITER_REDIS_POOL_SIZE=10` is enough for typical workloads. If you're seeing `redis.exceptions.ConnectionError` under load, it usually means pool exhaustion — raise the pool size or check upstream connection-leak issues first.

### Fail-open vs fail-closed

The default `RATE_LIMITER_FAIL_OPEN=true` means a Redis outage doesn't take your API down — requests pass through unrate-limited. This is the right call for most public APIs.

If you specifically need rate limits enforced even during cache outages (e.g. you're protecting an expensive AI inference endpoint that you don't want hammered), set `RATE_LIMITER_FAIL_OPEN=false`. Be aware: a flaky Redis connection now translates directly into 429s for users.

### Window behavior

The implementation uses a fixed-window counter (TTL on first increment). At the boundary between windows, a user can technically make `2 × limit` requests in a short span. For most use cases this is fine; if you need stricter sliding-window semantics, build that on top of the provider yourself.

### Anonymous-user limits

IP-based rate limits are easy to bypass with NAT / proxies / IPv6 rotation. They're a speed bump, not security. If you're trying to prevent abuse rather than control fair use, you need authentication, captchas, or upstream firewall rules — not just rate limits.

## Troubleshooting

### "My limit is not matching"

- Confirm `RATE_LIMITER_ENABLED=true`
- Confirm the rate limiter initialized cleanly at startup (look for `Cache backend not available` or similar)
- Confirm the dependency runs **before** the response is built (it does, by virtue of being a dependency — but if you're seeing an empty body the route may have errored earlier)

### "All requests look anonymous even though users are logged in"

`request.state.user` isn't being populated. Either implement the bridge middleware shown above, or accept that the rate limiter operates on IP only.

### "Path lookups never find the rate-limit row"

Verify the `path` column in `rate_limits` matches the exact request path, including `/api/v1`.

### "The rate-limiter dependency raises `RateLimiterBackendException`"

The Redis connection failed and `RATE_LIMITER_FAIL_OPEN=false`. Either fix Redis, switch to fail-open, or temporarily disable the limiter (`RATE_LIMITER_ENABLED=false`).

## Key Files

| Component             | Location                                                  |
|-----------------------|-----------------------------------------------------------|
| Middleware + dependency | `backend/src/infrastructure/rate_limit/middleware.py`   |
| Provider API          | `backend/src/infrastructure/rate_limit/provider.py`       |
| Backend implementations | `backend/src/infrastructure/rate_limit/backends/`       |
| Path sanitization     | `backend/src/infrastructure/rate_limit/utils.py`          |
| RateLimit model       | `backend/src/modules/rate_limit/models.py`                |
| Rate-limit routes     | `backend/src/modules/rate_limit/routes.py`                |
| Settings              | `backend/src/infrastructure/config/settings.py` (`RateLimiterSettings`) |

## Next Steps

- **[Tiers](../authentication/permissions.md#tier-based-authorization)** — Setting up user tiers
- **[Admin Panel → Adding Models](../admin-panel/adding-models.md)** — Adding a `RateLimitAdmin` view
- **[Caching → Cache Strategies](../caching/cache-strategies.md)** — Patterns that share the same Redis-as-state mindset
