CREATE TABLE IF NOT EXISTS tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    plan_tier TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS entitlement_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenant(id),
    feature_id UUID NOT NULL REFERENCES feature(id),
    usage_limit NUMERIC NOT NULL,
    period TEXT NOT NULL, -- e.g. 'monthly', 'daily'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS credit_pool (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenant(id),
    currency TEXT NOT NULL DEFAULT 'credits',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- append-only ledger, source of truth

CREATE TABLE IF NOT EXISTS credit_transaction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id UUID NOT NULL REFERENCES credit_pool(id),
    amount NUMERIC NOT NULL,
    type TEXT NOT NULL, -- 'debit', 'credit', 'adjustment'
    event_ref UUID,     -- links back to usage_event if applicable
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- raw ingested events
CREATE TABLE IF NOT EXISTS usage_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenant(id),
    feature_id UUID NOT NULL REFERENCES feature(id),
    quantity NUMERIC NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL DEFAULT 'synthetic',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- materialized read caches, rebuilt from ledger, NOT source of truth
CREATE TABLE IF NOT EXISTS credit_pool_balance (
    pool_id UUID PRIMARY KEY REFERENCES credit_pool(id),
    balance NUMERIC NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entitlement_usage (
    grant_id UUID PRIMARY KEY REFERENCES entitlement_grant(id),
    used NUMERIC NOT NULL DEFAULT 0,
    window_start TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
