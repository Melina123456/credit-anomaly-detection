package cache

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// UpdateCreditPoolBalances recomputes balance for every pool
// from the full ledger, and upserts into credit_pool_balance.
func UpdateCreditPoolBalances(ctx context.Context, pool *pgxpool.Pool) (int, error) {
	rows, err := pool.Query(ctx, `
		SELECT pool_id, SUM(amount) AS balance
		FROM credit_transaction
		GROUP BY pool_id
	`)
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	type result struct {
		poolID  string
		balance float64
	}
	var results []result
	for rows.Next() {
		var r result
		if err := rows.Scan(&r.poolID, &r.balance); err != nil {
			return 0, err
		}
		results = append(results, r)
	}

	count := 0
	for _, r := range results {
		_, err := pool.Exec(ctx, `
			INSERT INTO credit_pool_balance (pool_id, balance, updated_at)
			VALUES ($1, $2, now())
			ON CONFLICT (pool_id) DO UPDATE
			SET balance = $2, updated_at = now()
		`, r.poolID, r.balance)
		if err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}
