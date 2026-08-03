package ledger

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// WriteDebitsFromEvents converts each usage_event into a debit
// in credit_transaction, using each tenant's credit_pool.
func WriteDebitsFromEvents(ctx context.Context, pool *pgxpool.Pool) (int, error) {
	rows, err := pool.Query(ctx, `
		SELECT ue.id, cp.id, ue.quantity
		FROM usage_event ue
		JOIN credit_pool cp ON cp.tenant_id = ue.tenant_id
		WHERE ue.id NOT IN (
			SELECT event_ref FROM credit_transaction WHERE event_ref IS NOT NULL
		)
	`)
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	type pending struct {
		eventID  string
		poolID   string
		quantity float64
	}
	var toInsert []pending
	for rows.Next() {
		var p pending
		if err := rows.Scan(&p.eventID, &p.poolID, &p.quantity); err != nil {
			return 0, err
		}
		toInsert = append(toInsert, p)
	}

	count := 0
	for _, p := range toInsert {
		_, err := pool.Exec(ctx, `
			INSERT INTO credit_transaction (pool_id, amount, type, event_ref)
			VALUES ($1, $2, 'debit', $3)
		`, p.poolID, -p.quantity, p.eventID)
		if err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}
