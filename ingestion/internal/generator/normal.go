package generator

import (
	"math/rand"
	"time"
)

type EventSpec struct {
	TenantID   string
	FeatureID  string
	Quantity   float64
	OccurredAt time.Time
}

// baseline usage per plan tier per feature — rough daily volume
var tierBaseline = map[string]float64{
	"enterprise": 500,
	"pro":        150,
	"free":       20,
}

// GenerateNormalEvents produces `eventsPerDay` events per tenant per feature
// per day, over the `days` days ending at ref, with gaussian noise around
// each tenant's baseline. Every timestamp is derived from ref rather than the
// wall clock, so the same seed and ref always produce the same events.
func GenerateNormalEvents(rng *rand.Rand, ref time.Time, tenants []Tenant, features []Feature, days int, eventsPerDay int) []EventSpec {
	var events []EventSpec

	for _, t := range tenants {
		baseline := tierBaseline[t.PlanTier]
		for _, f := range features {
			for d := 0; d < days; d++ {
				dayStart := ref.AddDate(0, 0, -(d + 1))
				for i := 0; i < eventsPerDay; i++ {
					// spread events randomly through the day
					offset := time.Duration(rng.Intn(24*60)) * time.Minute
					occurredAt := dayStart.Add(offset)

					// gaussian noise around baseline/eventsPerDay, floor at 1
					mean := baseline / float64(eventsPerDay)
					qty := mean + rng.NormFloat64()*(mean*0.2)
					if qty < 1 {
						qty = 1
					}

					events = append(events, EventSpec{
						TenantID:   t.ID,
						FeatureID:  f.ID,
						Quantity:   qty,
						OccurredAt: occurredAt,
					})
				}
			}
		}
	}
	return events
}