package generator

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// InsertEvents writes events with an explicit ingested_at. Leaving it to the
// column's DEFAULT now() makes ingestion_lag_days — a model feature — depend
// on the wall-clock time the dataset happened to be generated, so the same
// seed produced different data on different runs.
func InsertEvents(ctx context.Context, pool *pgxpool.Pool, events []EventSpec, ingestedAt time.Time) error {
	for _, e := range events {
		_, err := pool.Exec(ctx, `
			INSERT INTO usage_event (tenant_id, feature_id, quantity, occurred_at, ingested_at, source)
			VALUES ($1, $2, $3, $4, $5, 'synthetic')
		`, e.TenantID, e.FeatureID, e.Quantity, e.OccurredAt, ingestedAt)
		if err != nil {
			return err
		}
	}
	return nil
}

// RecordGeneration stores the settings that produced the current dataset, so
// a trained model can be traced back to a seed that regenerates its data.
func RecordGeneration(ctx context.Context, pool *pgxpool.Pool, seed int64, ref time.Time, counts AnomalyCounts, eventCount int) error {
	_, err := pool.Exec(ctx, `
		INSERT INTO dataset_generation (seed, reference_time, anomaly_counts, event_count)
		VALUES ($1, $2, $3, $4)
	`, seed, ref, counts.String(), eventCount)
	return err
}
