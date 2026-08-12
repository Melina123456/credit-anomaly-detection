CREATE TABLE IF NOT EXISTS anomaly_label (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usage_event_id UUID NOT NULL REFERENCES usage_event(id),
    anomaly_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);