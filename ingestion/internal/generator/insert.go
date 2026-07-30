package generator

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

func InsertEvents(ctx context.Context, pool *pgxpool.Pool, events []EventSpec) error {
	for _, e := range events {
		_, err := pool.Exec(ctx, `
			INSERT INTO usage_event (tenant_id, feature_id, quantity, occurred_at, source)
			VALUES ($1, $2, $3, $4, 'synthetic')
		`, e.TenantID, e.FeatureID, e.Quantity, e.OccurredAt)
		if err != nil {
			return err
		}
	}
	return nil
}
