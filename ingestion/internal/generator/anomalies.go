package generator

import (
	"math/rand"
	"time"
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
