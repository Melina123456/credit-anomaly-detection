package generator

import (
	"context"
	"math/rand"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type AnomalyEvent struct {
	TenantID    string
	FeatureID   string
	Quantity    float64
	OccurredAt  time.Time
	AnomalyType string
}

// InjectSpikes creates a few events with abnormally high quantity
// for random tenant/feature pairs, within the last `days` days.
func InjectSpikes(tenants []Tenant, features []Feature, days int, count int) []AnomalyEvent {
	var anomalies []AnomalyEvent
	now := time.Now().UTC()

	for i := 0; i < count; i++ {
		t := tenants[rand.Intn(len(tenants))]
		f := features[rand.Intn(len(features))]
		baseline := tierBaseline[t.PlanTier]

		// 10x to 20x normal daily baseline, in a single event
		multiplier := 10 + rand.Float64()*10
		quantity := baseline * multiplier

		d := rand.Intn(days)
		offset := time.Duration(rand.Intn(24*60)) * time.Minute
		dayStart := now.AddDate(0, 0, -d)
		occurredAt := time.Date(dayStart.Year(), dayStart.Month(), dayStart.Day(), 0, 0, 0, 0, time.UTC).Add(offset)

		anomalies = append(anomalies, AnomalyEvent{
			TenantID:    t.ID,
			FeatureID:   f.ID,
			Quantity:    quantity,
			OccurredAt:  occurredAt,
			AnomalyType: "spike",
		})
	}
	return anomalies
}

// InjectReplays picks random existing events and duplicates them exactly,
// simulating a replay/duplicate-submission attack.
func InjectReplays(existing []EventSpec, count int) []AnomalyEvent {
	var anomalies []AnomalyEvent
	if len(existing) == 0 {
		return anomalies
	}

	for i := 0; i < count; i++ {
		e := existing[rand.Intn(len(existing))]
		anomalies = append(anomalies, AnomalyEvent{
			TenantID:    e.TenantID,
			FeatureID:   e.FeatureID,
			Quantity:    e.Quantity,   // exact same quantity
			OccurredAt:  e.OccurredAt, // exact same timestamp
			AnomalyType: "replay",
		})
	}
	return anomalies
}

// InjectNegativeBalanceAttempts creates single large events that exceed
// a tenant's current balance, simulating an overspend attempt.
func InjectNegativeBalanceAttempts(ctx context.Context, pool *pgxpool.Pool, tenants []Tenant, features []Feature, count int) ([]AnomalyEvent, error) {
	var anomalies []AnomalyEvent
	now := time.Now().UTC()

	for i := 0; i < count; i++ {
		t := tenants[rand.Intn(len(tenants))]
		f := features[rand.Intn(len(features))]

		// fetch current balance for this tenant
		var balance float64
		err := pool.QueryRow(ctx, `
			SELECT cpb.balance FROM credit_pool_balance cpb
			JOIN credit_pool cp ON cp.id = cpb.pool_id
			WHERE cp.tenant_id = $1
		`, t.ID).Scan(&balance)
		if err != nil {
			return nil, err
		}

		// quantity deliberately exceeds current balance
		quantity := balance + balance*0.5 + 100

		anomalies = append(anomalies, AnomalyEvent{
			TenantID:    t.ID,
			FeatureID:   f.ID,
			Quantity:    quantity,
			OccurredAt:  now,
			AnomalyType: "negative_balance_attempt",
		})
	}
	return anomalies, nil
}
