package cache

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// UpdateEntitlementUsage recomputes usage per grant, within the
// current period window (daily = since start of today UTC).
func UpdateEntitlementUsage(ctx context.Context, pool *pgxpool.Pool) (int, error) {
	windowStart := time.Now().UTC().Truncate(24 * time.Hour)

	rows, err := pool.Query(ctx, `
		SELECT eg.id, SUM(ue.quantity) AS used
		FROM entitlement_grant eg
		JOIN usage_event ue
			ON ue.tenant_id = eg.tenant_id
			AND ue.feature_id = eg.feature_id
			AND ue.occurred_at >= $1
		GROUP BY eg.id
	`, windowStart)
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	type result struct {
		grantID string
		used    float64
	}
	var results []result
	for rows.Next() {
		var r result
		if err := rows.Scan(&r.grantID, &r.used); err != nil {
			return 0, err
		}
		results = append(results, r)
	}

	count := 0
	for _, r := range results {
		_, err := pool.Exec(ctx, `
			INSERT INTO entitlement_usage (grant_id, used, window_start, updated_at)
			VALUES ($1, $2, $3, now())
			ON CONFLICT (grant_id) DO UPDATE
			SET used = $2, window_start = $3, updated_at = now()
		`, r.grantID, r.used, windowStart)
		if err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}
