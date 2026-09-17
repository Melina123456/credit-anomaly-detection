import os
import json

import redis

# Lazy, same reasoning as app.db.get_engine(): importing this module should
# never require Redis to be reachable — only actually calling one of these
# functions should.
_client = None


def get_client():
    global _client
    if _client is None:
        addr = os.getenv("REDIS_ADDR", "localhost:6379")
        _client = redis.Redis.from_url(f"redis://{addr}", decode_responses=True)
    return _client


def _baseline_key(tenant_id: str, feature_id: str) -> str:
    return f"baseline:{tenant_id}:{feature_id}"


def set_baseline(tenant_id: str, feature_id: str, median: float, mad: float) -> None:
    """Cache one tenant/feature's z-score baseline (median, MAD). Overwritten
    on every POST /train — there's no separate expiry, the cache is only ever
    as fresh as the last training run, same as the model itself."""
    get_client().set(_baseline_key(tenant_id, feature_id), json.dumps({"median": median, "mad": mad}))


def get_baseline(tenant_id: str, feature_id: str):
    """Returns (median, mad) if this tenant/feature was cached during the
    last training run, else None."""
    raw = get_client().get(_baseline_key(tenant_id, feature_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return data["median"], data["mad"]
