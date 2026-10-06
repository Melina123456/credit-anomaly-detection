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
// for random tenant/feature pairs, within the `days` days ending at ref.
func InjectSpikes(rng *rand.Rand, ref time.Time, tenants []Tenant, features []Feature, days int, count int) []AnomalyEvent {
	var anomalies []AnomalyEvent

	for i := 0; i < count; i++ {
		t := tenants[rng.Intn(len(tenants))]
		f := features[rng.Intn(len(features))]
		baseline := tierBaseline[t.PlanTier]

		// 10x to 20x normal daily baseline, in a single event
		multiplier := 10 + rng.Float64()*10
		quantity := baseline * multiplier

		d := rng.Intn(days)
		offset := time.Duration(rng.Intn(24*60)) * time.Minute
		occurredAt := ref.AddDate(0, 0, -(d + 1)).Add(offset)

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
func InjectReplays(rng *rand.Rand, existing []EventSpec, count int) []AnomalyEvent {
	var anomalies []AnomalyEvent
	if len(existing) == 0 {
		return anomalies
	}

	for i := 0; i < count; i++ {
		e := existing[rng.Intn(len(existing))]
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
func InjectNegativeBalanceAttempts(ctx context.Context, pool *pgxpool.Pool, rng *rand.Rand, ref time.Time, tenants []Tenant, features []Feature, count int) ([]AnomalyEvent, error) {
	var anomalies []AnomalyEvent

	for i := 0; i < count; i++ {
		t := tenants[rng.Intn(len(tenants))]
		f := features[rng.Intn(len(features))]

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
		absBalance := balance
		if absBalance < 0 {
			absBalance = -absBalance
		}
		quantity := absBalance + absBalance*0.5 + 500

		anomalies = append(anomalies, AnomalyEvent{
			TenantID:    t.ID,
			FeatureID:   f.ID,
			Quantity:    quantity,
			OccurredAt:  ref,
			AnomalyType: "negative_balance_attempt",
		})
	}
	return anomalies, nil
}

// InjectOutOfOrderEvents creates events with occurred_at far in the past,
// simulating backdated/late-arriving data.
func InjectOutOfOrderEvents(rng *rand.Rand, ref time.Time, tenants []Tenant, features []Feature, count int) []AnomalyEvent {
	var anomalies []AnomalyEvent

	for i := 0; i < count; i++ {
		t := tenants[rng.Intn(len(tenants))]
		f := features[rng.Intn(len(features))]
		baseline := tierBaseline[t.PlanTier]

		// normal-looking quantity, but backdated 20-40 days
		daysBack := 20 + rng.Intn(20)
		occurredAt := ref.AddDate(0, 0, -daysBack)
		quantity := baseline / 10 // roughly one normal event's worth

		anomalies = append(anomalies, AnomalyEvent{
			TenantID:    t.ID,
			FeatureID:   f.ID,
			Quantity:    quantity,
			OccurredAt:  occurredAt,
			AnomalyType: "out_of_order",
		})
	}
	return anomalies
}

// InsertAnomalies writes each anomaly into usage_event, then labels it
// in anomaly_label with its type. ingested_at is set explicitly rather than
// left to the database clock, for the same reason as InsertEvents.
func InsertAnomalies(ctx context.Context, pool *pgxpool.Pool, anomalies []AnomalyEvent, ingestedAt time.Time) (int, error) {
	count := 0
	for _, a := range anomalies {
		var eventID string
		err := pool.QueryRow(ctx, `
			INSERT INTO usage_event (tenant_id, feature_id, quantity, occurred_at, ingested_at, source)
			VALUES ($1, $2, $3, $4, $5, 'synthetic_anomaly')
			RETURNING id
		`, a.TenantID, a.FeatureID, a.Quantity, a.OccurredAt, ingestedAt).Scan(&eventID)
		if err != nil {
			return count, err
		}

		_, err = pool.Exec(ctx, `
			INSERT INTO anomaly_label (usage_event_id, anomaly_type)
			VALUES ($1, $2)
		`, eventID, a.AnomalyType)
		if err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}
