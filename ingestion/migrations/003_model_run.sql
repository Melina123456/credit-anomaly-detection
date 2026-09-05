-- records every time the AI service trains and persists a model, so
-- /analyze can always load "the current model" instead of retraining
-- from scratch on every request.
CREATE TABLE IF NOT EXISTS model_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_path TEXT NOT NULL,
    feature_set TEXT NOT NULL,
    training_row_count INTEGER NOT NULL,
    contamination NUMERIC NOT NULL,
    precision_score NUMERIC,
    recall_score NUMERIC,
    f1_score NUMERIC
);
