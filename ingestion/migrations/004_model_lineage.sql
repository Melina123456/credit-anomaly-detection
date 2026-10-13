-- one row per dataset the generator writes: enough to regenerate it exactly.
CREATE TABLE IF NOT EXISTS dataset_generation (
    id BIGSERIAL PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    seed BIGINT NOT NULL,
    reference_time TIMESTAMPTZ NOT NULL,
    anomaly_counts TEXT NOT NULL,
    event_count INTEGER NOT NULL
);

-- what each trained model came from: the data it saw (by content hash), the
-- dataset generation that was current at the time, the code that trained it,
-- and a hash of the saved model file itself.
ALTER TABLE model_run
    ADD COLUMN IF NOT EXISTS data_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS model_sha256 TEXT,
    ADD COLUMN IF NOT EXISTS git_commit TEXT,
    ADD COLUMN IF NOT EXISTS dataset_generation_id BIGINT REFERENCES dataset_generation(id);
